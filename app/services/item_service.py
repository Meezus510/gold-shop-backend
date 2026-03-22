from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.item_image_model import ItemImage
from app.models.item_model import Item, ItemStatus
from app.models.item_translation_model import ItemTranslation
from app.models.metal_model import Metal
from app.schemas.item_schema import ItemCreate, ItemPublicOut, ItemUpdate, UnitAdjust
from app.schemas.translation_schema import TranslationCreate
from app.services.pricing_service import compute_listed_prices


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def _resolve_translation(item: Item, lang: str) -> dict:
    translation = next((t for t in item.translations if t.language == lang), None)
    if not translation:
        translation = next((t for t in item.translations if t.language == "en"), None)
    if not translation and item.translations:
        translation = item.translations[0]
    return {
        "name":        translation.name        if translation else "",
        "description": translation.description if translation else None,
    }


def _upsert_translations(db: Session, item: Item, translations: List[TranslationCreate]):
    existing = {t.language: t for t in item.translations}
    for t_data in translations:
        if t_data.language in existing:
            existing[t_data.language].name        = t_data.name
            existing[t_data.language].description = t_data.description
        else:
            db.add(ItemTranslation(
                item_id=item.item_id,
                language=t_data.language,
                name=t_data.name,
                description=t_data.description,
            ))


def _replace_images(db: Session, item: Item, urls: List[str]):
    db.query(ItemImage).filter(ItemImage.item_id == item.item_id).delete()
    for position, url in enumerate(urls):
        db.add(ItemImage(item_id=item.item_id, url=url, position=position))


def _compute_metal_listed_prices(db: Session, item: Item) -> tuple[Decimal | None, Decimal | None]:
    """
    Returns (listed_price_flat, listed_price_loan) computed from current spot price + markups.
    Returns (None, None) if any required field is missing or spot price is unavailable.
    """
    if not item.metal_id or item.purity_karat is None or not item.weight_grams:
        return None, None
    if item.markup_flat is None:
        return None, None
    metal = db.query(Metal).filter(Metal.id == item.metal_id).first()
    if not metal:
        return None, None
    _, listed_flat, listed_loan = compute_listed_prices(
        api_symbol=metal.spot_price_api_symbol,
        weight_grams=item.weight_grams,
        purity_karat=item.purity_karat,
        purity_denominator=metal.purity_denominator,
        markup_flat=float(item.markup_flat),
        markup_loan=float(item.markup_loan or 0),
    )
    return listed_flat, listed_loan


def _recompute_status(item: Item) -> None:
    """Derive item status from unit counters. Always call after mutating counters."""
    if item.quantity_available > 0:
        item.status = ItemStatus.AVAILABLE
    elif item.quantity_pending > 0:
        item.status = ItemStatus.SALE_PENDING
    else:
        item.status = ItemStatus.SOLD


def _primary_image_url(item: Item) -> str | None:
    return item.images[0].url if item.images else None


def _image_url_list(item: Item) -> List[str]:
    return [img.url for img in item.images]


# ── Public ────────────────────────────────────────────────────────────────────

def get_public_items(db: Session, lang: str) -> List[ItemPublicOut]:
    items = (
        db.query(Item)
        .filter(Item.is_visible == True)  # noqa: E712
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
            listed_price_flat=item.listed_price_flat,
            listed_price_loan=item.listed_price_loan,
            price=item.listed_price_flat,   # backward-compat alias
            image_url=_primary_image_url(item),
            images=_image_url_list(item),
            status=item.status,
            metal=item.metal,
            purity_karat=item.purity_karat,
        ))
    return result


def get_public_item(db: Session, item_id: int, lang: str) -> ItemPublicOut:
    item = _get_item_or_404(db, item_id)
    if not item.is_visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    t = _resolve_translation(item, lang)
    return ItemPublicOut(
        item_id=item.item_id,
        name=t["name"],
        description=t["description"],
        category=item.category,
        weight_grams=item.weight_grams,
        listed_price_flat=item.listed_price_flat,
        listed_price_loan=item.listed_price_loan,
        price=item.listed_price_flat,
        image_url=_primary_image_url(item),
        images=_image_url_list(item),
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
        quantity=data.quantity,
        quantity_available=data.quantity,
        quantity_pending=0,
        quantity_sold=0,
        cost=data.cost,
        purchase_date=data.purchase_date,
        purchase_location_id=data.purchase_location_id,
        is_visible=data.is_visible,
        markup_flat=data.markup_flat,
        markup_loan=data.markup_loan,
        listed_price_flat=data.listed_price_flat,
        listed_price_loan=data.listed_price_loan,
    )
    db.add(item)
    db.flush()  # get item_id

    # For metal items, compute listed prices from markups + current spot price
    if data.metal_id and data.markup_flat is not None:
        flat, loan = _compute_metal_listed_prices(db, item)
        if flat is not None:
            item.listed_price_flat = flat
        if loan is not None:
            item.listed_price_loan = loan

    for t_data in data.translations:
        db.add(ItemTranslation(
            item_id=item.item_id,
            language=t_data.language,
            name=t_data.name,
            description=t_data.description,
        ))

    for position, url in enumerate(data.image_urls):
        db.add(ItemImage(item_id=item.item_id, url=url, position=position))

    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, data: ItemUpdate) -> Item:
    item = _get_item_or_404(db, item_id)

    if data.category is not None:
        item.category = data.category
    # Always apply metal_id so frontend can clear it by sending null
    item.metal_id = data.metal_id
    if data.purity_karat is not None:
        item.purity_karat = data.purity_karat
    if data.weight_grams is not None:
        item.weight_grams = data.weight_grams
    if data.purchase_date is not None:
        item.purchase_date = data.purchase_date
    if data.markup_flat is not None:
        item.markup_flat = data.markup_flat
    if data.markup_loan is not None:
        item.markup_loan = data.markup_loan
    if data.listed_price_flat is not None:
        item.listed_price_flat = data.listed_price_flat
    if data.listed_price_loan is not None:
        item.listed_price_loan = data.listed_price_loan
    if data.quantity is not None and data.quantity != item.quantity:
        delta = data.quantity - item.quantity
        item.quantity = data.quantity
        item.quantity_available = max(0, item.quantity_available + delta)
        _recompute_status(item)
    item.purchase_location_id = data.purchase_location_id
    if data.cost is not None:
        item.cost = data.cost
    if data.sell_price is not None:
        item.sell_price = data.sell_price
    if data.status is not None:
        item.status = data.status
    if data.is_visible is not None:
        item.is_visible = data.is_visible

    # Recompute listed prices when metal pricing fields change
    metal_fields_changed = any([
        data.metal_id is not None,
        data.purity_karat is not None,
        data.weight_grams is not None,
        data.markup_flat is not None,
        data.markup_loan is not None,
    ])
    if item.metal_id and metal_fields_changed and item.markup_flat is not None:
        flat, loan = _compute_metal_listed_prices(db, item)
        if flat is not None:
            item.listed_price_flat = flat
        if loan is not None:
            item.listed_price_loan = loan

    if data.translations is not None:
        _upsert_translations(db, item, data.translations)

    if data.image_urls is not None:
        _replace_images(db, item, data.image_urls)

    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    item = _get_item_or_404(db, item_id)
    db.delete(item)
    db.commit()


def update_item_status(
    db: Session,
    item_id: int,
    new_status: ItemStatus,
    sell_price: float | None = None,
) -> Item:
    item = _get_item_or_404(db, item_id)
    if new_status == ItemStatus.AVAILABLE:
        item.quantity_available, item.quantity_pending, item.quantity_sold = item.quantity, 0, 0
    elif new_status == ItemStatus.SALE_PENDING:
        item.quantity_available, item.quantity_pending, item.quantity_sold = 0, item.quantity, 0
    else:  # SOLD
        item.quantity_available, item.quantity_pending, item.quantity_sold = 0, 0, item.quantity
    item.status = new_status
    if sell_price is not None:
        item.sell_price = sell_price
    db.commit()
    db.refresh(item)
    return item


def toggle_visibility(db: Session, item_id: int, is_visible: bool) -> Item:
    item = _get_item_or_404(db, item_id)
    item.is_visible = is_visible
    db.commit()
    db.refresh(item)
    return item


def adjust_units(db: Session, item_id: int, data: UnitAdjust) -> Item:
    """Atomically move `data.units` items between available / pending / sold buckets."""
    item = _get_item_or_404(db, item_id)

    counter = {
        "available": "quantity_available",
        "pending":   "quantity_pending",
        "sold":      "quantity_sold",
    }
    src_attr = counter[data.from_state]
    dst_attr = counter[data.to_state]

    src_count = getattr(item, src_attr)
    if src_count < data.units:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {src_count} unit(s) in '{data.from_state}' state — cannot move {data.units}",
        )

    setattr(item, src_attr, src_count - data.units)
    setattr(item, dst_attr, getattr(item, dst_attr) + data.units)
    _recompute_status(item)

    db.commit()
    db.refresh(item)
    return item
