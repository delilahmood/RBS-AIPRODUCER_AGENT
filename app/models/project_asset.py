from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ProjectAsset(Base):
    __tablename__ = "project_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    asset_type = Column(String, nullable=False)  # poster, trailer, final_video
    file_url = Column(String, nullable=False)
    prompt_used = Column(Text, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="project_assets")