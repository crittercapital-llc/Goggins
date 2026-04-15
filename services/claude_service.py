import json
import os
from typing import AsyncGenerator, Optional, List, Dict, Any

from anthropic import AsyncAnthropic

_client: Optional[AsyncAnthropic] = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """\
You are Goggins, an elite personal training AI that creates brutally effective,
science-based, periodized training programs with military precision and
motivational fire.

Your training plans follow these rules:
- Progressive overload is built in week-over-week across the program.
- Rep ranges match the primary goal:
    strength      → 1-5 reps, heavy, long rest (3-5 min)
    hypertrophy   → 6-12 reps, moderate weight, 60-90s rest
    endurance     → 15+ reps, lighter weight, 30-60s rest
    fat_loss      → 12-20 reps, moderate weight, 30-45s rest, supersets OK
    general_fitness → mixed 8-15 reps
- ONLY prescribe exercises the athlete can perform with their listed equipment.
- Include a deload week every 4th week (same exercises, ~50% volume).
- Every workout specifies exact exercises, sets, reps, rest periods, and a
  brief technique cue.

Output ONLY valid JSON — no markdown fences, no explanation text before or
after. Match this exact schema (all fields required):

{
  "plan_name": "string",
  "description": "string (2-3 sentences on program philosophy)",
  "total_weeks": 8,
  "weeks": [
    {
      "week_number": 1,
      "theme": "Foundation|Accumulation|Intensification|Deload",
      "workouts": [
        {
          "day_number": 1,
          "day_label": "Monday",
          "focus": "Lower Body – Squat Focus",
          "intended_intensity": "low|moderate|high",
          "is_rest_day": false,
          "workout_structure": {
            "warmup": [
              {"exercise": "string", "duration_seconds": 0, "reps": 0, "notes": "string"}
            ],
            "main": [
              {
                "exercise": "string",
                "sets": 4,
                "reps": "5",
                "weight_guidance": "string (e.g. 80% 1RM or RPE 8)",
                "rest_seconds": 180,
                "notes": "string",
                "superset_group": null
              }
            ],
            "accessory": [
              {
                "exercise": "string",
                "sets": 3,
                "reps": "10-12",
                "weight_guidance": "string",
                "rest_seconds": 60,
                "notes": "string",
                "superset_group": null
              }
            ],
            "cooldown": [
              {"exercise": "string", "duration_seconds": 30, "reps": 0, "notes": "string"}
            ]
          }
        },
        {
          "day_number": 2,
          "day_label": "Tuesday",
          "focus": "Rest & Recovery",
          "intended_intensity": "low",
          "is_rest_day": true,
          "workout_structure": {"warmup": [], "main": [], "accessory": [], "cooldown": []}
        }
      ]
    }
  ]
}"""


ADAPTATION_SYSTEM_PROMPT = """\
You are Goggins, a precision training AI. You adapt planned workouts based on
recovery data to maximise long-term progress and avoid injury.

Recovery zones and mandatory rules:
  0–33   RED   — Replace the entire workout with active recovery only:
                 20-30 min easy walk or light mobility work, no loaded movements.
  34–66  YELLOW — Keep the primary compound lift; reduce to 2-3 sets at 85% of
                  planned load. Cut total volume by ~30%. Drop accessories unless
                  the athlete's notes suggest they feel better than the score implies.
  67–84  GREEN  — Execute as planned. Fine to swap an exercise for an equivalent.
  85–100 PEAK   — Execute as planned. Add one extra working set to the main
                  compound lift and push the top-set intensity.

Output ONLY valid JSON — no markdown, no extra text:
{
  "adaptation_notes": "string — what changed and why, 1-3 sentences",
  "adapted_structure": {
    "warmup":    [{"exercise":"string","duration_seconds":0,"reps":0,"notes":"string"}],
    "main":      [{"exercise":"string","sets":0,"reps":"string","weight_guidance":"string","rest_seconds":0,"notes":"string","superset_group":null}],
    "accessory": [{"exercise":"string","sets":0,"reps":"string","weight_guidance":"string","rest_seconds":0,"notes":"string","superset_group":null}],
    "cooldown":  [{"exercise":"string","duration_seconds":0,"reps":0,"notes":"string"}]
  }
}"""


FEEDBACK_SYSTEM_PROMPT = """\
You are Goggins, a demanding but deeply supportive personal training AI.
You analyse completed workouts and deliver direct, actionable feedback.

Always follow this exact structure (no headers needed, just flowing prose):
1. Acknowledge the work with specific numbers — what was done, no vagueness.
2. Name 1-2 things done well and why they matter for the goal.
3. Identify ONE thing to improve or watch: form, progressive overload, effort.
4. Give ONE specific action item for the next session.
5. Close with a single Goggins-style sentence — raw, fire-filled, earned.

Hard rules:
- Under 280 words total.
- Be brutally honest. Celebrate PRs by name. Call out sandbagging.
- Never use bullet points or numbered lists in the response.
- Speak directly to the athlete ("you", "your")."""


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

async def generate_plan_stream(
    profile: Dict[str, Any],
    weeks: int,
    notes: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    client = get_client()
    equipment_str = ", ".join(profile.get("equipment") or ["bodyweight only"])

    user_prompt = (
        f"Create a {weeks}-week training plan for this athlete:\n\n"
        f"Name: {profile.get('name', 'Athlete')}\n"
        f"Experience Level: {profile.get('experience_level', 'intermediate')}\n"
        f"Primary Goal: {profile.get('primary_goal', 'general_fitness')}\n"
        f"Secondary Goal: {profile.get('secondary_goal') or 'none'}\n"
        f"Available Equipment: {equipment_str}\n"
        f"Training Days Per Week: {profile.get('days_per_week', 4)}\n"
        f"Session Duration: {profile.get('session_duration_minutes', 60)} minutes\n"
        f"Physical Limitations: {profile.get('injuries_limitations') or 'none'}\n"
        f"Age: {profile.get('age') or 'not specified'}\n"
        f"Additional Notes: {notes or 'none'}\n\n"
        f"Generate the complete {weeks}-week periodized plan. Week 1 should be "
        f"moderate intensity. Progress through mesocycles. Deload every 4th week. "
        f"Output ONLY valid JSON."
    )

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=[
            {
                "type": "text",
                "text": PLAN_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def adapt_workout_stream(
    profile: Dict[str, Any],
    planned_workout: Dict[str, Any],
    recovery_score: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    client = get_client()
    score = recovery_score.get("whoop_score", 70)

    if score <= 33:
        zone = "Red (Low Recovery)"
    elif score <= 66:
        zone = "Yellow (Moderate Recovery)"
    elif score <= 84:
        zone = "Green (Ready)"
    else:
        zone = "Blue (Peak)"

    # Parse workout_structure if it's a string
    ws = planned_workout.get("workout_structure", "{}")
    if isinstance(ws, str):
        try:
            ws = json.loads(ws)
        except json.JSONDecodeError:
            ws = {}

    user_prompt = (
        f"Today's Recovery Score: {score}/100 — Zone: {zone}\n"
        f"HRV: {recovery_score.get('hrv') or 'not provided'}\n"
        f"Resting HR: {recovery_score.get('rhr') or 'not provided'} bpm\n"
        f"Sleep: {recovery_score.get('sleep_hours') or 'not provided'} hours\n"
        f"How I Feel: {recovery_score.get('subjective_feel') or 'not reported'}\n"
        f"Notes: {recovery_score.get('notes') or 'none'}\n\n"
        f"Planned Workout — {planned_workout.get('day_label')} ({planned_workout.get('focus')}):\n"
        f"{json.dumps(ws, indent=2)}\n\n"
        f"Athlete Profile:\n"
        f"- Primary Goal: {profile.get('primary_goal', 'general_fitness')}\n"
        f"- Experience: {profile.get('experience_level', 'intermediate')}\n"
        f"- Limitations: {profile.get('injuries_limitations') or 'none'}\n\n"
        f"Adapt this workout for the recovery score. Output ONLY valid JSON."
    )

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=[
            {
                "type": "text",
                "text": ADAPTATION_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    ) as stream:
        async for text in stream.text_stream:
            yield text


def _format_exercises(exercises: List[Any]) -> str:
    lines = []
    for ex in exercises:
        if not isinstance(ex, dict):
            continue
        name = ex.get("exercise", "Unknown")
        if ex.get("skipped"):
            reason = ex.get("skip_reason", "no reason given")
            lines.append(f"  - {name}: SKIPPED ({reason})")
        else:
            sets_data = ex.get("sets") or []
            parts = []
            for s in sets_data:
                if not isinstance(s, dict):
                    continue
                reps = s.get("reps", "?")
                weight = s.get("weight_lbs")
                rpe = s.get("rpe")
                entry = f"{reps} reps"
                if weight:
                    entry = f"{reps}×{weight}lb"
                if rpe:
                    entry += f" @RPE{rpe}"
                parts.append(entry)
            lines.append(f"  - {name}: {', '.join(parts) if parts else 'logged (no set data)'}")
    return "\n".join(lines) if lines else "  (no exercises recorded)"


async def generate_feedback_stream(
    profile: Dict[str, Any],
    log: Dict[str, Any],
    plan_name: str,
    planned_focus: str,
    recovery_score: Optional[int],
    recent_logs_summary: str,
) -> AsyncGenerator[str, None]:
    client = get_client()

    exercises_raw = log.get("exercises_completed", "[]")
    if isinstance(exercises_raw, str):
        try:
            exercises = json.loads(exercises_raw)
        except json.JSONDecodeError:
            exercises = []
    else:
        exercises = exercises_raw or []

    exercises_text = _format_exercises(exercises)
    recovery_str = f"{recovery_score}/100" if recovery_score is not None else "not recorded"

    user_prompt = (
        f"Workout completed — here's the data:\n\n"
        f"Date: {log.get('workout_date')}\n"
        f"Program: {plan_name}\n"
        f"Session: {planned_focus}\n"
        f"Recovery Score Going In: {recovery_str}\n\n"
        f"What Was Done:\n{exercises_text}\n\n"
        f"Overall RPE: {log.get('overall_rpe') or 'not provided'}/10\n"
        f"Energy Level: {log.get('energy_level') or 'not provided'}\n"
        f"Athlete Notes: {log.get('notes') or 'none'}\n\n"
        f"Recent History (last 3 sessions):\n{recent_logs_summary or 'First workout logged'}\n\n"
        f"Provide post-workout feedback."
    )

    system_context = (
        f"{FEEDBACK_SYSTEM_PROMPT}\n\n"
        f"Current Program: {plan_name} — "
        f"{profile.get('primary_goal', 'general fitness')} focus for a "
        f"{profile.get('experience_level', 'intermediate')} athlete."
    )

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": system_context,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def chat_stream(
    thread_messages: List[Dict[str, Any]],
    system_context: str,
    new_message: str,
) -> AsyncGenerator[str, None]:
    client = get_client()
    messages = list(thread_messages) + [{"role": "user", "content": new_message}]

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=[
            {
                "type": "text",
                "text": system_context,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    ) as stream:
        async for text in stream.text_stream:
            yield text
