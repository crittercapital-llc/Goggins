import json
import aiosqlite
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from models import StartLogRequest, UpdateExercisesRequest, CompleteLogRequest

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/history")
async def get_log_history(
    limit: int = 20, offset: int = 0, db: aiosqlite.Connection = Depends(get_db)
):
    cursor = await db.execute(
        """
        SELECT wl.*,
               pw.focus, pw.day_label, pw.week_number, pw.day_number,
               tp.name AS plan_name,
               af.response_text AS feedback_text,
               af.id AS feedback_id
        FROM workout_logs wl
        LEFT JOIN planned_workouts pw ON wl.planned_workout_id = pw.id
        LEFT JOIN training_plans tp ON pw.plan_id = tp.id
        LEFT JOIN ai_feedback af
            ON af.feedback_type = 'post_workout' AND af.reference_id = wl.id
        WHERE wl.user_id = 1 AND wl.completed = 1
        ORDER BY wl.workout_date DESC, wl.completed_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    rows = await cursor.fetchall()
    result = []
    for row in rows:
        data = dict(row)
        if isinstance(data.get("exercises_completed"), str):
            try:
                data["exercises_completed"] = json.loads(data["exercises_completed"])
            except json.JSONDecodeError:
                data["exercises_completed"] = []
        result.append(data)
    return result


@router.post("/start")
async def start_log(
    request: StartLogRequest, db: aiosqlite.Connection = Depends(get_db)
):
    today = date.today().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO workout_logs
            (user_id, planned_workout_id, adapted_workout_id, workout_date,
             started_at, exercises_completed, completed)
        VALUES (1, ?, ?, ?, datetime('now'), '[]', 0)
        """,
        (request.planned_workout_id, request.adapted_workout_id),
    )
    log_id = cursor.lastrowid
    await db.commit()
    return {"log_id": log_id, "workout_date": today}


@router.put("/{log_id}/exercises")
async def update_exercises(
    log_id: int,
    request: UpdateExercisesRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        "SELECT id FROM workout_logs WHERE id = ? AND user_id = 1", (log_id,)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Log not found")

    await db.execute(
        "UPDATE workout_logs SET exercises_completed = ? WHERE id = ?",
        (json.dumps(request.exercises_completed), log_id),
    )
    await db.commit()
    return {"status": "saved"}


@router.post("/{log_id}/complete")
async def complete_log(
    log_id: int,
    request: CompleteLogRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        "SELECT id FROM workout_logs WHERE id = ? AND user_id = 1", (log_id,)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Log not found")

    completed_at = request.completed_at or datetime.utcnow().isoformat()
    await db.execute(
        """
        UPDATE workout_logs
        SET exercises_completed = ?,
            overall_rpe  = ?,
            energy_level = ?,
            notes        = ?,
            completed_at = ?,
            completed    = 1
        WHERE id = ?
        """,
        (
            json.dumps(request.exercises_completed),
            request.overall_rpe,
            request.energy_level,
            request.notes,
            completed_at,
            log_id,
        ),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM workout_logs WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    data = dict(row)
    if isinstance(data.get("exercises_completed"), str):
        data["exercises_completed"] = json.loads(data["exercises_completed"])
    return data


@router.get("/{log_id}")
async def get_log(log_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM workout_logs WHERE id = ? AND user_id = 1", (log_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Log not found")

    data = dict(row)
    if isinstance(data.get("exercises_completed"), str):
        data["exercises_completed"] = json.loads(data["exercises_completed"])
    return data
