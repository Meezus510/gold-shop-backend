from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.item_model import Item, ItemStatus
from app.models.item_translation_model import ItemTranslation
from app.models.metal_model import Metal
from app.schemas.item_schema import ItemCreate, ItemUpdate, ItemPublicOut
from app.schemas.translation_schema import TranslationCreate
from app.services.pricing_service import calculate_item_price


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def _resolve_translation(item: Item, lang: str) -> dict:
    """Pick the requested language, fall back to 'en', then first available."""
    translation = next((t for t in item.translations if t.language == lang), None)
    if not translation:
        translation = next((t for t in item.translations if t.language == "en"), None)
    if not translation and item.translations:
        translation = item.translations[0]
    return {
        "name": translation.name if translation else "",
        "description": translation.description if translation else None,
    }


def _upsert_translations(db: Session, item: Item, translations: List[TranslationCreate]):
    existing = {t.language: t for t in item.translations}
    for t_data in translations:
        if t_data.language in existing:
            existing[t_data.language].name = t_data.name
            existing[t_data.language].description = t_data.description
        else:
            db.add(ItemTranslation(
                item_id=item.item_id,
                language=t_data.language,
                name=t_data.name,
                description=t_data.description,
            ))


def _calculate_metal_price(db: Session, item: Item) -> float | None:
    """
    Auto-calculates price for metal items.
    Returns None if metal info is incomplete or spot price fetch fails.
    """
    if not item.metal_id or item.purity_karat is None or not item.weight_grams or not item.price_multiplier:
        return None
    metal = db.query(Metal).filter(Metal.id == item.metal_id).first()
    if not metal:
        return None
    return calculate_item_price(
        api_symbol=metal.spot_price_api_symbol,
        weight_grams=item.weight_grams,
        purity_karat=item.purity_karat,
        purity_denominator=metal.purity_denominator,
        price_multiplier=item.price_multiplier,
    )


# ── Public ────────────────────────────────────────────────────────────────────

def get_public_items(db: Session, lang: str) -> List[ItemPublicOut]:
    """Returns all items (all statuses) — frontend displays status badges."""
    items = (
        db.query(Item)
        .order_by(Item.created_at.desc())
        .all()
    )
    result = []
    for item in items:
        t = _resolve_translation(item, lang)
        result.append(ItemPublicOut(
            item_id=item.item_id,
            name=t["name"],
            description=t["description"],
            category=item.category,
            weight_grams=item.weight_grams,
            price=item.price,
            image_url=item.image_url,
            status=item.status,
            metal=item.metal,
            purity_karat=item.purity_karat,
        ))
    return result


def get_public_item(db: Session, item_id: int, lang: str) -> ItemPublicOut:
    item = _get_item_or_404(db, item_id)
    t = _resolve_translation(item, lang)
    return ItemPublicOut(
        item_id=item.item_id,
        name=t["name"],
        description=t["description"],
        category=item.category,
        weight_grams=item.weight_grams,
        price=item.price,
        image_url=item.image_url,
        status=item.status,
        metal=item.metal,
        purity_karat=item.purity_karat,
    )


# ── Admin ─────────────────────────────────────────────────────────────────────

def create_item(db: Session, data: ItemCreate) -> Item:
    item = Item(
        category=data.category,
        metal_id=data.metal_id,
        purity_karat=data.purity_karat,
        weight_grams=data.weight_grams,
        cost=data.cost,
        price=data.price,           # may be overwritten below for metal items
        price_multiplier=data.price_multiplier,
        image_url=data.image_url,
    )
    db.add(item)
    db.flush()  # get item_id before adding translations

    # Auto-calculate price for metal items (overrides manual price)
    if data.metal_id:
        calculated = _calculate_metal_price(db, item)
        if calculated is not None:
            item.price = calculated

    for t_data in data.translations:
        db.add(ItemTranslation(
            item_id=item.item_id,
            language=t_data.language,
            name=t_data.name,
            description=t_data.description,
        ))
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, data: ItemUpdate) -> Item:
    item = _get_item_or_404(db, item_id)
    if data.category is not None:
        item.category = data.category
    if data.metal_id is not None:
        item.metal_id = data.metal_id
    if data.purity_karat is not None:
        item.purity_karat = data.purity_karat
    if data.weight_grams is not None:
        item.weight_grams = data.weight_grams
    if data.price_multiplier is not None:
        item.price_multiplier = data.price_multiplier
    if data.cost is not None:
        item.cost = data.cost
    if data.sell_price is not None:
        item.sell_price = data.sell_price
    if data.image_url is not None:
        item.image_url = data.image_url
    if data.status is not None:
        item.status = data.status

    # Recalculate price for metal items when relevant fields change
    metal_fields_changed = any([
        data.metal_id, data.purity_karat, data.weight_grams, data.price_multiplier
    ])
    if item.metal_id and metal_fields_changed:
        calculated = _calculate_metal_price(db, item)
        if calculated is not None:
            item.price = calculated
    elif data.price is not None and not item.metal_id:
        # Manual price for non-metal items
        item.price = data.price

    if data.translations is not None:
        _upsert_translations(db, item, data.translations)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    item = _get_item_or_404(db, item_id)
    db.delete(item)
    db.commit()


def update_item_status(db: Session, item_id: int, new_status: ItemStatus, sell_price: float | None = None) -> Item:
    item = _get_item_or_404(db, item_id)
    item.status = new_status
    if sell_price is not None:
        item.sell_price = sell_price
    db.commit()
    db.refresh(item)
    return item
