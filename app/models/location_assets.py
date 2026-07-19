from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class LocationAsset(Base):
    __tablename__ = "location_assets"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    asset_type = Column(String, nullable=False, default="reference")  # 'reference'

    file_url = Column(String, nullable=False)  # URL permanente (static/assets/locations/...)

    prompt_used = Column(Text, nullable=True)
    model_used = Column(String, nullable=True)  # ex: 'wan2.2-t2i-plus', ou 'user_upload'
    seed = Column(Integer, nullable=True)

    version = Column(Integer, default=1)
    generation_batch = Column(Integer, default=1)
    is_selected = Column(Boolean, default=False)
    status = Column(String, default="completed")  # 'pending', 'completed', 'failed'

    created_at = Column(DateTime, default=datetime.utcnow)

    location = relationship("Location", back_populates="assets")
