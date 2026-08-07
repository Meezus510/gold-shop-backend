from pydantic import BaseModel


class ItemImageOut(BaseModel):
    id: int
    url: str
    enhanced_url: str | None = None
    position: int

    model_config = {"from_attributes": True}
