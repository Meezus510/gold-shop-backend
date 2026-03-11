from pydantic import BaseModel
from typing import Literal


class TranslationCreate(BaseModel):
    language: Literal["en", "es"]
    name: str
    description: str | None = None


class TranslationOut(BaseModel):
    id: int
    language: str
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}
