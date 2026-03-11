import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class ItemStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    SALE_PENDING = "SALE_PENDING"
    SOLD = "SOLD"


class Item(Base):
    __tablename__ = "items"

    item_id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)

    # Metal link — nullable so non-metal items (bags, accessories, etc.) are supported
    metal_id = Column(Integer, ForeignKey("metals.id"), nullable=True)
    purity_karat = Column(Float, nullable=True)   # e.g. 22 (for 22k gold), 925 (sterling silver)

    weight_grams = Column(Float, nullable=True)   # nullable for non-weight-based items
    cost = Column(Float, nullable=True)           # what you paid for it
    price = Column(Float, nullable=True)          # auto-calculated for metal items; manual for others
    price_multiplier = Column(Float, nullable=True, default=1.0)  # nullable for non-metal items
    sell_price = Column(Float, nullable=True)     # actual price it sold for
    image_url = Column(String, nullable=True)
    status = Column(Enum(ItemStatus), nullable=False, default=ItemStatus.AVAILABLE)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    metal = relationship("Metal", back_populates="items")
    translations = relationship(
        "ItemTranslation", back_populates="item", cascade="all, delete-orphan"
    )
