from pydantic import BaseModel, Field
from typing import Optional, List, Any


# --- User Profile ---

class UserProfileCreate(BaseModel):
    name: str = "Athlete"
    experience_level: str  # beginner | intermediate | advanced
    primary_goal: str  # strength | hypertrophy | endurance | fat_loss | general_fitness
    secondary_goal: Optional[str] = None
    equipment: List[str] = []
    days_per_week: int = Field(default=4, ge=2, le=7)
    session_duration_minutes: int = Field(default=60, ge=20, le=180)
    injuries_limitations: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=10, le=100)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    experience_level: Optional[str] = None
    primary_goal: Optional[str] = None
    secondary_goal: Optional[str] = None
    equipment: Optional[List[str]] = None
    days_per_week: Optional[int] = Field(default=None, ge=2, le=7)
    session_duration_minutes: Optional[int] = Field(default=None, ge=20, le=180)
    injuries_limitations: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=10, le=100)


# --- Training Plans ---

class GeneratePlanRequest(BaseModel):
    weeks: int = Field(default=8, ge=4, le=16)
    notes: Optional[str] = None


# --- Recovery ---

class RecoveryScoreCreate(BaseModel):
    score_date: str  # ISO date: "2026-04-13"
    whoop_score: int = Field(ge=0, le=100)
    hrv: Optional[int] = Field(default=None, ge=0, le=300)
    rhr: Optional[int] = Field(default=None, ge=20, le=200)
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    subjective_feel: Optional[str] = None  # terrible|poor|okay|good|great
    notes: Optional[str] = None


# --- Workout Adaptation ---

class AdaptWorkoutRequest(BaseModel):
    planned_workout_id: int
    recovery_score_id: int


# --- Workout Logs ---

class StartLogRequest(BaseModel):
    planned_workout_id: Optional[int] = None
    adapted_workout_id: Optional[int] = None


class UpdateExercisesRequest(BaseModel):
    exercises_completed: List[Any]


class CompleteLogRequest(BaseModel):
    exercises_completed: List[Any]
    overall_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    energy_level: Optional[str] = None  # low | medium | high
    notes: Optional[str] = None
    completed_at: Optional[str] = None


# --- Chat ---

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[int] = None
    context_type: Optional[str] = None  # plan | workout | general
    context_id: Optional[int] = None
