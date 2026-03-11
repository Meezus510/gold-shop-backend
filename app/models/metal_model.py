from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Metal(Base):
    __tablename__ = "metals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)          # e.g. "Gold"
    symbol = Column(String, nullable=False, unique=True)         # e.g. "XAU"
    spot_price_api_symbol = Column(String, nullable=False)       # e.g. "gold" (used in API URL)
    purity_denominator = Column(Integer, nullable=False)         # 24 for gold karats, 1000 for silver millesimal
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("Item", back_populates="metal")
