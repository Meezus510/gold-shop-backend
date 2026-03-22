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
from app.services.pricing_service import compute_listed_prices

logger = logging.getLogger(__name__)

SYNC_INTERVAL_DAYS = 7


def recalculate_all(db: Session, *, force_fresh_prices: bool = True) -> dict:
    """
    Recalculate listed_price_flat and listed_price_loan for every metal item
    that has markup_flat configured.
    Returns a summary dict.
    """
    if force_fresh_prices:
        invalidate_cache()

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
            if item.weight_grams and item.purity_karat and item.markup_flat is not None:
                _, listed_flat, listed_loan = compute_listed_prices(
                    api_symbol=metal.spot_price_api_symbol,
                    weight_grams=item.weight_grams,
                    purity_karat=item.purity_karat,
                    purity_denominator=metal.purity_denominator,
                    markup_flat=float(item.markup_flat),
                    markup_loan=float(item.markup_loan or 0),
                )
                if listed_flat is not None:
                    item.listed_price_flat = listed_flat
                if listed_loan is not None:
                    item.listed_price_loan = listed_loan
                total_updated += 1
            else:
                total_skipped += 1

    db.commit()
    return {"updated": total_updated, "skipped": total_skipped, "errors": errors}


def recalculate_one(db: Session, item_id: int) -> Item:
    """Recalculate listed prices for a single metal item. Raises ValueError if not applicable."""
    item = db.query(Item).filter(Item.item_id == item_id).first()
    if not item:
        raise ValueError("Item not found")
    if not item.metal_id:
        raise ValueError("Item has no metal — prices must be set manually")
    if not (item.weight_grams and item.purity_karat and item.markup_flat is not None):
        raise ValueError("Item is missing weight, purity, or markup_flat")

    metal = db.query(Metal).filter(Metal.id == item.metal_id).first()
    spot_price = get_spot_price(metal.spot_price_api_symbol)
    if spot_price is None:
        raise ValueError(f"Could not fetch {metal.name} spot price from external API")

    _, listed_flat, listed_loan = compute_listed_prices(
        api_symbol=metal.spot_price_api_symbol,
        weight_grams=item.weight_grams,
        purity_karat=item.purity_karat,
        purity_denominator=metal.purity_denominator,
        markup_flat=float(item.markup_flat),
        markup_loan=float(item.markup_loan or 0),
    )
    if listed_flat is not None:
        item.listed_price_flat = listed_flat
    if listed_loan is not None:
        item.listed_price_loan = listed_loan

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
    config.last_sync_at      = datetime.now(timezone.utc)
    config.next_sync_at      = next_sync_at
    config.last_items_updated = items_updated
    db.commit()
    db.refresh(config)
    return config
