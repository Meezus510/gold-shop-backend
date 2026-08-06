import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.models.item_model import PricingMode
from app.schemas.item_schema import ItemAdminOut, ItemCreate
from app.schemas.translation_schema import TranslationCreate
from app.services import item_service
from app.services.auth_service import get_current_admin
from app.services.cloudinary_service import upload_image
from app.services.gemini_service import analyze_broquel_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Fast Broquel Intake"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024
LIST_PRICE_MULTIPLIER = Decimal("2")


@router.post(
    "/fast-broquel",
    response_model=ItemAdminOut,
    status_code=status.HTTP_201_CREATED,
)
async def fast_create_broquel(
    file: UploadFile = File(...),
    cost: Decimal = Form(..., ge=0),
    publish: bool = Form(default=True),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Analyze one product photo and immediately create a Broqueles listing."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use a JPEG, PNG, or WEBP image.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The image is empty.",
        )
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be under 10 MB.",
        )

    try:
        analysis = analyze_broquel_image(contents, file.content_type)
        image_url = upload_image(contents, file.filename or "broquel")
        listed_price = (cost * LIST_PRICE_MULTIPLIER).quantize(Decimal("0.01"))
        return item_service.create_item(
            db,
            ItemCreate(
                category="broqueles",
                metal_id=None,
                pricing_mode=PricingMode.MANUAL,
                quantity=1,
                cost=float(cost),
                is_visible=publish,
                listed_price_flat=listed_price,
                image_urls=[image_url],
                translations=[
                    TranslationCreate(
                        language="es",
                        name=analysis.name_es,
                        description=analysis.description_es,
                    ),
                    TranslationCreate(
                        language="en",
                        name=analysis.name_en,
                        description=analysis.description_en,
                    ),
                ],
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Fast Broquel intake failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not analyze and add this item. Please try again.",
        )
