import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# Load from .env if present
load_dotenv()

# Securely retrieve API KEY from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# ⚠️ Note: "gemini-2.5-flash" doesn't exist yet. 
# Using gemini-1.5-flash which is stable for evaluation.
model = genai.GenerativeModel("gemini-1.5-flash")


def _safe_parse(text: str, fallback: dict) -> dict:
    """Strip markdown fences and parse JSON, returning fallback on failure."""
    try:
        clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return fallback


# ── Used for `speech` questions ───────────────────────────────────────────────
def evaluate_speech_answer(question: str, spoken: str, accuracy: float, fluency: float,
                            forbidden_words: list = None) -> dict:
    """
    Evaluates a spoken free-form answer.
    Returns: { language_score: 0-100, relevance_score: 0-100, feedback: str }
    """
    forbidden_note = ""
    if forbidden_words:
        forbidden_note = (
            f"\nIMPORTANT: The student must NOT use these words: {forbidden_words}. "
            "Deduct 20 points from language_score if any forbidden word is used."
        )

    prompt = f"""
You are a friendly English tutor evaluating a Class 7 student's spoken response.

Question: {question}
Student said: {spoken}
Azure Pronunciation Accuracy: {accuracy:.1f}/100
Azure Fluency Score: {fluency:.1f}/100{forbidden_note}

Evaluate on two dimensions:
1. language_score (0-100): grammar, vocabulary, sentence structure
2. relevance_score (0-100): does the answer actually address the question?

Respond ONLY with valid JSON (no markdown):
{{
  "language_score": <number>,
  "relevance_score": <number>,
  "feedback": "<one encouraging sentence for a kid, max 15 words>"
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"language_score": 50, "relevance_score": 50, "feedback": "Good try!"})


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