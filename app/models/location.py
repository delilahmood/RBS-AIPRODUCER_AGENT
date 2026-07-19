from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)      # description narrative du lieu
    mood = Column(String, nullable=True)            # ambiance/atmosphère
    key_visual_details = Column(Text, nullable=True)  # éléments visuels marquants (analogue à visual_trait)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="locations")
    assets = relationship("LocationAsset", back_populates="location", cascade="all, delete-orphan")
