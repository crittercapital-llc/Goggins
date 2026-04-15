import os
import aiosqlite
from typing import AsyncGenerator

DB_PATH = os.environ.get("DB_PATH", "./goggins.db")

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    name TEXT NOT NULL DEFAULT 'Athlete',
    experience_level TEXT NOT NULL,
    primary_goal TEXT NOT NULL,
    secondary_goal TEXT,
    equipment TEXT NOT NULL DEFAULT '[]',
    days_per_week INTEGER NOT NULL DEFAULT 4,
    session_duration_minutes INTEGER NOT NULL DEFAULT 60,
    injuries_limitations TEXT,
    age INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS training_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    total_weeks INTEGER NOT NULL,
    plan_structure TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS planned_workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    week_number INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    day_label TEXT NOT NULL,
    focus TEXT NOT NULL,
    workout_structure TEXT NOT NULL DEFAULT '{}',
    intended_intensity TEXT NOT NULL DEFAULT 'moderate',
    is_rest_day INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (plan_id) REFERENCES training_plans(id)
);

CREATE TABLE IF NOT EXISTS recovery_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    score_date TEXT NOT NULL UNIQUE,
    whoop_score INTEGER NOT NULL,
    hrv INTEGER,
    rhr INTEGER,
    sleep_hours REAL,
    subjective_feel TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS adapted_workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planned_workout_id INTEGER NOT NULL,
    recovery_score_id INTEGER NOT NULL,
    workout_date TEXT NOT NULL,
    adapted_structure TEXT NOT NULL DEFAULT '{}',
    adaptation_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (planned_workout_id) REFERENCES planned_workouts(id),
    FOREIGN KEY (recovery_score_id) REFERENCES recovery_scores(id)
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    planned_workout_id INTEGER,
    adapted_workout_id INTEGER,
    workout_date TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    exercises_completed TEXT NOT NULL DEFAULT '[]',
    overall_rpe INTEGER,
    energy_level TEXT,
    notes TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    feedback_type TEXT NOT NULL,
    reference_id INTEGER,
    prompt_summary TEXT,
    response_text TEXT NOT NULL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cache_read_tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_type TEXT NOT NULL DEFAULT 'general',
    reference_id INTEGER,
    messages TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_planned_workouts_plan ON planned_workouts(plan_id, week_number, day_number);
CREATE INDEX IF NOT EXISTS idx_recovery_date ON recovery_scores(score_date);
CREATE INDEX IF NOT EXISTS idx_workout_logs_date ON workout_logs(workout_date);
CREATE INDEX IF NOT EXISTS idx_adapted_workouts_date ON adapted_workouts(workout_date);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
