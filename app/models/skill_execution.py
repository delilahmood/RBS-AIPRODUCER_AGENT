from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class SkillExecution(Base):
    __tablename__ = "skill_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Nom du skill : 'story_architect', 'visual_director', 'video_producer'
    skill_name = Column(String, nullable=False) 
    
    # État : 'pending', 'running', 'completed', 'failed'
    status = Column(String, default="pending") 
    
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    # Logs pour l'UI (ex: "Génération de Kairo Ash...")
    logs = Column(Text, nullable=True) 
    
    # Résultat JSON (optionnel, pour stocker les IDs des assets créés)
    result_data = Column(Text, nullable=True)

    project = relationship("Project", back_populates="skill_executions")

