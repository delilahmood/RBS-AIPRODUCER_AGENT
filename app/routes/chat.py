from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.memory import ChatSession
from app.schemas.chat import ChatMessage, ChatResponse
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.services.context_service import ContextService

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/send", response_model=ChatResponse)
async def send_message(
    message: ChatMessage, 
    db: Session = Depends(get_db)
):
    # Get context-specific system prompt
    system_prompt = ContextService.get_system_prompt(
        context_type=message.context_type,
        project_id=message.project_id
    )
    
    # Call AI service
    ai_service = AIService()
    response = await ai_service.chat(
        system_prompt=system_prompt,
        user_message=message.message,
        model="qwen-plus"
    )
    
    # Save session (summary only, not all messages)
    memory_service = MemoryService()
    await memory_service.save_session_summary(
        project_id=message.project_id,
        user_id=1,  # TODO: Get from authenticated user
        summary=f"User asked about: {message.message[:100]}",
        key_decisions=[],
        last_messages=[{"role": "user", "content": message.message}],
        context_type=message.context_type
    )
    
    return ChatResponse(
        response=response,
        session_summary=None
    )

@router.get("/session/{session_id}")
async def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session