import aiosqlite
from typing import Optional, Dict, Any, Set


async def get_next_planned_workout(
    db: aiosqlite.Connection, plan_id: int
) -> Optional[Dict[str, Any]]:
    """
    Return the next planned workout in the sequence that hasn't been logged as complete.
    Rest days that have been acknowledged are also considered done.
    """
    # Collect planned_workout_ids that have a completed log
    cursor = await db.execute(
        """
        SELECT DISTINCT planned_workout_id
        FROM workout_logs
        WHERE planned_workout_id IN (
            SELECT id FROM planned_workouts WHERE plan_id = ?
        )
        AND completed = 1
        """,
        (plan_id,),
    )
    rows = await cursor.fetchall()
    completed_ids: Set[int] = {row[0] for row in rows if row[0] is not None}

    # Walk workouts in order and return the first incomplete one
    cursor = await db.execute(
        "SELECT * FROM planned_workouts WHERE plan_id = ? ORDER BY week_number, day_number",
        (plan_id,),
    )
    all_workouts = await cursor.fetchall()

    for workout in all_workouts:
        if workout["id"] not in completed_ids:
            return dict(workout)

    return None  # All workouts completed


async def get_completed_workout_count(db: aiosqlite.Connection, plan_id: int) -> int:
    cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT planned_workout_id)
        FROM workout_logs
        WHERE planned_workout_id IN (
            SELECT id FROM planned_workouts WHERE plan_id = ?
        )
        AND completed = 1
        """,
        (plan_id,),
    )
    row = await cursor.fetchone()
    return row[0] if row else 0
