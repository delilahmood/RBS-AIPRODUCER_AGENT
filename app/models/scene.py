from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, DateTime, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Scene(Base):
    __tablename__ = "scenes"
    
    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)  # décor de cette scène
    character_ids = Column(JSON, nullable=True)  # liste des IDs personnages présents dans le plan
    number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    camera_movement = Column(String, nullable=True)
    mood = Column(String, nullable=True)
    dialogue = Column(Text, nullable=True)
    storyboard_prompts = Column(JSON, nullable=True)
    video_url = Column(String, nullable=True)
    status = Column(String, default="draft")
    
    # NOUVEAUX CHAMPS POUR LE SHORT DRAMA
    duration_seconds = Column(Float, default=10.0)  # Durée précise de la scène (ex: 12.5s)
    video_prompt = Column(Text, nullable=True)  # Prompt spécifique pour Wan/HappyHorse (différent du storyboard)
    is_cliffhanger = Column(Boolean, default=False)  # True si c'est la scène finale d'un pilote
    cliffhanger_description = Column(Text, nullable=True)  # Description du cliffhanger
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    episode = relationship("Episode", back_populates="scenes")
    assets = relationship("SceneAsset", back_populates="scene", cascade="all, delete-orphan")