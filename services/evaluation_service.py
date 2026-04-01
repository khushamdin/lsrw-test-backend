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
  conversational_writing → Turn-based writing conversation with AI feedback
"""

from services.azure_service import analyze_pronunciation, parse_result, transcribe_only
from services.gemini_service import (
    evaluate_speech_answer,
    evaluate_open_text,
    evaluate_rewrite,
    generate_writing_chat_response,
    evaluate_writing_conversation,
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

def evaluate(question: dict, input_data, conversation_history=None) -> dict:
    """
    Args:
        question  – a question dict from QUESTIONS
        input_data – varies by type:
            mcq / tap_wrong_word → str   (selected option or tapped word)
            fill_blank           → list  (list of strings, one per blank)
            sentence_build       → str   (the assembled sentence)
            rewrite / open_text  → str   (typed answer)
            speech               → str   (file path to the audio file)
            conversational_writing → str (typed message in conversation)
        conversation_history – list of chat turns for conversational types

    Returns a dict always containing at least: { score, feedback }
    For conversational types, may also return: { is_turn_based, chat_response, is_finished }
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
        gemini = evaluate_open_text(
            question["question"], 
            input_data, 
            context=question.get("image_description")
        )
        return {
            "score": gemini["language_score"],
            "feedback": gemini["feedback"],
        }

    # ── CONVERSATIONAL WRITING ────────────────────────────────────────────────
    elif qtype == "conversational_writing":
        """
        Turn-based writing conversation:
        1. Student writes a response
        2. AI gives gentle feedback + follow-up question
        3. After 2 turns, evaluate and finish
        """
        if conversation_history is None:
            conversation_history = []
        
        # Add student's message to history
        conversation_history.append({
            "role": "user",
            "parts": [{"text": input_data}]
        })
        
        # Generate AI response with feedback and follow-up
        ai_response = generate_writing_chat_response(
            history=conversation_history,
            image_description=question.get("image_description")
        )
        
        # Add AI response to history
        conversation_history.append({
            "role": "model",
            "parts": [{"text": ai_response["response"]}]
        })
        
        # If conversation is finished, evaluate it
        if ai_response.get("is_finished"):
            final_eval = evaluate_writing_conversation(
                history=conversation_history,
                image_description=question.get("image_description")
            )
            return {
                "score": final_eval["overall_score"],
                "feedback": final_eval["feedback"],
                "language_score": final_eval["language_score"],
                "relevance_score": final_eval["relevance_score"],
                "conversation_history": conversation_history,
            }
        else:
            # Mid-conversation: return the AI's response for display
            return {
                "score": 0,  # No score yet
                "is_turn_based": True,
                "chat_response": ai_response["response"],
                "is_finished": False,
                "conversation_history": conversation_history,
            }

    # ── SPEECH ────────────────────────────────────────────────────────────────
    elif qtype == "speech":
        audio_path = input_data

        # Step 1: Transcribe FIRST (STT) for relevance check (per user request)
        spoken = transcribe_only(audio_path)
        if not spoken:
            return {
                "score": 0,
                "spoken": "[Silence or unreadable]",
                "feedback": "I couldn't hear you clearly. Could you try speaking again?",
            }

        # Step 2: Gemini Relevance + Language Check
        forbidden = question.get("forbidden_words", None)
        gemini = evaluate_speech_answer(
            question=question["question"],
            spoken=spoken,
            accuracy=0.0,  # Placeholder, will update if relevant
            fluency=0.0,   # Placeholder
            forbidden_words=forbidden,
        )

        relevance = gemini.get("relevance_score", 0)
        
        # Threshold: If it's not relevant (e.g. saying 'happy birthday' to beach question),
        # don't bother with Azure pronunciation, just penalize.
        if relevance < 40:
             return {
                "score": round(relevance * 0.5, 1),
                "spoken": spoken,
                "relevance_score": relevance,
                "feedback": gemini["feedback"] + " (Wait, that doesn't seem to answer my question! 🤔)",
                "is_irrelevant": True
            }

        # Step 3: Azure Pronunciation Analysis (Full)
        # Using the corrected text from Gemini as reference for MUCH better accuracy
        reference = gemini.get("corrected_sentence", spoken)
        azure_raw = analyze_pronunciation(audio_path, reference_text=reference)
        parsed = parse_result(azure_raw)

        accuracy = parsed["accuracy"]
        fluency = parsed["fluency"]

        # Step 4: Composite Score
        # Now 50% is pronunciation, 50% is content (language + relevance)
        composite = (
            0.30 * accuracy
            + 0.20 * fluency
            + 0.25 * gemini["language_score"]
            + 0.25 * relevance
        )

        return {
            "score": round(composite, 1),
            "spoken": spoken,
            "pronunciation_accuracy": round(accuracy, 1),
            "fluency": round(fluency, 1),
            "language_score": gemini["language_score"],
            "relevance_score": relevance,
            "feedback": gemini["feedback"],
            "corrected_sentence": gemini.get("corrected_sentence", spoken)
        }

    # ── UNKNOWN TYPE ──────────────────────────────────────────────────────────
    else:
        return {
            "score": 0,
            "feedback": f"Unknown question type: {qtype}",
        }