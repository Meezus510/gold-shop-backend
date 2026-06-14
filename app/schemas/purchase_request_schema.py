from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.purchase_request_model import PurchaseRequestStatus


class PurchaseRequestCreate(BaseModel):
    item_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=40)


class PurchaseRequestPublicOut(BaseModel):
    id: int
    status: PurchaseRequestStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseRequestAdminOut(BaseModel):
    id: int
    status: PurchaseRequestStatus
    item_id: int
    item_number_prefix_snapshot: str | None = None
    item_number_snapshot: int | None = None
    item_code_snapshot: str | None = None
    item_name_snapshot: str
    listed_price_snapshot: Decimal | None = None
    customer_name: str
    customer_phone: str
    decided_by_admin_id: int | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PurchaseRequestCountOut(BaseModel):
    pending: int


PurchaseRequestStatusFilter = Literal["all", "pending", "accepted", "declined"]
