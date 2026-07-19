from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class CharacterAsset(Base):
    __tablename__ = "character_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    
    # Type d'asset : 'portrait', 'reference_sheet', 'video_clip'
    asset_type = Column(String, nullable=False) 
    
    # Lien image — TOUJOURS une URL permanente (static/assets/characters/...),
    # jamais un lien DashScope brut (qui expire sous 24h).
    file_url = Column(String, nullable=False) 
    
    # Métadonnées IA
    prompt_used = Column(Text, nullable=True)
    model_used = Column(String, nullable=True) # ex: 'wan2.2-t2i-plus', ou 'user_upload'
    seed = Column(Integer, nullable=True) # Pour reproduire l'image si besoin
    
    # Versioning (Règle n°14 du Spec)
    version = Column(Integer, default=1)
    generation_batch = Column(Integer, default=1)  # incrémente à chaque régénération, préserve l'historique
    is_selected = Column(Boolean, default=False)    # image retenue comme fiche du personnage
    status = Column(String, default="completed") # 'pending', 'completed', 'failed'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relation avec le personnage
    character = relationship("Character", back_populates="assets")