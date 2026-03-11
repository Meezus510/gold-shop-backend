from datetime import datetime

from pydantic import BaseModel


class PurchaseLocationCreate(BaseModel):
    name: str


class PurchaseLocationOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
