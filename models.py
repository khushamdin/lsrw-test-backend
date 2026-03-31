from pydantic import BaseModel
from typing import List, Optional, Any


# -------------------------
# START TEST
# -------------------------

class StartResponse(BaseModel):
    session_id: str
    question: dict


# -------------------------
# ANSWER REQUEST
# -------------------------

class AnswerRequest(BaseModel):
    session_id: str
    answer: Optional[str] = None


# -------------------------
# EVALUATION RESULT
# -------------------------

class EvaluationResult(BaseModel):
    score: float
    feedback: str
    spoken: Optional[str] = None


# -------------------------
# NEXT QUESTION RESPONSE
# -------------------------

class NextQuestionResponse(BaseModel):
    done: bool
    next_question: Optional[dict] = None
    result: Optional[EvaluationResult] = None
    final_score: Optional[float] = None


# -------------------------
# SESSION (DB STRUCTURE)
# -------------------------

class SessionModel(BaseModel):
    id: str
    current_question: int
    answers: List[Any]
    scores: List[float]