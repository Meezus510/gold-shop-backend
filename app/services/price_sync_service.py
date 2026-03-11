"""
Shared logic for recalculating all metal item prices.
Called by both the scheduled job and the manual admin trigger.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.item_model import Item
from app.models.metal_model import Metal
from app.models.price_sync_model import PriceSyncConfig
from app.services.metals_price_service import get_spot_price, invalidate_cache
from app.services.pricing_service import calculate_item_price

logger = logging.getLogger(__name__)

SYNC_INTERVAL_DAYS = 7


def recalculate_all(db: Session, *, force_fresh_prices: bool = True) -> dict:
    """
    Recalculate prices for every metal item that has enough data.
    Returns a summary dict.
    """
    if force_fresh_prices:
        invalidate_cache()  # force fresh fetch from gold-api.com

    metals = db.query(Metal).all()
    total_updated = 0
    total_skipped = 0
    errors = []

    for metal in metals:
        spot_price = get_spot_price(metal.spot_price_api_symbol)
        if spot_price is None:
            errors.append(f"Could not fetch {metal.name} spot price")
            continue

        items = db.query(Item).filter(Item.metal_id == metal.id).all()
        for item in items:
            if item.weight_grams and item.purity_karat and item.price_multiplier:
                item.price = calculate_item_price(
                    api_symbol=metal.spot_price_api_symbol,
                    weight_grams=item.weight_grams,
                    purity_karat=item.purity_karat,
                    purity_denominator=metal.purity_denominator,
                    price_multiplier=item.price_multiplier,
                    flat_markup=item.flat_markup or 0.0,
                )
                total_updated += 1
            else:
                total_skipped += 1

    db.commit()
    return {"updated": total_updated, "skipped": total_skipped, "errors": errors}


def recalculate_one(db: Session, item_id: int) -> Item:
    """Recalculate price for a single metal item. Raises ValueError if not applicable."""
    item = db.query(Item).filter(Item.item_id == item_id).first()
    if not item:
        raise ValueError("Item not found")
    if not item.metal_id:
        raise ValueError("Item has no metal — price must be set manually")
    if not (item.weight_grams and item.purity_karat and item.price_multiplier):
        raise ValueError("Item is missing weight, purity or multiplier")

    metal = db.query(Metal).filter(Metal.id == item.metal_id).first()
    spot_price = get_spot_price(metal.spot_price_api_symbol)
    if spot_price is None:
        raise ValueError(f"Could not fetch {metal.name} spot price from external API")

    item.price = calculate_item_price(
        api_symbol=metal.spot_price_api_symbol,
        weight_grams=item.weight_grams,
        purity_karat=item.purity_karat,
        purity_denominator=metal.purity_denominator,
        price_multiplier=item.price_multiplier,
        flat_markup=item.flat_markup or 0.0,
    )
    db.commit()
    db.refresh(item)
    return item


# ── Sync config helpers ────────────────────────────────────────────────────────

def get_or_create_config(db: Session) -> PriceSyncConfig:
    config = db.query(PriceSyncConfig).filter(PriceSyncConfig.id == 1).first()
    if not config:
        config = PriceSyncConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def record_sync(db: Session, items_updated: int, next_sync_at: datetime) -> PriceSyncConfig:
    config = get_or_create_config(db)
    config.last_sync_at = datetime.now(timezone.utc)
    config.next_sync_at = next_sync_at
    config.last_items_updated = items_updated
    db.commit()
    db.refresh(config)
    return config
