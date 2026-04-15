import aiosqlite
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from database import get_db
from models import RecoveryScoreCreate

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("")
async def create_recovery_score(
    data: RecoveryScoreCreate, db: aiosqlite.Connection = Depends(get_db)
):
    await db.execute(
        """
        INSERT INTO recovery_scores
            (user_id, score_date, whoop_score, hrv, rhr, sleep_hours, subjective_feel, notes)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(score_date) DO UPDATE SET
            whoop_score    = excluded.whoop_score,
            hrv            = excluded.hrv,
            rhr            = excluded.rhr,
            sleep_hours    = excluded.sleep_hours,
            subjective_feel = excluded.subjective_feel,
            notes          = excluded.notes
        """,
        (
            data.score_date,
            data.whoop_score,
            data.hrv,
            data.rhr,
            data.sleep_hours,
            data.subjective_feel,
            data.notes,
        ),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM recovery_scores WHERE score_date = ? AND user_id = 1",
        (data.score_date,),
    )
    row = await cursor.fetchone()
    return dict(row)


@router.get("/today")
async def get_today_recovery(db: aiosqlite.Connection = Depends(get_db)):
    today = date.today().isoformat()
    cursor = await db.execute(
        "SELECT * FROM recovery_scores WHERE score_date = ? AND user_id = 1",
        (today,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


@router.get("/history")
async def get_recovery_history(
    days: int = 30, db: aiosqlite.Connection = Depends(get_db)
):
    since = (date.today() - timedelta(days=days)).isoformat()
    cursor = await db.execute(
        """
        SELECT * FROM recovery_scores
        WHERE user_id = 1 AND score_date >= ?
        ORDER BY score_date DESC
        """,
        (since,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
