from datetime import datetime

from pydantic import BaseModel


class MetalCreate(BaseModel):
    name: str
    symbol: str
    spot_price_api_symbol: str
    purity_denominator: int


class MetalUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    spot_price_api_symbol: str | None = None
    purity_denominator: int | None = None


class MetalOut(BaseModel):
    id: int
    name: str
    symbol: str
    spot_price_api_symbol: str
    purity_denominator: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MetalSpotPrice(BaseModel):
    metal_id: int
    name: str
    symbol: str
    spot_price_usd_per_oz: float
