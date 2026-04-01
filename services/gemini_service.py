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

# ── Conversational Listening ──────────────────────────────────────────────────

def generate_listening_chat_response(history: list, student_name: str = "there") -> dict:
    """
    Generates the next AI response in a conversational listening assessment.
    history: list of {"role": "user"|"model", "content": str}
    Returns: {"response": str, "is_finished": bool}
    """
    prompt = f"""
You are Sam, a friendly and warm AI tutor for kids (age 12). 
You are conducting a conversational English Speaking assessment.
The student's name is {student_name}.

Conversation history:
{json.dumps(history, indent=2)}

Rules for Sam's response:
1. React warmly and naturally to what the student said in the last interaction. 
2. If the kid was sad or had a bad day, show genuine empathy.
3. Then, bridge to a fun/engaging follow-up question.
4. Topics should be simple: favorite food, superpowers, hobbies, animals, movies, or cartoons.
5. Keep your response between 15-30 words.
6. Use 1 emoji. 

Ending the conversation:
- We want at least 3 high-quality turns (user answered 3 times).
- Count how many times the student (role: user) has spoken in the history above.
- If they have spoken 3 or 4 times, set 'is_finished' to true and say a sweet goodbye like "It was so wonderful chatting with you, {student_name}! Have a great day!".
- If they have spoken less than 3 times, keep the conversation going and set 'is_finished' to false.

Respond ONLY with valid JSON:
{{
  "response": "<Sam's response>",
  "is_finished": <true or false>
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"response": "That's great! Tell me, what is your favorite cartoon?", "is_finished": False})


def evaluate_listening_conversation(history: list) -> dict:
    """
    Final evaluation of the entire listening conversation.
    """
    prompt = f"""
You are a friendly English evaluator. Evaluate this conversation between a student and an AI tutor 'Sam'.
Look for:
1. Did the student understand Sam's questions?
2. Did they respond relevantly?
3. Grammar and vocabulary for a Class 7 student.
4. Provide constructive feedback on what they did well and ONE specific tip for improvement.

Conversation history:
{json.dumps(history, indent=2)}

Respond ONLY with valid JSON:
{{
  "language_score": <0-100>,
  "relevance_score": <0-100>,
  "feedback": "<constructive feedback for improvement, max 25 words>",
  "overall_score": <0-100>
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"language_score": 75, "relevance_score": 75, "feedback": "Great chatting with you! You did well.", "overall_score": 75})