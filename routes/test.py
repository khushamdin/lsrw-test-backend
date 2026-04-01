from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional, List
import uuid
import json
import shutil
import os

from db import get_db
from questions.class_7 import QUESTIONS
from services.evaluation_service import evaluate

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
def start(section: Optional[str] = None):
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
        "INSERT INTO sessions (id, current_question, answers, scores, question_indices) VALUES (?, ?, ?, ?, ?)",
        (session_id, 0, "[]", "[]", indices_json),
    )
    conn.commit()
    conn.close()

    first_q = _safe_question(QUESTIONS[indices[0]])
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

    if qtype == "speech":
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
        # mcq, tap_wrong_word, sentence_build, open_text, rewrite
        result = evaluate(question, answer or "")

    # ── Persist ───────────────────────────────────────────────────────────────
    answers.append(result)
    scores.append(result["score"])
    next_idx_within_indices = current_idx_within_indices + 1

    cursor.execute(
        "UPDATE sessions SET current_question=?, answers=?, scores=? WHERE id=?",
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
        "next_question": _safe_question(QUESTIONS[next_actual_q_index]),
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

def _safe_question(q: dict) -> dict:
    """Strip answer keys before sending to frontend."""
    return {k: v for k, v in q.items() if k not in ("answer", "correct_version")}