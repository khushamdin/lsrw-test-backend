import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# Load from .env if present
load_dotenv()

# Securely retrieve API KEY from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


model = genai.GenerativeModel("gemini-2.5-flash")


def _safe_parse(text: str, fallback: dict) -> dict:
    """Strip markdown fences and parse JSON, returning fallback on failure."""
    try:
        clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return fallback
def generate_speaking_guide_message(
    question: str,
    task: str,
    hint: str = "",
    forbidden_words: list = None,
    previous_spoken: str = None,
    previous_feedback: str = None,
) -> str:
    """
    Generates a short, warm, conversational guide message for the current
    speaking step. Called BEFORE the student records.
 
    task:
      "line1"   → introduce the question, ask for first sentence
      "line2"   → react to what they said, ask for second sentence
      "combine" → react to both lines, ask them to say the full answer together
 
    Returns a plain string (1-3 sentences max). No JSON.
    """
    forbidden_note = (
        f"Remind them they cannot use the words: {forbidden_words}. "
        if forbidden_words else ""
    )
 
    previous_context = ""
    if previous_spoken:
        previous_context += f'\nThe student just said: "{previous_spoken}"'
    if previous_feedback:
        previous_context += f'\nYour last feedback to them was: "{previous_feedback}"'
 
    task_instruction = {
        "line1": (
            "Introduce the speaking task warmly. Ask the student to say just ONE sentence "
            "in response to the question. Keep it encouraging and low-pressure."
        ),
        "line2": (
            "React naturally to what the student just said (refer to it briefly). "
            "Then ask them to add ONE more sentence — a detail, reason, or what happens next. "
            "Be warm and specific to what they said."
        ),
        "combine": (
            "Celebrate that they've said both parts. Now ask them to say BOTH sentences "
            "together as one smooth, flowing answer. Be encouraging and specific — "
            "maybe mention something good from their previous attempts."
        ),
    }.get(task, "Ask the student to speak one sentence.")
 
    prompt = f"""You are a friendly, encouraging English tutor for a Class 7 student (age 12-13).
You are guiding them through a speaking exercise in a chat-style conversation.
 
Speaking question: {question}
Current step: {task}
Hint available for student: {hint}
{forbidden_note}{previous_context}
 
Your job now: {task_instruction}
 
Rules:
- Write ONLY the message you'd send to the student. No labels, no JSON, no quotes around it.
- Max 2-3 sentences. Be natural, warm, conversational — like a cool tutor, not a robot.
- Use 1 emoji max. Do not be over-the-top enthusiastic.
- If task is "line2" or "combine", specifically reference what they said before.
- Do NOT include the hint text verbatim — just guide them naturally.
"""
 
    res = model.generate_content(prompt)
    return res.text.strip()

# ── Used for `speech` questions ───────────────────────────────────────────────
def evaluate_speech_answer(question: str, spoken: str, accuracy: float, fluency: float,
                            forbidden_words: list = None) -> dict:
    """
    Evaluates a spoken free-form answer.
    Returns: { language_score, relevance_score, feedback, corrected_sentence }
    """
    forbidden_note = ""
    if forbidden_words:
        forbidden_note = (
            f"\nIMPORTANT: The student must NOT use these words: {forbidden_words}. "
            "Deduct 20 points from language_score if any forbidden word is used."
        )
 
    pron_note = f"\nAzure Pronunciation Accuracy: {accuracy:.1f}/100" if accuracy > 0 else ""
    fluency_note = f"\nAzure Fluency Score: {fluency:.1f}/100" if fluency > 0 else ""
 
    prompt = f"""
You are a friendly English tutor evaluating a Class 7 student's spoken response.
 
Question: {question}
Student said: {spoken}{pron_note}{fluency_note}{forbidden_note}
 
Evaluate on:
1. language_score (0-100): grammar, vocabulary, sentence structure
2. relevance_score (0-100): does the answer address the question?
3. feedback: one encouraging sentence for a 12-year-old (max 15 words)
4. corrected_sentence: a clean, corrected version of what they said
   (if already correct, repeat it as-is)
 
Respond ONLY with valid JSON (no markdown):
{{
  "language_score": <number>,
  "relevance_score": <number>,
  "feedback": "<short encouraging sentence>",
  "corrected_sentence": "<corrected version of their sentence>"
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {
        "language_score": 50,
        "relevance_score": 50,
        "feedback": "Good try!",
        "corrected_sentence": spoken,
    })


# ── Used for `open_text` questions ────────────────────────────────────────────
def evaluate_open_text(question: str, answer: str) -> dict:
    """
    Evaluates a written creative / open-ended answer.
    Returns: { language_score: 0-100, feedback: str }
    """
    prompt = f"""
You are a friendly English tutor evaluating a Class 7 student's written response.

Question: {question}
Student wrote: {answer}

Score the response on:
- language_score (0-100): grammar, vocabulary, sentence formation
- Creativity and relevance don't need to be penalised harshly for a kid.

Respond ONLY with valid JSON (no markdown):
{{
  "language_score": <number>,
  "feedback": "<one encouraging sentence for a kid, max 15 words>"
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"language_score": 50, "feedback": "Good effort!"})


# ── Used for `rewrite` questions ──────────────────────────────────────────────
def evaluate_rewrite(original: str, correct_version: str, student_answer: str) -> dict:
    """
    Checks if the student correctly rewrote a sentence.
    Returns: { score: 0-100, is_correct: bool, feedback: str }
    """
    prompt = f"""
You are an English grammar checker for Class 7 students.

Original (incorrect) sentence: {original}
Expected correction: {correct_version}
Student's rewrite: {student_answer}

Check if the student fixed the grammatical error(s). Minor spelling variations are acceptable.

Respond ONLY with valid JSON (no markdown):
{{
  "score": <0, 50, or 100>,
  "is_correct": <true or false>,
  "feedback": "<one friendly sentence, max 15 words>"
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"score": 50, "is_correct": False, "feedback": "Nice try, check the verb tense!"})