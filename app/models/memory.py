from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON, Text, String
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ProjectMemory(Base):
    __tablename__ = "project_memories"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), unique=True, nullable=False)
    decisions = Column(JSON, nullable=True)  # Key narrative decisions
    style_preferences = Column(JSON, nullable=True)  # Visual and narrative style preferences
    character_notes = Column(JSON, nullable=True)  # Notes about characters
    world_building = Column(JSON, nullable=True)  # World/lore information
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="memory")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_summary = Column(Text, nullable=False)  # Summary of the session
    key_decisions = Column(JSON, nullable=True)  # Important decisions made in this session
    last_messages = Column(JSON, nullable=True)  # Last 5-10 messages for context
    context_type = Column(String, nullable=False)  # dashboard, project, characters, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")