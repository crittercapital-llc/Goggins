import json
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from models import UserProfileCreate, UserProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    row = await cursor.fetchone()
    if not row:
        return {"exists": False}
    data = dict(row)
    data["equipment"] = json.loads(data["equipment"])
    return data


@router.post("")
async def create_profile(
    profile: UserProfileCreate, db: aiosqlite.Connection = Depends(get_db)
):
    equipment_json = json.dumps(profile.equipment)
    await db.execute("DELETE FROM user_profile WHERE id = 1")
    await db.execute(
        """
        INSERT INTO user_profile
            (id, name, experience_level, primary_goal, secondary_goal,
             equipment, days_per_week, session_duration_minutes,
             injuries_limitations, age)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile.name,
            profile.experience_level,
            profile.primary_goal,
            profile.secondary_goal,
            equipment_json,
            profile.days_per_week,
            profile.session_duration_minutes,
            profile.injuries_limitations,
            profile.age,
        ),
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    row = await cursor.fetchone()
    data = dict(row)
    data["equipment"] = json.loads(data["equipment"])
    return data


@router.put("")
async def update_profile(
    profile: UserProfileUpdate, db: aiosqlite.Connection = Depends(get_db)
):
    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")

    updates = profile.model_dump(exclude_none=True)
    if "equipment" in updates:
        updates["equipment"] = json.dumps(updates["equipment"])

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [1]
        await db.execute(
            f"UPDATE user_profile SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        await db.commit()

    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    row = await cursor.fetchone()
    data = dict(row)
    data["equipment"] = json.loads(data["equipment"])
    return data
