from sqlalchemy.orm import Session

from app.models.item_model import Item, PricingMode
from app.models.metal_model import Metal


def category_key(category: str | None) -> str:
    raw = (category or "").strip().lower()
    return raw[4:] if raw.startswith("cat.") else raw


def item_number_prefix(db: Session, *, category: str | None, metal_id: int | None, pricing_mode: PricingMode) -> str:
    if category_key(category) == "broqueles":
        return "B"

    if metal_id:
        metal = db.query(Metal).filter(Metal.id == metal_id).first()
        metal_name = (metal.name if metal else "").strip().lower()
        if metal_name == "gold":
            return "O"
        if metal_name == "silver":
            return "P"
        if metal_name == "platinum":
            return "PT"

    if pricing_mode == PricingMode.MANUAL:
        return "B"

    return "X"


def next_item_number(db: Session, prefix: str) -> int:
    max_number = (
        db.query(Item.item_number)
        .filter(
            Item.item_number_prefix == prefix,
            Item.item_number.isnot(None),
        )
        .order_by(Item.item_number.desc())
        .limit(1)
        .scalar()
    )
    return (max_number or 0) + 1


def item_code(prefix: str | None, number: int | None) -> str | None:
    if not prefix or number is None:
        return None
    return f"{prefix}-{number}"
