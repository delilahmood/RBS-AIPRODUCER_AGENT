from pydantic import BaseModel
from typing import Optional, List

class ChatMessage(BaseModel):
    message: str
    project_id: Optional[int] = None
    context_type: str = "dashboard"  # dashboard, project, characters, etc.

class ChatResponse(BaseModel):
    response: str
    session_summary: Optional[str] = None

class SessionSummary(BaseModel):
    session_id: int
    project_id: Optional[int]
    summary: str
    key_decisions: Optional[List[str]] = None
    context_type: str
    created_at: str