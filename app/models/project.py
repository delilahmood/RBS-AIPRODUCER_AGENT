from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, index=True, nullable=False)
    
    # Type et Format
    type = Column(String, nullable=False)  # "series" or "film"
    project_format = Column(String, default="one_shot")  # "one_shot" ou "serie"
    is_pilot = Column(Boolean, default=False)
    
    # Genres et Styles
    genres = Column(JSON, nullable=True)
    visual_styles = Column(JSON, nullable=True)
    tone = Column(String, nullable=True)
    narrative_style = Column(String, nullable=True)  # NOUVEAU: Dark, Romance, etc.
    
    # Idée originale
    idea = Column(Text, nullable=True)  # NOUVEAU: L'idée de base
    
    # Images de référence
    reference_image_world = Column(String, nullable=True)  # NOUVEAU: URL image monde
    reference_image_character = Column(String, nullable=True)  # NOUVEAU: URL image perso
    extracted_style_prompt = Column(Text, nullable=True)  # conservé pour compat, plus rempli automatiquement
    world_style_prompt = Column(Text, nullable=True)      # style extrait de l'image World
    character_style_prompt = Column(Text, nullable=True)  # style extrait de l'image Character
    
    # Progression de génération
    generation_progress = Column(JSON, nullable=True)  # NOUVEAU: {"synopsis": "done", "casting": "running"}
    
    # Durée
    duration_seconds = Column(Integer, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Format vidéo (16:9 pour Short Movie, 9:16 pour Short Drama par défaut)
    aspect_ratio = Column(String, default="16:9")
    
    # Narration
    synopsis = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    cliffhanger = Column(Text, nullable=True)
    
    # Note Marketing
    production_note = Column(JSON, nullable=True)
    
    # Structure
    seasons = Column(Integer, nullable=True)
    episodes_per_season = Column(Integer, nullable=True)
    status = Column(String, default="draft")  # draft, generating, partial, ready, completed
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    memory = relationship("ProjectMemory", back_populates="project", uselist=False, cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="project", cascade="all, delete-orphan")
    project_assets = relationship("ProjectAsset", back_populates="project", cascade="all, delete-orphan")
    skill_executions = relationship("SkillExecution", back_populates="project", cascade="all, delete-orphan")


