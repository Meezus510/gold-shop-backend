import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class ItemStatus(str, enum.Enum):
    AVAILABLE    = "AVAILABLE"
    SALE_PENDING = "SALE_PENDING"
    SOLD         = "SOLD"


class Item(Base):
    __tablename__ = "items"

    item_id  = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)

    # Metal link — nullable so non-metal items (bags, accessories, etc.) are supported
    metal_id     = Column(Integer, ForeignKey("metals.id"), nullable=True)
    purity_karat = Column(Float, nullable=True)   # e.g. 14 (for 14k gold), 925 (sterling silver)

    weight_grams = Column(Float, nullable=True)
    purchase_date = Column(Date, nullable=True)

    quantity           = Column(Integer, nullable=False, default=1)
    quantity_available = Column(Integer, nullable=False, default=0)
    quantity_pending   = Column(Integer, nullable=False, default=0)
    quantity_sold      = Column(Integer, nullable=False, default=0)

    cost = Column(Float, nullable=True)  # what you paid for it

    # ── Pricing config ────────────────────────────────────────────────────────
    # Metal items: store markups ($ above base_market_price). Weekly scheduler
    # recomputes listed_price_flat/loan from these + current spot price.
    # Non-metal items: markup_flat/loan are NULL; listed prices set directly.
    markup_flat = Column(Numeric(10, 2), nullable=True)
    markup_loan = Column(Numeric(10, 2), nullable=True)

    # Cached listed prices. Source of truth for what customers see.
    listed_price_flat = Column(Numeric(10, 2), nullable=True)
    listed_price_loan = Column(Numeric(10, 2), nullable=True)

    # Actual price this item sold for — only populated when status → SOLD
    # DB column renamed to actual_sell_price; Python attr kept as sell_price
    # for backward compatibility with existing API responses.
    sell_price = Column("actual_sell_price", Numeric(10, 2), nullable=True)

    purchase_location_id = Column(Integer, ForeignKey("purchase_locations.id"), nullable=True)
    is_visible = Column(Boolean, nullable=False, default=False)
    status     = Column(Enum(ItemStatus), nullable=False, default=ItemStatus.AVAILABLE)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    metal             = relationship("Metal", back_populates="items", lazy="selectin")
    purchase_location = relationship("PurchaseLocation", back_populates="items", lazy="selectin")
    translations      = relationship(
        "ItemTranslation", back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )
    images = relationship(
        "ItemImage", back_populates="item", cascade="all, delete-orphan",
        order_by="ItemImage.position", lazy="selectin",
    )
