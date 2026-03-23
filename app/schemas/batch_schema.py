from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field

from app.models.item_model import ItemStatus


class BatchRowPreview(BaseModel):
    """One enriched row returned to the admin for review before committing."""
    purchase_date:     date    | None = None
    purchase_location: str     | None = None
    qty:               int     | None = None
    category:          str     | None = None   # inferred by Claude
    name_es:           str     | None = None
    description_es:    str     | None = None
    name_en:           str     | None = None
    description_en:    str     | None = None
    cost:              Decimal | None = None
    weight_grams:      float   | None = None
    listed_price_flat: Decimal | None = None
    listed_price_loan: Decimal | None = None


class BatchParseResponse(BaseModel):
    """Response from POST /admin/parse-batch-image."""
    rows:             List[BatchRowPreview]
    source_image_url: str   # Cloudinary URL of the uploaded source image


class BatchRowCreate(BaseModel):
    """One confirmed row submitted by admin after reviewing the preview table."""
    purchase_date:     date    | None = None
    purchase_location: str     | None = None
    qty:               int            = Field(default=1, ge=1)
    category:          str            = Field(min_length=1, max_length=100)
    name_es:           str            = Field(min_length=1)
    description_es:    str     | None = None
    name_en:           str     | None = None
    description_en:    str     | None = None
    cost:              Decimal | None = Field(default=None, ge=0)
    weight_grams:      float   | None = Field(default=None, gt=0)
    listed_price_flat: Decimal | None = Field(default=None, ge=0)
    listed_price_loan: Decimal | None = Field(default=None, ge=0)
    status:            ItemStatus     = ItemStatus.AVAILABLE
    sell_price:        Decimal | None = Field(default=None, ge=0)


class BatchCreate(BaseModel):
    """Full payload for POST /admin/items/batch."""
    batch_type:   str   = "metal"          # "metal" | "na"
    metal_id:     int   | None = None
    purity_karat: float | None = Field(default=None, gt=0, le=1_000)
    rows:         List[BatchRowCreate] = Field(min_length=1)
