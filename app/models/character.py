from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Character(Base):
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, index=True, nullable=False)
    alias = Column(String, nullable=True)
    role = Column(String, nullable=False)  # protagonist, antagonist, supporting
    age = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    traits = Column(JSON, nullable=True)
    reference_images = Column(JSON, nullable=True)
    is_agent = Column(Boolean, default=False)
    agent_public_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # NOUVEAUX CHAMPS POUR LE SHORT DRAMA
    objective = Column(Text, nullable=True) # Ce qu'il veut immédiatement
    visual_trait = Column(Text, nullable=True) # Détail fort repérable en 2s
    secret = Column(Text, nullable=True) # Ce qu'il cache
    has_secret = Column(Boolean, default=False)
    arc_potential = Column(Text, nullable=True) # Potentiel pour la saison 2
    
    
    # Relationships
    project = relationship("Project", back_populates="characters")
    relations = relationship("CharacterRelation", back_populates="character", cascade="all, delete-orphan", foreign_keys="CharacterRelation.character_id")
    assets = relationship("CharacterAsset", back_populates="character", cascade="all, delete-orphan")

class CharacterRelation(Base):
    __tablename__ = "character_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    related_character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    relation_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    character = relationship("Character", back_populates="relations", foreign_keys=[character_id])
    related_character = relationship("Character", foreign_keys=[related_character_id])