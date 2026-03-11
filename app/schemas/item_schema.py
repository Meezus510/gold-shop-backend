from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.models.item_model import ItemStatus
from app.schemas.metal_schema import MetalOut
from app.schemas.translation_schema import TranslationCreate, TranslationOut


# ── Public response (single language resolved) ──────────────────────────────

class ItemPublicOut(BaseModel):
    item_id: int
    name: str
    description: str | None = None
    category: str
    weight_grams: float | None = None
    price: float | None = None
    image_url: str | None = None
    status: ItemStatus
    metal: MetalOut | None = None
    purity_karat: float | None = None

    model_config = {"from_attributes": True}


# ── Admin create / update ────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    category: str
    # Metal items
    metal_id: int | None = None
    purity_karat: float | None = None
    weight_grams: float | None = None
    price_multiplier: float | None = 1.0
    # Non-metal items (or manual price override)
    price: float | None = None
    cost: float | None = None
    image_url: str | None = None
    translations: List[TranslationCreate]


class ItemUpdate(BaseModel):
    category: str | None = None
    metal_id: int | None = None
    purity_karat: float | None = None
    weight_grams: float | None = None
    price_multiplier: float | None = None
    price: float | None = None          # manual price for non-metal items
    cost: float | None = None
    sell_price: float | None = None
    image_url: str | None = None
    status: ItemStatus | None = None
    translations: List[TranslationCreate] | None = None


class ItemStatusUpdate(BaseModel):
    status: ItemStatus
    sell_price: float | None = None  # optionally record sell price when marking SOLD


# ── Admin full response (all translations + metal info) ──────────────────────

class ItemAdminOut(BaseModel):
    item_id: int
    category: str
    metal: MetalOut | None = None
    purity_karat: float | None = None
    weight_grams: float | None = None
    cost: float | None = None
    price: float | None = None
    price_multiplier: float | None = None
    sell_price: float | None = None
    image_url: str | None = None
    status: ItemStatus
    created_at: datetime
    updated_at: datetime
    translations: List[TranslationOut]

    model_config = {"from_attributes": True}
