"""
Batch item processing: image parsing and bulk item creation.
"""
import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.item_image_model import ItemImage
from app.models.item_model import Item, ItemStatus
from app.models.item_translation_model import ItemTranslation
from app.models.metal_model import Metal
from app.models.purchase_location_model import PurchaseLocation
from app.schemas.batch_schema import BatchCreate, BatchParseResponse, BatchRowPreview
from app.services import claude_service
from app.services.cloudinary_service import upload_image
from app.services.metals_price_service import GRAMS_PER_TROY_OZ, get_spot_price

logger = logging.getLogger(__name__)


def parse_batch_image(
    image_bytes: bytes,
    content_type: str,
    filename: str,
    batch_type: str = "metal",
) -> BatchParseResponse:
    """
    Upload image to Cloudinary, extract rows via Claude Vision,
    enrich with translations/category, and return a preview for admin review.
    Nothing is written to the database.
    """
    # Upload source image to Cloudinary for audit trail
    source_url = upload_image(image_bytes, f"batch-source-{filename}")

    # Step 1: OCR extraction — use appropriate prompt based on batch type
    if batch_type == "na":
        raw_rows = claude_service.extract_rows_from_image_na(image_bytes, content_type)
    else:
        raw_rows = claude_service.extract_rows_from_image(image_bytes, content_type)

    # Step 2: Enrich with name/description (ES + EN) and category
    enriched_rows = claude_service.enrich_rows(raw_rows)

    # Step 3: Apply category-based weight defaults for rows missing weight (metal batches only)
    if batch_type != "na":
        for row in enriched_rows:
            if not row.get("weight_grams"):
                cat = (row.get("category") or "").lower()
                default_w = claude_service.CATEGORY_DEFAULT_WEIGHT.get(cat)
                if default_w is not None:
                    row["weight_grams"] = default_w

    preview_rows = [
        BatchRowPreview(
            purchase_date=row.get("purchase_date"),
            purchase_location=row.get("purchase_location"),
            qty=row.get("qty"),
            category=row.get("category"),
            name_es=row.get("name_es"),
            description_es=row.get("description_es"),
            name_en=row.get("name_en"),
            description_en=row.get("description_en"),
            cost=row.get("cost"),
            weight_grams=row.get("weight_grams"),
            listed_price_flat=row.get("listed_price_flat"),
            listed_price_loan=row.get("listed_price_loan"),
        )
        for row in enriched_rows
    ]

    return BatchParseResponse(rows=preview_rows, source_image_url=source_url)


def create_batch_items(db: Session, data: BatchCreate) -> List[Item]:
    """
    Create all confirmed batch rows in a single transaction.

    Metal batches:
    - Fetches the metal spot price once and computes markup_flat / markup_loan.
      markup_flat is above metal value; markup_loan is above flat sale price.
    N/A batches:
    - No metal; listed_price_flat is set directly from the row; no markups.
    """
    is_na = data.batch_type == "na"

    metal = None
    spot_price = None
    if not is_na:
        metal = db.query(Metal).filter(Metal.id == data.metal_id).first()
        if not metal:
            raise ValueError(f"Metal with id={data.metal_id} not found")
        spot_price = get_spot_price(metal.spot_price_api_symbol)

    # Cache location lookups within this batch to avoid redundant queries
    location_id_cache: dict[str, int] = {}

    created_items: List[Item] = []

    for row in data.rows:
        # ── Purchase location ────────────────────────────────────────────────
        location_id: int | None = None
        if row.purchase_location:
            loc_name = row.purchase_location.strip()
            if loc_name not in location_id_cache:
                loc = db.query(PurchaseLocation).filter(
                    PurchaseLocation.name == loc_name
                ).first()
                if not loc:
                    loc = PurchaseLocation(name=loc_name)
                    db.add(loc)
                    db.flush()
                    logger.info("batch: created new purchase_location '%s'", loc_name)
                location_id_cache[loc_name] = loc.id
            location_id = location_id_cache[loc_name]

        # ── Markups (metal batches only) ─────────────────────────────────────
        markup_flat: float | None = None
        markup_loan: float | None = None

        if not is_na and spot_price and row.weight_grams and data.purity_karat:
            base_market = (
                (row.weight_grams / GRAMS_PER_TROY_OZ)
                * spot_price
                * (data.purity_karat / metal.purity_denominator)
            )
            if row.listed_price_flat is not None:
                markup_flat = round(float(row.listed_price_flat) - base_market, 2)
            if row.listed_price_loan is not None:
                flat_price = (
                    float(row.listed_price_flat)
                    if row.listed_price_flat is not None
                    else base_market
                )
                markup_loan = max(round(float(row.listed_price_loan) - flat_price, 2), 0)

        # ── Item ─────────────────────────────────────────────────────────────
        qty = row.qty or 1
        is_sold = row.status == ItemStatus.SOLD
        item = Item(
            category=row.category,
            metal_id=data.metal_id if not is_na else None,
            purity_karat=data.purity_karat if not is_na else None,
            weight_grams=row.weight_grams,
            quantity=qty,
            quantity_available=0 if is_sold else qty,
            quantity_pending=0,
            quantity_sold=qty if is_sold else 0,
            cost=row.cost,
            purchase_date=row.purchase_date,
            purchase_location_id=location_id,
            markup_flat=markup_flat,
            markup_loan=markup_loan,
            listed_price_flat=row.listed_price_flat,
            listed_price_loan=row.listed_price_loan if not is_na else None,
            sell_price=row.sell_price,
            is_visible=False,
            status=row.status,
        )
        db.add(item)
        db.flush()  # get item_id before adding translations

        # ── Translations ─────────────────────────────────────────────────────
        if row.name_es:
            db.add(ItemTranslation(
                item_id=item.item_id,
                language="es",
                name=row.name_es,
                description=row.description_es,
            ))
        if row.name_en:
            db.add(ItemTranslation(
                item_id=item.item_id,
                language="en",
                name=row.name_en,
                description=row.description_en,
            ))

        created_items.append(item)

    db.commit()
    for item in created_items:
        db.refresh(item)

    logger.info("batch: created %d items", len(created_items))
    return created_items
