import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv

# Load from .env if present
load_dotenv()

# Securely retrieve API KEY from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


model = genai.GenerativeModel("gemini-2.5-flash")


def _safe_parse(text: str, fallback: dict) -> dict:
    """JSON parse with block stripping and robustness."""
    try:
        # Try to find JSON block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
             return json.loads(match.group(1))
        
        # Try to find generic code block
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
             return json.loads(match.group(1))
        
        # Try to parse the text directly (perhaps AI didn't use blocks)
        try:
            return json.loads(text.strip())
        except:
            # Last ditch effort: find anything between curly braces
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise Exception("No JSON found")

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


def evaluate_open_text(question: str, answer: str, context: str = None) -> dict:
    """
    Evaluates a written creative / open-ended answer.
    Returns: { language_score: 0-100, feedback: str }
    """
    context_note = f"\nAdditional Context (e.g. image they are describing): {context}" if context else ""
    
    prompt = f"""
You are a friendly English tutor evaluating a Class 7 student's written response.

Question: {question}{context_note}
Student wrote: {answer}

Score the response on:
- language_score (0-100): grammar, vocabulary, sentence formation
- Relevance to the question/context.
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
    Evaluates a grammatical rewrite task.
    Returns: { score, is_correct, feedback }
    """
    prompt = f"""
You are a friendly English tutor evaluating a Class 7 student.
Task: The student had to rewrite a grammatically incorrect sentence correctly.

Original sentence (errors): {original}
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
    history: list of {"role": "user"|"model", "parts": [{"text": str}]}
    Returns: {"response": str, "is_finished": bool}
    """
    prompt = f"""
You are Sam, a friendly and warm AI tutor for kids (age 12). 
You are conducting a conversational English Speaking assessment.
The student's name is {student_name}.

Conversation history:
{json.dumps(history, indent=2)}

Task:
1. Respond naturally and briefly to the student's last message.
2. If this is the 1st or 2nd turn, ask one more engaging follow-up question.
3. If this is the 3rd turn (total 3 user messages), end the conversation politely.
4. Keep your response short and sweet (max 30 words).

Respond ONLY with valid JSON:
{{
  "response": "<Your response here>",
  "is_finished": <true if this was the 3rd user turn, else false>
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"response": "Nice talking to you! Let's move on.", "is_finished": True})


def evaluate_listening_conversation(history: list) -> dict:
    """
    Evaluates a full multi-turn conversation.
    Returns composite scores and feedback.
    """
    prompt = f"""
You are an English evaluator. Review this spoken conversation between a 12-year-old student and an AI tutor.

Conversation history:
{json.dumps(history, indent=2)}

Respond ONLY with valid JSON:
{{
  "overall_score": <0-100>,
  "language_score": <0-100>,
  "relevance_score": <0-100>,
  "feedback": "<one short constructive sentence max 20 words>"
}}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"overall_score": 70, "language_score": 70, "relevance_score": 70, "feedback": "Good effort!"})


# ── Conversational Writing ────────────────────────────────────────────────────

def generate_writing_chat_response(history: list, image_description: str = None) -> dict:
    """
    Generates the next AI response in a conversational writing assessment.
    Returns: {"response": str, "is_finished": bool}
    """
    image_description_note = f"\nThe image being discussed shows: {image_description}" if image_description else ""
    
    prompt = f"""
You are Quto, a friendly and observant AI tutor for kids (age 12). 
You are conducting a writing assessment about an image.
{image_description_note}

Rules for your response:
1. React warmly and naturally to the student's last message.
2. **Gently Correct**: If the student made a spelling or grammar mistake (e.g., "ballon" instead of "balloon"), correct it naturally in your response without being harsh. For example: "That's a great sentence! Yes, the red balloon (with two 'o's!) is very bright."
3. **Appreciate**: If they described something accurately, celebrate it!
4. **Follow-up**: If they haven't finished the task (usually after the 1st response), ask ONE simple follow-up question about the image details (e.g., the weather, the color of the balloon, the house, or the trees).
5. Keep your response short (15-30 words).
6. Use 1 emoji.

Ending rules:
- Count the number of 'user' messages in the 'Conversation history' above.
- If there is ONLY 1 'user' message, you MUST set 'is_finished' to false and ask a follow-up question.
- If there are 2 or more 'user' messages, set 'is_finished' to true and say a sweet goodbye.
- You must be VERY strict about this count.

Conversation history:
{json.dumps(history, indent=2)}

Respond ONLY with valid JSON:
{{
  "response": "<Your response here>",
  "is_finished": <true or false>
}}
"""
    res = model.generate_content(prompt)
    fallback = {"response": "That sounds great! Keep writing! ✍️", "is_finished": False}
    return _safe_parse(res.text, fallback)


def evaluate_writing_conversation(history: list, image_description: str = None) -> dict:
    """
    Final evaluation of a writing conversation.
    """
    image_note = f"\nThe image shows: {image_description}" if image_description else ""
    
    prompt = f"""
You are Quto, a friendly and encouraging AI tutor for kids (age 12). 
Review this writing conversation about an image.
{image_note}

Evaluate:
1. Did the student describe the image accurately?
2. Grammar, punctuation (like capitalizing 'I' and full stops), and vocabulary.
3. Sentence structure for a Class 7 student.

Respond ONLY with valid JSON:
{{
  "language_score": <0-100>,
  "relevance_score": <0-100>,
  "feedback": "A very warm, encouraging sentence for a 12-year-old student from Quto the AI tutor. Praise their effort and give one small, friendly tip for next time.",
  "overall_score": <0-100>
}}

Conversation history:
{json.dumps(history, indent=2)}
"""
    res = model.generate_content(prompt)
    return _safe_parse(res.text, {"language_score": 70, "relevance_score": 70, "feedback": "Nice job describing the sketch!", "overall_score": 70})
