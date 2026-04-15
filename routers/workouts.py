import json
import aiosqlite
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, DB_PATH
from models import AdaptWorkoutRequest
from services.claude_service import adapt_workout_stream
from services.workout_service import get_next_planned_workout

router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.get("/today")
async def get_today_workout(db: aiosqlite.Connection = Depends(get_db)):
    today = date.today().isoformat()

    empty = {
        "date": today,
        "planned_workout": None,
        "adapted_workout": None,
        "recovery_score": None,
        "log_exists": False,
        "log_completed": False,
        "log_id": None,
    }

    # Active plan
    cursor = await db.execute(
        """
        SELECT * FROM training_plans
        WHERE is_active = 1 AND user_id = 1
        ORDER BY created_at DESC LIMIT 1
        """
    )
    plan = await cursor.fetchone()
    if not plan:
        return {**empty, "no_plan": True}

    # Next unlogged workout
    planned = await get_next_planned_workout(db, plan["id"])
    if not planned:
        return {**empty, "plan_complete": True}

    # Today's recovery score
    cursor = await db.execute(
        "SELECT * FROM recovery_scores WHERE score_date = ? AND user_id = 1",
        (today,),
    )
    recovery_row = await cursor.fetchone()
    recovery = dict(recovery_row) if recovery_row else None

    # Adapted workout (only if recovery score exists)
    adapted = None
    if recovery:
        cursor = await db.execute(
            """
            SELECT * FROM adapted_workouts
            WHERE planned_workout_id = ? AND workout_date = ?
            """,
            (planned["id"], today),
        )
        adapted_row = await cursor.fetchone()
        if adapted_row:
            adapted = dict(adapted_row)
            adapted["adapted_structure"] = json.loads(adapted["adapted_structure"])

    # Existing log
    cursor = await db.execute(
        """
        SELECT id, completed FROM workout_logs
        WHERE planned_workout_id = ? AND workout_date = ? AND user_id = 1
        LIMIT 1
        """,
        (planned["id"], today),
    )
    log_row = await cursor.fetchone()

    planned["workout_structure"] = json.loads(planned["workout_structure"])

    return {
        "date": today,
        "planned_workout": planned,
        "adapted_workout": adapted,
        "recovery_score": recovery,
        "log_exists": log_row is not None,
        "log_completed": bool(log_row["completed"]) if log_row else False,
        "log_id": log_row["id"] if log_row else None,
    }


@router.post("/adapt")
async def adapt_workout(
    request: AdaptWorkoutRequest, db: aiosqlite.Connection = Depends(get_db)
):
    today = date.today().isoformat()

    # Profile
    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = await cursor.fetchone()
    if not profile_row:
        raise HTTPException(status_code=400, detail="Profile not found")
    profile = dict(profile_row)
    profile["equipment"] = json.loads(profile["equipment"])

    # Planned workout
    cursor = await db.execute(
        "SELECT * FROM planned_workouts WHERE id = ?", (request.planned_workout_id,)
    )
    workout_row = await cursor.fetchone()
    if not workout_row:
        raise HTTPException(status_code=404, detail="Planned workout not found")
    planned = dict(workout_row)

    # Recovery score
    cursor = await db.execute(
        "SELECT * FROM recovery_scores WHERE id = ?", (request.recovery_score_id,)
    )
    recovery_row = await cursor.fetchone()
    if not recovery_row:
        raise HTTPException(status_code=404, detail="Recovery score not found")
    recovery = dict(recovery_row)

    planned_workout_id = request.planned_workout_id
    recovery_score_id = request.recovery_score_id

    async def event_generator():
        full_text = ""
        try:
            async for chunk in adapt_workout_stream(profile, planned, recovery):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            clean = full_text.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            try:
                adaptation = json.loads(clean)
            except json.JSONDecodeError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'JSON parse error: {e}'})}\n\n"
                return

            async with aiosqlite.connect(DB_PATH) as save_db:
                await save_db.execute(
                    """
                    DELETE FROM adapted_workouts
                    WHERE planned_workout_id = ? AND workout_date = ?
                    """,
                    (planned_workout_id, today),
                )
                cursor = await save_db.execute(
                    """
                    INSERT INTO adapted_workouts
                        (planned_workout_id, recovery_score_id, workout_date,
                         adapted_structure, adaptation_notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        planned_workout_id,
                        recovery_score_id,
                        today,
                        json.dumps(adaptation.get("adapted_structure", {})),
                        adaptation.get("adaptation_notes", ""),
                    ),
                )
                adapted_id = cursor.lastrowid
                await save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'adapted_workout_id': adapted_id, 'adaptation_notes': adaptation.get('adaptation_notes', '')})}\n\n"

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


@router.get("/{planned_workout_id}")
async def get_workout(
    planned_workout_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    cursor = await db.execute(
        "SELECT * FROM planned_workouts WHERE id = ?", (planned_workout_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout = dict(row)
    workout["workout_structure"] = json.loads(workout["workout_structure"])
    return workout
