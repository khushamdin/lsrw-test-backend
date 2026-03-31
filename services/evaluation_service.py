"""
Evaluation router — maps each question type to the correct scoring strategy.

Question types and their scoring logic:
  mcq            → exact string match                              → score 0 or 100
  tap_wrong_word → exact string match on the tapped word           → score 0 or 100
  fill_blank     → case-insensitive match for each blank           → score 0-100 (proportional)
  sentence_build → compare assembled sentence to answer string     → score 0 or 100
  rewrite        → Gemini grammar checker                          → score 0-100
  open_text      → Gemini language quality scorer                  → score 0-100
  speech         → Azure pronunciation (accuracy + fluency)
                   + Gemini relevance & language quality           → composite 0-100
"""

from services.azure_service import analyze_pronunciation, parse_result
from services.gemini_service import (
    evaluate_speech_answer,
    evaluate_open_text,
    evaluate_rewrite,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase + strip for case-insensitive comparison."""
    return s.strip().lower()


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(question: dict, input_data) -> dict:
    """
    Args:
        question  – a question dict from QUESTIONS
        input_data – varies by type:
            mcq / tap_wrong_word → str   (selected option or tapped word)
            fill_blank           → list  (list of strings, one per blank)
            sentence_build       → str   (the assembled sentence)
            rewrite / open_text  → str   (typed answer)
            speech               → str   (file path to the audio file)

    Returns a dict always containing at least: { score, feedback }
    """

    qtype = question["type"]

    # ── MCQ ───────────────────────────────────────────────────────────────────
    if qtype == "mcq":
        correct = question["answer"]
        is_correct = _norm(input_data) == _norm(correct)
        return {
            "score": 100 if is_correct else 0,
            "is_correct": is_correct,
            "feedback": "Correct! 🎉" if is_correct else question.get("feedback_wrong", "Not quite!"),
        }

    # ── TAP WRONG WORD ────────────────────────────────────────────────────────
    elif qtype == "tap_wrong_word":
        correct = question["answer"]
        is_correct = _norm(input_data) == _norm(correct)
        return {
            "score": 100 if is_correct else 0,
            "is_correct": is_correct,
            "feedback": "You found the wrong word! ✅" if is_correct else question.get("feedback_wrong", "Not that word!"),
        }

    # ── FILL IN THE BLANK(S) ──────────────────────────────────────────────────
    elif qtype == "fill_blank":
        # input_data should be a list of strings, one per blank
        if isinstance(input_data, str):
            input_data = [input_data]

        expected = question["answer"]  # list of strings
        correct_count = sum(
            1 for given, exp in zip(input_data, expected)
            if _norm(given) == _norm(exp)
        )
        total = len(expected)
        score = round((correct_count / total) * 100) if total else 0
        is_correct = correct_count == total

        return {
            "score": score,
            "is_correct": is_correct,
            "correct_count": correct_count,
            "total_blanks": total,
            "feedback": "All blanks correct! 🎉" if is_correct else question.get("feedback_wrong", "Check your answers!"),
        }

    # ── SENTENCE BUILD ────────────────────────────────────────────────────────
    elif qtype == "sentence_build":
        correct = question["answer"]
        is_correct = _norm(input_data) == _norm(correct)
        return {
            "score": 100 if is_correct else 0,
            "is_correct": is_correct,
            "feedback": "Perfect order! 📜" if is_correct else question.get("feedback_wrong", "Try rearranging the words!"),
        }

    # ── REWRITE ───────────────────────────────────────────────────────────────
    elif qtype == "rewrite":
        gemini = evaluate_rewrite(
            original=question["question"],
            correct_version=question["correct_version"],
            student_answer=input_data,
        )
        return {
            "score": gemini["score"],
            "is_correct": gemini.get("is_correct", False),
            "feedback": gemini["feedback"],
        }

    # ── OPEN TEXT ─────────────────────────────────────────────────────────────
    elif qtype == "open_text":
        gemini = evaluate_open_text(question["question"], input_data)
        return {
            "score": gemini["language_score"],
            "feedback": gemini["feedback"],
        }

    # ── SPEECH ────────────────────────────────────────────────────────────────
    elif qtype == "speech":
        audio_path = input_data

        # Step 1: Azure pronunciation analysis
        azure_raw = analyze_pronunciation(audio_path, reference_text="")
        parsed = parse_result(azure_raw)

        spoken = parsed["spoken"]
        accuracy = parsed["accuracy"]
        fluency = parsed["fluency"]

        # Step 2: Gemini relevance + language quality check
        forbidden = question.get("forbidden_words", None)
        gemini = evaluate_speech_answer(
            question=question["question"],
            spoken=spoken,
            accuracy=accuracy,
            fluency=fluency,
            forbidden_words=forbidden,
        )

        # Step 3: Composite score
        # 40% pronunciation accuracy, 20% fluency, 25% language quality, 15% relevance
        composite = (
            0.40 * accuracy
            + 0.20 * fluency
            + 0.25 * gemini["language_score"]
            + 0.15 * gemini["relevance_score"]
        )

        return {
            "score": round(composite, 1),
            "spoken": spoken,
            "pronunciation_accuracy": round(accuracy, 1),
            "fluency": round(fluency, 1),
            "language_score": gemini["language_score"],
            "relevance_score": gemini["relevance_score"],
            "feedback": gemini["feedback"],
        }

    # ── UNKNOWN TYPE ──────────────────────────────────────────────────────────
    else:
        return {
            "score": 0,
            "feedback": f"Unknown question type: {qtype}",
        }