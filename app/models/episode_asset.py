from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class EpisodeAsset(Base):
    __tablename__ = "episode_assets"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)

    asset_type = Column(String, nullable=False, default="cover")  # 'cover'

    file_url = Column(String, nullable=False)

    prompt_used = Column(Text, nullable=True)
    model_used = Column(String, nullable=True)  # ex: 'qwen-image-2.0-pro', ou 'user_upload'

    version = Column(Integer, default=1)
    generation_batch = Column(Integer, default=1)
    is_selected = Column(Boolean, default=False)
    status = Column(String, default="completed")  # 'pending', 'completed', 'failed'

    created_at = Column(DateTime, default=datetime.utcnow)

    episode = relationship("Episode", back_populates="assets")
