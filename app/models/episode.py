from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Episode(Base):
    __tablename__ = "episodes"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    season = Column(Integer, nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    characters = Column(JSON, nullable=True)  # List of character IDs appearing in this episode
    status = Column(String, default="draft")  # draft, in_progress, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    script_content = Column(Text, nullable=True)
    
    # NOUVEAUX CHAMPS POUR LE SHORT DRAMA
    episode_number = Column(Integer, default=1)
    season_number = Column(Integer, default=1)
    ends_with_cliffhanger = Column(Boolean, default=False)
    cliffhanger_description = Column(Text, nullable=True)

    # Assemblage final de l'épisode — pas de version multiple nécessaire ici,
    # une seule vidéo finale à la fois (le cover, lui, a son propre historique
    # via EpisodeAsset, voir plus bas).
    assembled_video_url = Column(String, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="episodes")
    scenes = relationship("Scene", back_populates="episode", cascade="all, delete-orphan")
    assets = relationship("EpisodeAsset", back_populates="episode", cascade="all, delete-orphan")