import json
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, DB_PATH
from models import GeneratePlanRequest
from services.claude_service import generate_plan_stream

router = APIRouter(prefix="/plans", tags=["plans"])


async def _save_plan(db: aiosqlite.Connection, plan_json: dict, user_id: int = 1) -> int:
    # Deactivate previous plans
    await db.execute(
        "UPDATE training_plans SET is_active = 0 WHERE user_id = ?", (user_id,)
    )

    plan_name = plan_json.get("plan_name", "Training Plan")
    weeks_list = plan_json.get("weeks", [])
    total_weeks = plan_json.get("total_weeks", len(weeks_list))

    cursor = await db.execute(
        """
        INSERT INTO training_plans (user_id, name, total_weeks, plan_structure, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (user_id, plan_name, total_weeks, json.dumps(plan_json)),
    )
    plan_id = cursor.lastrowid

    for week in weeks_list:
        week_num = week.get("week_number", 1)
        for workout in week.get("workouts", []):
            await db.execute(
                """
                INSERT INTO planned_workouts
                    (plan_id, week_number, day_number, day_label, focus,
                     workout_structure, intended_intensity, is_rest_day)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    week_num,
                    workout.get("day_number", 1),
                    workout.get("day_label", f"Day {workout.get('day_number', 1)}"),
                    workout.get("focus", "Training"),
                    json.dumps(workout.get("workout_structure", {})),
                    workout.get("intended_intensity", "moderate"),
                    1 if workout.get("is_rest_day", False) else 0,
                ),
            )

    await db.commit()
    return plan_id


@router.post("/generate")
async def generate_plan(
    request: GeneratePlanRequest, db: aiosqlite.Connection = Depends(get_db)
):
    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = await cursor.fetchone()
    if not profile_row:
        raise HTTPException(
            status_code=400, detail="Create a profile first."
        )

    profile = dict(profile_row)
    profile["equipment"] = json.loads(profile["equipment"])

    weeks = request.weeks
    notes = request.notes

    async def event_generator():
        full_text = ""
        try:
            async for chunk in generate_plan_stream(profile, weeks, notes):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # Strip markdown fences if present
            clean = full_text.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            try:
                plan_data = json.loads(clean)
            except json.JSONDecodeError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'JSON parse error: {e}'})}\n\n"
                return

            async with aiosqlite.connect(DB_PATH) as save_db:
                save_db.row_factory = aiosqlite.Row
                plan_id = await _save_plan(save_db, plan_data)

            yield f"data: {json.dumps({'type': 'done', 'plan_id': plan_id, 'plan_name': plan_data.get('plan_name', 'Training Plan')})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_plan_history(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """
        SELECT id, name, total_weeks, is_active, created_at
        FROM training_plans
        WHERE user_id = 1
        ORDER BY created_at DESC
        """
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/active")
async def get_active_plan(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """
        SELECT * FROM training_plans
        WHERE is_active = 1 AND user_id = 1
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    plan_row = await cursor.fetchone()
    if not plan_row:
        return {"plan": None, "weeks": []}

    plan = dict(plan_row)
    plan_id = plan["id"]

    cursor = await db.execute(
        """
        SELECT * FROM planned_workouts
        WHERE plan_id = ?
        ORDER BY week_number, day_number
        """,
        (plan_id,),
    )
    workout_rows = await cursor.fetchall()

    weeks: dict = {}
    for row in workout_rows:
        w = dict(row)
        wn = w["week_number"]
        if wn not in weeks:
            weeks[wn] = {"week_number": wn, "workouts": []}
        weeks[wn]["workouts"].append(
            {
                "id": w["id"],
                "day_number": w["day_number"],
                "day_label": w["day_label"],
                "focus": w["focus"],
                "intended_intensity": w["intended_intensity"],
                "is_rest_day": bool(w["is_rest_day"]),
            }
        )

    # Compute which week the athlete is currently on
    cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT planned_workout_id) AS cnt
        FROM workout_logs
        WHERE planned_workout_id IN (SELECT id FROM planned_workouts WHERE plan_id = ?)
        AND completed = 1
        """,
        (plan_id,),
    )
    done_row = await cursor.fetchone()
    completed_count = done_row["cnt"] if done_row else 0

    training_days = [w for w in workout_rows if not w["is_rest_day"]]
    wpw = max(1, len(training_days) // max(1, plan["total_weeks"]))
    current_week = min(plan["total_weeks"], completed_count // wpw + 1)

    return {
        "plan": {
            "id": plan["id"],
            "name": plan["name"],
            "total_weeks": plan["total_weeks"],
            "current_week": current_week,
            "created_at": plan["created_at"],
        },
        "weeks": list(weeks.values()),
    }


@router.get("/{plan_id}")
async def get_plan(plan_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM training_plans WHERE id = ? AND user_id = 1", (plan_id,)
    )
    plan_row = await cursor.fetchone()
    if not plan_row:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = dict(plan_row)
    plan["plan_structure"] = json.loads(plan["plan_structure"])

    cursor = await db.execute(
        "SELECT * FROM planned_workouts WHERE plan_id = ? ORDER BY week_number, day_number",
        (plan_id,),
    )
    workout_rows = await cursor.fetchall()
    plan["planned_workouts"] = [dict(w) for w in workout_rows]
    return plan
