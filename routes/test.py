from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional, List
import uuid
import json
import shutil
import os

from db import get_db
from questions.class_7 import QUESTIONS
from services.evaluation_service import evaluate
from services.gemini_service import generate_listening_chat_response, evaluate_listening_conversation
from services.azure_service import transcribe_only, analyze_pronunciation, parse_result

router = APIRouter()

TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


@router.get("/questions")
def get_questions():
    """Return all questions (without answers) — useful for the frontend to pre-load."""
    safe = []
    for q in QUESTIONS:
        item = {k: v for k, v in q.items() if k not in ("answer", "correct_version")}
        safe.append(item)
    return {"questions": safe, "total": len(safe)}


@router.post("/start")
def start(name: str = Form(...), section: Optional[str] = None):
    """Create a new session and return the first question, optionally filtered by section."""
    session_id = str(uuid.uuid4())
    
    # Calculate indices based on section
    if section:
        indices = [i for i, q in enumerate(QUESTIONS) if q.get("section") == section]
    else:
        indices = list(range(len(QUESTIONS)))
    
    if not indices:
        return {"error": f"No questions found for section '{section}'"}, 404

    indices_json = json.dumps(indices)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (id, current_question, answers, scores, question_indices, student_name, chat_history, turn_metrics) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, 0, "[]", "[]", indices_json, name, "[]", "[]"),
    )
    conn.commit()
    conn.close()

    first_q = _safe_question(QUESTIONS[indices[0]], name=name)
    return {"session_id": session_id, "question": first_q, "total": len(indices)}


@router.post("/answer")
async def answer(
    session_id: str = Form(...),
    # For text-based answers (mcq, tap_wrong_word, open_text, rewrite, sentence_build)
    answer: Optional[str] = Form(None),
    # For fill_blank: comma-separated values e.g. "studied,carefully"
    answer_list: Optional[str] = Form(None),
    # For speech questions
    file: Optional[UploadFile] = File(None),
):
    """
    Submit an answer for the current question in a session.

    - For `fill_blank`  → send `answer_list` as comma-separated answers (e.g. "opened" or "studied,carefully")
    - For `speech`      → send audio file in `file` field
    - For everything else → send plain text in `answer`
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    session = cursor.fetchone()

    if not session:
        conn.close()
        return {"error": "Session not found"}, 404

    current_idx_within_indices = session["current_question"]
    indices = json.loads(session["question_indices"] or "[]")
    
    # If no indices were stored (old session), assume all questions
    if not indices:
        indices = list(range(len(QUESTIONS)))

    if current_idx_within_indices >= len(indices):
        conn.close()
        return {"error": "All questions in this quiz session are already answered."}, 400

    actual_q_index = indices[current_idx_within_indices]
    question = QUESTIONS[actual_q_index]
    answers = json.loads(session["answers"])
    scores = json.loads(session["scores"])

    # ── Route input to the right format per question type ─────────────────────
    qtype = question["type"]

    if qtype == "conversational_speech":
        if not file:
            conn.close()
            return {"error": "Audio file required for conversational listening"}

        temp_path = os.path.join(TEMP_DIR, f"{session_id}_{file.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Perform Pronunciation Assessment (Azure returns the transcript too!)
        # We pass empty reference_text to allow it to transcribe freely
        azure_raw = analyze_pronunciation(temp_path, reference_text="")
        parsed = parse_result(azure_raw)
        spoken = parsed["spoken"]
        
        # 2. Get history and student name
        history = json.loads(session["chat_history"] or "[]")
        name = session["student_name"] or "Student"
        
        if not history:
             # Add the Sam's initial greeting if history is empty
             history.append({"role": "model", "parts": [{"text": question["question"]}]})

        # 3. Add current turn to history
        history.append({"role": "user", "parts": [{"text": spoken}]})
        
        # 4. Generate AI response
        ai_resp_data = generate_listening_chat_response(history, student_name=name)
        ai_message = ai_resp_data["response"]
        is_finished = ai_resp_data["is_finished"]
        
        # 5. Add AI response to history
        history.append({"role": "model", "parts": [{"text": ai_message}]})
        
        turn_result = {
            "spoken": spoken,
            "ai_response": ai_message,
            "accuracy": parsed["accuracy"],
            "fluency": parsed["fluency"],
            "completeness": parsed["completeness"],
            "pronunciation": parsed["pronunciation"],
            "finished": is_finished,
            "score": 0 # Not a final score yet
        }
        
        os.remove(temp_path)

        # Update chat history and turn metrics in DB
        metrics = json.loads(session["turn_metrics"] or "[]")
        metrics.append({
            "accuracy": parsed["accuracy"], 
            "fluency": parsed["fluency"],
            "completeness": parsed["completeness"],
            "pronunciation": parsed["pronunciation"]
        })

        cursor.execute("UPDATE sessions SET chat_history=?, turn_metrics=? WHERE id=?", 
                       (json.dumps(history), json.dumps(metrics), session_id))
        
        if not is_finished:
            # Don't move to next question!
            conn.commit()
            conn.close()
            return {
                "done": False,
                "result": turn_result,
                "chat_response": ai_message, # Frontend can use this to update the Sammy's message
                "is_turn_based": True,
                "progress": {"current": current_idx_within_indices, "total": len(indices)}
            }
        else:
            # Finalize this conversational question
            avg_acc = sum(m["accuracy"] for m in metrics) / len(metrics) if metrics else 0
            avg_flu = sum(m["fluency"] for m in metrics) / len(metrics) if metrics else 0
            avg_comp = sum(m["completeness"] for m in metrics) / len(metrics) if metrics else 0
            avg_pron = sum(m["pronunciation"] for m in metrics) / len(metrics) if metrics else 0

            eval_result = evaluate_listening_conversation(history)
            result = {
                "score": eval_result["overall_score"],
                "feedback": eval_result["feedback"],
                "language_score": eval_result["language_score"],
                "relevance_score": eval_result["relevance_score"],
                "avg_accuracy": round(avg_acc, 1),
                "avg_fluency": round(avg_flu, 1),
                "avg_completeness": round(avg_comp, 1),
                "avg_pronunciation": round(avg_pron, 1),
                "spoken": spoken,
                "history": history
            }

    elif qtype == "speech":
        if not file:
            conn.close()
            return {"error": "Audio file required for speech questions"}

        temp_path = os.path.join(TEMP_DIR, f"{session_id}_{file.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = evaluate(question, temp_path)
        os.remove(temp_path)

    elif qtype == "fill_blank":
        # accept comma-separated string or just a plain answer for single blanks
        raw = answer_list or answer or ""
        parsed_list = [a.strip() for a in raw.split(",")]
        result = evaluate(question, parsed_list)

    else:
        # Check if it was a conversational turn
        history = json.loads(session["chat_history"] or "[]")
        
        # If it was a writing conversation, initialize history with initial_message if empty
        if qtype == "conversational_writing" and not history:
             history.append({"role": "model", "content": question.get("initial_message", question["question"])})

        result = evaluate(question, answer or "", conversation_history=history)
        
        # If is_turn_based, return early!
        if result.get("is_turn_based"):
            new_history = result.get("conversation_history", history)
            cursor.execute("UPDATE sessions SET chat_history=? WHERE id=?", (json.dumps(new_history), session_id))
            conn.commit()
            conn.close()
            return {
                "done": False,
                "result": result,
                "chat_response": result["chat_response"],
                "is_turn_based": True,
                "progress": {"current": current_idx_within_indices, "total": len(indices)}
            }

    # ── Persist (Final) ───────────────────────────────────────────────────────
    answers.append(result)
    scores.append(result["score"])
    next_idx_within_indices = current_idx_within_indices + 1

    # Clear chat history for next question
    cursor.execute(
        "UPDATE sessions SET current_question=?, answers=?, scores=?, chat_history='[]' WHERE id=?",
        (next_idx_within_indices, json.dumps(answers), json.dumps(scores), session_id),
    )
    conn.commit()
    conn.close()

    # ── Response ──────────────────────────────────────────────────────────────
    if next_idx_within_indices >= len(indices):
        final_score = round(sum(scores) / len(scores), 1)
        return {
            "done": True,
            "final_score": final_score,
            "result": result,
        }

    next_actual_q_index = indices[next_idx_within_indices]
    return {
        "done": False,
        "result": result,
        "next_question": _safe_question(QUESTIONS[next_actual_q_index], name=session["student_name"]),
        "progress": {"current": next_idx_within_indices, "total": len(indices)},
    }


@router.get("/session/{session_id}")
def get_session(session_id: str):
    """Retrieve full session details including all answers and scores so far."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    session = cursor.fetchone()
    conn.close()

    if not session:
        return {"error": "Session not found"}

    return {
        "session_id": session_id,
        "current_question": session["current_question"],
        "total": len(QUESTIONS),
        "answers": json.loads(session["answers"]),
        "scores": json.loads(session["scores"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_question(q: dict, name: str = "") -> dict:
    """Strip answer keys and personalize if needed."""
    q_copy = {k: v for k, v in q.items() if k not in ("answer", "correct_version")}
    
    if q_copy.get("type") == "conversational_speech" and name:
        msg = f"Hi {name}! I'm Sam. How are you doing today? How was your day?"
        q_copy["question"] = msg
        q_copy["audio_script"] = msg
        
    return q_copy
