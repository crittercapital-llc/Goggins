import json
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, DB_PATH
from models import ChatRequest
from services.claude_service import generate_feedback_stream, chat_stream

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/workout/{log_id}")
async def generate_workout_feedback(
    log_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    cursor = await db.execute(
        "SELECT * FROM workout_logs WHERE id = ? AND user_id = 1", (log_id,)
    )
    log_row = await cursor.fetchone()
    if not log_row:
        raise HTTPException(status_code=404, detail="Log not found")
    log = dict(log_row)

    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = await cursor.fetchone()
    if not profile_row:
        raise HTTPException(status_code=400, detail="Profile not found")
    profile = dict(profile_row)

    plan_name = "Training Program"
    planned_focus = "Workout"
    if log.get("planned_workout_id"):
        cursor = await db.execute(
            """
            SELECT pw.focus, pw.day_label, tp.name
            FROM planned_workouts pw
            JOIN training_plans tp ON pw.plan_id = tp.id
            WHERE pw.id = ?
            """,
            (log["planned_workout_id"],),
        )
        pw_row = await cursor.fetchone()
        if pw_row:
            plan_name = pw_row["name"]
            planned_focus = f"{pw_row['day_label']} — {pw_row['focus']}"

    cursor = await db.execute(
        "SELECT whoop_score FROM recovery_scores WHERE score_date = ? AND user_id = 1",
        (log.get("workout_date"),),
    )
    rec_row = await cursor.fetchone()
    recovery_score = rec_row["whoop_score"] if rec_row else None

    cursor = await db.execute(
        """
        SELECT wl.workout_date, wl.overall_rpe, pw.focus, wl.exercises_completed
        FROM workout_logs wl
        LEFT JOIN planned_workouts pw ON wl.planned_workout_id = pw.id
        WHERE wl.user_id = 1 AND wl.completed = 1 AND wl.id != ?
        ORDER BY wl.completed_at DESC
        LIMIT 3
        """,
        (log_id,),
    )
    recent_rows = await cursor.fetchall()
    summaries = []
    for row in recent_rows:
        rd = dict(row)
        try:
            exs = json.loads(rd.get("exercises_completed") or "[]")
        except json.JSONDecodeError:
            exs = []
        count = len([e for e in exs if isinstance(e, dict) and not e.get("skipped")])
        summaries.append(
            f"  {rd.get('workout_date')}: {rd.get('focus', 'Workout')} "
            f"— {count} exercises, RPE {rd.get('overall_rpe', '?')}/10"
        )
    recent_summary = "\n".join(summaries) if summaries else "No prior workouts"

    async def event_generator():
        full_text = ""
        try:
            async for chunk in generate_feedback_stream(
                profile, log, plan_name, planned_focus, recovery_score, recent_summary
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            async with aiosqlite.connect(DB_PATH) as save_db:
                cursor = await save_db.execute(
                    """
                    INSERT INTO ai_feedback
                        (user_id, feedback_type, reference_id, response_text)
                    VALUES (1, 'post_workout', ?, ?)
                    """,
                    (log_id, full_text),
                )
                feedback_id = cursor.lastrowid
                await save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'feedback_id': feedback_id})}\n\n"

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


@router.get("/{feedback_id}")
async def get_feedback(feedback_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM ai_feedback WHERE id = ? AND user_id = 1", (feedback_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return dict(row)


@router.post("/chat")
async def chat(request: ChatRequest, db: aiosqlite.Connection = Depends(get_db)):
    thread_id = request.thread_id
    messages = []

    if thread_id:
        cursor = await db.execute(
            "SELECT * FROM conversation_threads WHERE id = ?", (thread_id,)
        )
        thread_row = await cursor.fetchone()
        if not thread_row:
            raise HTTPException(status_code=404, detail="Thread not found")
        messages = json.loads(dict(thread_row)["messages"])

    cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = await cursor.fetchone()
    profile = dict(profile_row) if profile_row else {}

    system_context = (
        f"You are Goggins, a personal training AI helping {profile.get('name', 'the athlete')} "
        f"with their {profile.get('primary_goal', 'fitness')} training. "
        f"Be direct, specific, and motivating. Keep responses concise and actionable."
    )

    if request.context_type == "plan" and request.context_id:
        cursor = await db.execute(
            "SELECT name FROM training_plans WHERE id = ?", (request.context_id,)
        )
        plan_row = await cursor.fetchone()
        if plan_row:
            system_context += f"\n\nCurrent Program: {plan_row['name']}"

    new_message = request.message
    context_type = request.context_type
    context_id = request.context_id

    async def event_generator():
        full_response = ""
        try:
            async for chunk in chat_stream(messages, system_context, new_message):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            new_messages = messages + [
                {"role": "user", "content": new_message},
                {"role": "assistant", "content": full_response},
            ]

            async with aiosqlite.connect(DB_PATH) as save_db:
                if thread_id:
                    await save_db.execute(
                        """
                        UPDATE conversation_threads
                        SET messages = ?, updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (json.dumps(new_messages), thread_id),
                    )
                    saved_id = thread_id
                else:
                    cursor = await save_db.execute(
                        """
                        INSERT INTO conversation_threads
                            (thread_type, reference_id, messages)
                        VALUES (?, ?, ?)
                        """,
                        (
                            context_type or "general",
                            context_id,
                            json.dumps(new_messages),
                        ),
                    )
                    saved_id = cursor.lastrowid
                await save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'thread_id': saved_id})}\n\n"

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
