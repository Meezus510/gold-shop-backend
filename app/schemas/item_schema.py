from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.item_model import ItemStatus
from app.schemas.item_image_schema import ItemImageOut
from app.schemas.metal_schema import MetalOut
from app.schemas.purchase_location_schema import PurchaseLocationOut
from app.schemas.translation_schema import TranslationCreate, TranslationOut


# ── Public response (single language resolved) ───────────────────────────────

class ItemPublicOut(BaseModel):
    item_id:     int
    name:        str
    description: str | None = None
    category:    str
    weight_grams: float | None = None
    listed_price_flat: Decimal | None = None
    listed_price_loan: Decimal | None = None
    # Backward-compat alias: frontend reads `price` — maps to listed_price_flat
    price: Decimal | None = None
    image_url: str | None = None          # first image for catalog cards / WhatsApp
    images:    List[str] = []             # full ordered list for detail gallery
    status:    ItemStatus
    metal:        MetalOut | None = None
    purity_karat: float | None = None

    model_config = {"from_attributes": True}


# ── Admin create ─────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    category:     str   = Field(min_length=1, max_length=100)
    metal_id:     int   | None = None
    purity_karat: float | None = Field(default=None, gt=0, le=1_000)
    weight_grams: float | None = Field(default=None, gt=0, le=100_000)
    quantity:     int          = Field(default=1, ge=1, le=100_000)
    cost:         float | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    purchase_location_id: int | None = None
    is_visible: bool = False

    # Metal items: provide markups — listed prices are computed from spot price + markup
    markup_flat: Decimal | None = Field(default=None, ge=0)
    markup_loan: Decimal | None = Field(default=None, ge=0)

    # Non-metal items: set listed prices directly (markups left NULL)
    listed_price_flat: Decimal | None = Field(default=None, ge=0)
    listed_price_loan: Decimal | None = Field(default=None, ge=0)

    # Ordered list of image URLs already uploaded to Cloudinary
    image_urls:   List[str]            = Field(default_factory=list, max_length=20)
    translations: List[TranslationCreate]


# ── Admin update ─────────────────────────────────────────────────────────────

class ItemUpdate(BaseModel):
    category:     str   | None = Field(default=None, min_length=1, max_length=100)
    metal_id:     int   | None = None
    purity_karat: float | None = Field(default=None, gt=0, le=1_000)
    weight_grams: float | None = Field(default=None, gt=0, le=100_000)
    quantity:     int   | None = Field(default=None, ge=1, le=100_000)
    cost:         float | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    purchase_location_id: int | None = None
    is_visible: bool | None = None

    markup_flat: Decimal | None = Field(default=None, ge=0)
    markup_loan: Decimal | None = Field(default=None, ge=0)
    listed_price_flat: Decimal | None = Field(default=None, ge=0)
    listed_price_loan: Decimal | None = Field(default=None, ge=0)

    sell_price: float | None = Field(default=None, ge=0)

    # None = don't touch images; [] = remove all; [...] = replace with this list
    image_urls:   List[str] | None = Field(default=None, max_length=20)
    status:       ItemStatus | None = None
    translations: List[TranslationCreate] | None = None


# ── Status update ─────────────────────────────────────────────────────────────

class ItemStatusUpdate(BaseModel):
    status:     ItemStatus
    sell_price: float | None = Field(default=None, ge=0)


# ── Visibility toggle ─────────────────────────────────────────────────────────

class ItemVisibilityUpdate(BaseModel):
    is_visible: bool


# ── Unit adjustment (multi-quantity items) ────────────────────────────────────

class UnitAdjust(BaseModel):
    """Move `units` items between available / pending / sold buckets."""
    from_state: Literal["available", "pending", "sold"]
    to_state:   Literal["available", "pending", "sold"]
    units:      int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def states_must_differ(self) -> "UnitAdjust":
        if self.from_state == self.to_state:
            raise ValueError("from_state and to_state must be different")
        return self


# ── Admin full response ───────────────────────────────────────────────────────

class ItemAdminOut(BaseModel):
    item_id:      int
    category:     str
    metal:        MetalOut | None = None
    purity_karat: float | None = None
    weight_grams: float | None = None
    cost:         float | None = None
    purchase_date: date | None = None

    quantity:           int = 1
    quantity_available: int = 0
    quantity_pending:   int = 0
    quantity_sold:      int = 0

    markup_flat:       Decimal | None = None
    markup_loan:       Decimal | None = None
    listed_price_flat: Decimal | None = None
    listed_price_loan: Decimal | None = None
    sell_price:        Decimal | None = None   # actual price sold for

    purchase_location: PurchaseLocationOut | None = None
    is_visible: bool = True
    images:      List[ItemImageOut] = []
    status:      ItemStatus
    created_at:  datetime
    updated_at:  datetime
    translations: List[TranslationOut]

    model_config = {"from_attributes": True}
