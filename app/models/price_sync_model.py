from datetime import datetime

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func

from app.db.database import Base


class PriceSyncConfig(Base):
    """Single-row table that tracks when prices were last synced and when they're due next."""
    __tablename__ = "price_sync_config"

    id                 = Column(Integer, primary_key=True, default=1)
    last_sync_at       = Column(DateTime(timezone=True), nullable=True)
    next_sync_at       = Column(DateTime(timezone=True), nullable=True)
    last_items_updated = Column(Integer, nullable=False, default=0)
    updated_at         = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
