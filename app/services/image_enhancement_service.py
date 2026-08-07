import logging
import re
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.catalog_setting_model import CatalogSetting
from app.models.item_image_model import ItemImage
from app.models.item_model import Item, ItemStatus
from app.schemas.image_enhancement_schema import ImageEnhancementSettingOut

logger = logging.getLogger(__name__)

ENHANCEMENT_TRANSFORMATION = (
    "c_fill_pad,g_auto:subject:thirds_0,w_1200,h_1200,b_rgb:f7f4ee/"
    "e_improve/e_sharpen:40/q_auto,f_auto"
)
_VERSION_RE = re.compile(r"^v\d+$")
_TERMINAL_STATUSES = {ItemStatus.SOLD, ItemStatus.RETURNED_TO_VENDOR}


def cloudinary_asset_key(url: str | None) -> str | None:
    """Return a version-independent Cloudinary asset key for duplicate checks."""
    if not url or "/image/upload/" not in url:
        return None
    path = url.split("/image/upload/", 1)[1].split("?", 1)[0]
    parts = path.split("/")
    version_index = next(
        (index for index, part in enumerate(parts) if _VERSION_RE.fullmatch(part)),
        None,
    )
    if version_index is not None:
        parts = parts[version_index + 1:]
    if not parts:
        return None
    asset = "/".join(parts)
    return asset.rsplit(".", 1)[0] if "." in asset.rsplit("/", 1)[-1] else asset


def duplicate_asset_keys(db: Session) -> set[str]:
    """Return Cloudinary assets referenced by more than one inventory image."""
    keys = [
        key
        for (url,) in db.query(ItemImage.url).all()
        if (key := cloudinary_asset_key(url))
    ]
    return {key for key, count in Counter(keys).items() if count > 1}


def build_enhanced_url(original_url: str | None) -> str | None:
    """Build a reversible Cloudinary delivery URL; the original asset is untouched."""
    if not original_url or "/image/upload/" not in original_url:
        return None
    prefix, remainder = original_url.split("/image/upload/", 1)
    if ENHANCEMENT_TRANSFORMATION in remainder:
        return original_url
    return f"{prefix}/image/upload/{ENHANCEMENT_TRANSFORMATION}/{remainder}"


def build_unique_enhanced_url(
    db: Session,
    original_url: str | None,
    item_id: int,
) -> str | None:
    """Return an enhancement URL only when no other item shares the asset."""
    key = cloudinary_asset_key(original_url)
    if not key:
        return None
    other_urls = (
        db.query(ItemImage.url)
        .filter(ItemImage.item_id != item_id)
        .all()
    )
    if any(cloudinary_asset_key(row[0]) == key for row in other_urls):
        return None
    return build_enhanced_url(original_url)


def item_is_eligible(item: Item) -> bool:
    return item.status not in _TERMINAL_STATUSES


def get_or_create_settings(db: Session) -> CatalogSetting:
    settings = db.query(CatalogSetting).filter(CatalogSetting.id == 1).first()
    if settings:
        return settings
    settings = CatalogSetting(id=1, use_enhanced_images=False)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def effective_image_url(image: ItemImage, item: Item, global_enabled: bool) -> str:
    use_enhanced = (
        item_is_eligible(item)
        and image.enhanced_url
        and (global_enabled or item.use_enhanced_image)
    )
    return image.enhanced_url if use_enhanced else image.url


def enhancement_stats(db: Session) -> ImageEnhancementSettingOut:
    settings = get_or_create_settings(db)
    images = db.query(ItemImage).join(Item).all()
    eligible = [image for image in images if item_is_eligible(image.item)]
    return ImageEnhancementSettingOut(
        global_enabled=settings.use_enhanced_images,
        eligible_images=len(eligible),
        enhanced_images=sum(bool(image.enhanced_url) for image in eligible),
    )


def set_global_enabled(db: Session, enabled: bool) -> ImageEnhancementSettingOut:
    settings = get_or_create_settings(db)
    settings.use_enhanced_images = enabled
    db.commit()
    return enhancement_stats(db)


def set_item_enabled(db: Session, item_id: int, enabled: bool) -> Item:
    item = db.query(Item).filter(Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not item_is_eligible(item):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sold and returned items cannot use enhanced images.",
        )
    if enabled and not any(image.enhanced_url for image in item.images):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This item does not have an enhanced image available.",
        )
    item.use_enhanced_image = enabled
    db.commit()
    db.refresh(item)
    return item


def backfill_existing_images(db: Session) -> int:
    """Create enhanced delivery URLs for unique, non-terminal inventory photos."""
    images = db.query(ItemImage).join(Item).all()
    duplicate_keys = duplicate_asset_keys(db)
    updated = 0
    for image in images:
        key = cloudinary_asset_key(image.url)
        if (
            image.enhanced_url
            or not item_is_eligible(image.item)
            or not key
            or key in duplicate_keys
        ):
            continue
        image.enhanced_url = build_enhanced_url(image.url)
        if image.enhanced_url:
            updated += 1
    if updated:
        db.commit()
    logger.info("Image enhancement backfill prepared %d unique images", updated)
    return updated
