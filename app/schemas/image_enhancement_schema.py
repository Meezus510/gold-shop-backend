from pydantic import BaseModel


class ImageEnhancementSettingOut(BaseModel):
    global_enabled: bool
    eligible_images: int
    enhanced_images: int


class ImageEnhancementSettingUpdate(BaseModel):
    global_enabled: bool


class ItemImageEnhancementUpdate(BaseModel):
    enabled: bool
