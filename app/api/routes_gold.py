from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.models.item_model import Item
from app.services.auth_service import get_current_admin
from app.services.gold_price_service import GRAMS_PER_TROY_OZ, get_current_gold_price

router = APIRouter(prefix="/gold", tags=["Gold Price"])


@router.get("/price")
def current_gold_price(_: Admin = Depends(get_current_admin)):
    """Returns the current spot gold price (admin only)."""
    price = get_current_gold_price()
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch gold price from external API",
        )
    return {"gold_price_usd_per_oz": price}


@router.post("/recalculate-prices")
def recalculate_all_prices(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """
    Recalculates price for every item using the current gold spot price.
    Intended to be called from a scheduled weekly job.
    """
    gold_price = get_current_gold_price()
    if gold_price is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch gold price from external API",
        )

    items = db.query(Item).all()
    updated = 0
    for item in items:
        item.price = round((item.weight_grams / GRAMS_PER_TROY_OZ) * gold_price * item.price_multiplier, 2)
        updated += 1

    db.commit()
    return {"updated_items": updated, "gold_price_used": gold_price}
