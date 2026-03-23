import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.schemas.batch_schema import BatchCreate, BatchParseResponse
from app.schemas.item_schema import ItemAdminOut
from app.services import batch_service
from app.services.auth_service import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Batch"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB — purchase sheets can be large photos


@router.post("/parse-batch-image", response_model=BatchParseResponse)
async def parse_batch_image(
    file: UploadFile = File(...),
    batch_type: str = Form(default="metal"),
    _: Admin = Depends(get_current_admin),
):
    """
    Upload a photo of a purchase sheet. Returns enriched rows for admin review.
    Nothing is saved to the database — this is a preview-only endpoint.
    """
    if not any((file.content_type or "").startswith(t) for t in ALLOWED_TYPES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WEBP.",
        )

    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be under 20 MB.",
        )

    try:
        return batch_service.parse_batch_image(
            image_bytes=contents,
            content_type=file.content_type,
            filename=file.filename or "batch-upload",
            batch_type=batch_type,
        )
    except ValueError as exc:
        logger.warning("parse_batch_image failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("parse_batch_image unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to process image. Please try again.",
        )


@router.post("/items/batch", response_model=List[ItemAdminOut], status_code=status.HTTP_201_CREATED)
def create_batch_items(
    data: BatchCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """
    Save the admin-reviewed batch rows as new inventory items.
    All rows are created in a single transaction — if any row fails, none are saved.
    """
    try:
        return batch_service.create_batch_items(db, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("create_batch_items unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save batch items. Please try again.",
        )
