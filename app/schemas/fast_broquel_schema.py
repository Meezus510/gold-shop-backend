from pydantic import BaseModel, Field


class FastBroquelAnalysis(BaseModel):
    name_es: str = Field(min_length=1, max_length=60)
    description_es: str = Field(min_length=1, max_length=500)
    name_en: str = Field(min_length=1, max_length=60)
    description_en: str = Field(min_length=1, max_length=500)
