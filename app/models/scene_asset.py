from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class SceneAsset(Base):
    __tablename__ = "scene_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    
    # Type : 'storyboard', 'image', 'video', 'audio'
    asset_type = Column(String, nullable=False) 
    
    file_url = Column(String, nullable=False) 
    
    # Métadonnées IA
    prompt_used = Column(Text, nullable=True)
    model_used = Column(String, nullable=True) # ex: 'wanx2.1-i2v-plus'
    seed = Column(Integer, nullable=True)
    
    # Spécifique Vidéo
    duration_seconds = Column(Float, nullable=True) # ex: 5.0
    
    # Versioning (même système que CharacterAsset/LocationAsset)
    version = Column(Integer, default=1)
    generation_batch = Column(Integer, default=1)
    is_selected = Column(Boolean, default=False)
    status = Column(String, default="completed")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relation avec la scène
    scene = relationship("Scene", back_populates="assets")