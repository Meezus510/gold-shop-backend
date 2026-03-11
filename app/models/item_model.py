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
    quantity           = Column(Integer, nullable=False, default=1)
    quantity_available = Column(Integer, nullable=False, default=0)
    quantity_pending   = Column(Integer, nullable=False, default=0)
    quantity_sold      = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=True)           # what you paid for it
    price = Column(Float, nullable=True)          # auto-calculated for metal items; manual for others
    price_multiplier = Column(Float, nullable=True, default=1.0)  # nullable for non-metal items
    flat_markup = Column(Float, nullable=True, default=0.0)      # fixed $ added on top of metal value × multiplier
    sell_price = Column(Float, nullable=True)     # actual price it sold for
    purchase_location_id = Column(Integer, ForeignKey("purchase_locations.id"), nullable=True)
    status = Column(Enum(ItemStatus), nullable=False, default=ItemStatus.AVAILABLE)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    metal = relationship("Metal", back_populates="items", lazy="selectin")
    purchase_location = relationship("PurchaseLocation", back_populates="items", lazy="selectin")
    translations = relationship(
        "ItemTranslation", back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )
    images = relationship(
        "ItemImage", back_populates="item", cascade="all, delete-orphan",
        order_by="ItemImage.position", lazy="selectin"
    )
