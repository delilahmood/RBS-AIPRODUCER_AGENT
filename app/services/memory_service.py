from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.memory import ProjectMemory, ChatSession

class MemoryService:
    def __init__(self):
        self.db = SessionLocal()
    
    async def save_session_summary(
        self,
        project_id: Optional[int],
        user_id: int,
        summary: str,
        key_decisions: List[str],
        last_messages: List[Dict],
        context_type: str
    ) -> ChatSession:
        """Save a summarized chat session"""
        session = ChatSession(
            project_id=project_id,
            user_id=user_id,
            session_summary=summary,
            key_decisions=key_decisions,
            last_messages=last_messages[-10:],  # Keep only last 10 messages
            context_type=context_type
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    async def get_project_context(self, project_id: int) -> Dict[str, Any]:
        """Get project memory and context"""
        memory = self.db.query(ProjectMemory).filter(
            ProjectMemory.project_id == project_id
        ).first()
        
        if not memory:
            memory = ProjectMemory(
                project_id=project_id,
                decisions={},
                style_preferences={},
                character_notes={}
            )
            self.db.add(memory)
            self.db.commit()
        
        return {
            "decisions": memory.decisions or {},
            "style_preferences": memory.style_preferences or {},
            "character_notes": memory.character_notes or {},
            "world_building": memory.world_building or {}
        }
    
    async def update_project_memory(
        self,
        project_id: int,
        decisions: Optional[Dict] = None,
        style_preferences: Optional[Dict] = None,
        character_notes: Optional[Dict] = None,
        world_building: Optional[Dict] = None
    ) -> ProjectMemory:
        """Update project memory"""
        memory = self.db.query(ProjectMemory).filter(
            ProjectMemory.project_id == project_id
        ).first()
        
        if not memory:
            memory = ProjectMemory(project_id=project_id)
            self.db.add(memory)
        
        if decisions:
            memory.decisions = decisions
        if style_preferences:
            memory.style_preferences = style_preferences
        if character_notes:
            memory.character_notes = character_notes
        if world_building:
            memory.world_building = world_building
        
        self.db.commit()
        self.db.refresh(memory)
        
        return memory
    
    async def get_recent_sessions(
        self,
        project_id: Optional[int] = None,
        limit: int = 5
    ) -> List[ChatSession]:
        """Get recent chat sessions"""
        query = self.db.query(ChatSession)
        
        if project_id:
            query = query.filter(ChatSession.project_id == project_id)
        
        sessions = query.order_by(ChatSession.created_at.desc()).limit(limit).all()
        return sessions
    
    def close(self):
        """Close database session"""
        self.db.close()