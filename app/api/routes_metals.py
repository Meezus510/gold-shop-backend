from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.models.item_model import Item
from app.models.metal_model import Metal
from app.schemas.metal_schema import MetalCreate, MetalOut, MetalSpotPrice, MetalUpdate
from app.services.auth_service import get_current_admin
from app.services.metals_price_service import get_spot_price
from app.services.pricing_service import calculate_item_price
from app.services import price_sync_service, scheduler_service
from app.models.price_sync_model import PriceSyncConfig

router = APIRouter(prefix="/metals", tags=["Metals"])


# ── Public — list metals ────────────────────────────────────────────────────

@router.get("", response_model=List[MetalOut])
def list_metals(db: Session = Depends(get_db)):
    """Returns all configured metals (public — used to populate dropdowns)."""
    return db.query(Metal).order_by(Metal.name).all()


# ── Admin — CRUD ────────────────────────────────────────────────────────────

@router.post("", response_model=MetalOut, status_code=status.HTTP_201_CREATED)
def create_metal(
    data: MetalCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    if db.query(Metal).filter(Metal.symbol == data.symbol).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Metal symbol already exists")
    metal = Metal(**data.model_dump())
    db.add(metal)
    db.commit()
    db.refresh(metal)
    return metal


@router.put("/{metal_id}", response_model=MetalOut)
def update_metal(
    metal_id: int,
    data: MetalUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    metal = db.query(Metal).filter(Metal.id == metal_id).first()
    if not metal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metal not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(metal, field, value)
    db.commit()
    db.refresh(metal)
    return metal


@router.delete("/{metal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metal(
    metal_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    metal = db.query(Metal).filter(Metal.id == metal_id).first()
    if not metal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metal not found")
    if db.query(Item).filter(Item.metal_id == metal_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete metal that has associated items",
        )
    db.delete(metal)
    db.commit()


# ── Admin — Spot prices & recalculation ─────────────────────────────────────

@router.get("/spot-prices", response_model=List[MetalSpotPrice])
def all_spot_prices(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Fetches current spot prices for all configured metals."""
    metals = db.query(Metal).order_by(Metal.name).all()
    result = []
    for metal in metals:
        price = get_spot_price(metal.spot_price_api_symbol)
        if price is not None:
            result.append(MetalSpotPrice(
                metal_id=metal.id,
                name=metal.name,
                symbol=metal.symbol,
                spot_price_usd_per_oz=price,
            ))
    return result


@router.post("/{metal_id}/recalculate-prices")
def recalculate_metal_prices(
    metal_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """
    Recalculates prices for all items of a specific metal using current spot price.
    Skips items missing weight, purity, or multiplier.
    """
    metal = db.query(Metal).filter(Metal.id == metal_id).first()
    if not metal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metal not found")

    spot_price = get_spot_price(metal.spot_price_api_symbol)
    if spot_price is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not fetch {metal.name} spot price from external API",
        )

    items = db.query(Item).filter(Item.metal_id == metal_id).all()
    updated = 0
    skipped = 0
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
            updated += 1
        else:
            skipped += 1

    db.commit()
    return {
        "metal": metal.name,
        "spot_price_used": spot_price,
        "updated_items": updated,
        "skipped_items": skipped,
    }


@router.post("/recalculate-all-prices")
def recalculate_all_metal_prices(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Recalculates prices for ALL metal items, then resets the weekly auto-sync countdown."""
    from datetime import datetime, timedelta, timezone
    result = price_sync_service.recalculate_all(db, force_fresh_prices=True)
    next_sync = datetime.now(timezone.utc) + timedelta(days=price_sync_service.SYNC_INTERVAL_DAYS)
    price_sync_service.record_sync(db, result["updated"], next_sync)
    scheduler_service.reset_schedule(db, next_sync)
    return {
        "total_updated": result["updated"],
        "total_skipped": result["skipped"],
        "errors":        result["errors"],
        "next_sync_at":  next_sync.isoformat(),
    }


@router.get("/price-sync-status")
def price_sync_status(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Returns last/next sync times and the scheduler's live next_run_time."""
    config = price_sync_service.get_or_create_config(db)
    next_run = scheduler_service.get_next_run_time()
    return {
        "last_sync_at":       config.last_sync_at.isoformat() if config.last_sync_at else None,
        "next_sync_at":       (next_run or config.next_sync_at or None) and
                              (next_run or config.next_sync_at).isoformat(),
        "last_items_updated": config.last_items_updated,
    }
