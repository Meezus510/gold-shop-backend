from pydantic import BaseModel


class ItemImageOut(BaseModel):
    id: int
    url: str
    position: int

    model_config = {"from_attributes": True}
