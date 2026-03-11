import logging
from typing import List

import bcrypt
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.schemas.admin_schema import AdminLogin, TokenOut
from app.schemas.item_schema import ItemAdminOut, ItemCreate, ItemStatusUpdate, ItemUpdate, UnitAdjust
from app.services import item_service
from app.services.auth_service import get_current_admin
from app.services.cloudinary_service import upload_image
from app.utils.limiter import limiter
from app.utils.security import create_access_token, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

# Pre-computed dummy hash — used so bcrypt always runs on login, preventing timing attacks.
_DUMMY_HASH: str = bcrypt.hashpw(b"dummy-timing-guard", bcrypt.gensalt(rounds=12)).decode()


# ── Authentication ─────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
def login(request: Request, payload: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == payload.username).first()
    # Always run bcrypt regardless of whether the admin exists — prevents timing attacks.
    hash_to_check = admin.password_hash if admin else _DUMMY_HASH
    password_ok = verify_password(payload.password, hash_to_check)
    if not admin or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": str(admin.id), "username": admin.username})
    return TokenOut(access_token=token)


# ── Image upload ───────────────────────────────────────────────────────────

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-image")
async def upload_item_image(
    file: UploadFile = File(...),
    _: Admin = Depends(get_current_admin),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WEBP.",
        )

    contents = await file.read()

    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be under 10 MB.",
        )

    try:
        url = upload_image(contents, file.filename or "upload")
    except Exception as exc:
        logger.error("Image upload failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image upload failed. Please try again.",
        )

    return {"url": url}


# ── Item management (protected) ────────────────────────────────────────────

@router.get("/items", response_model=List[ItemAdminOut])
def admin_list_items(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    from app.models.item_model import Item
    return db.query(Item).order_by(Item.created_at.desc()).all()


@router.post("/items", response_model=ItemAdminOut, status_code=status.HTTP_201_CREATED)
def admin_create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return item_service.create_item(db, data)


@router.put("/items/{item_id}", response_model=ItemAdminOut)
def admin_update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return item_service.update_item(db, item_id, data)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    item_service.delete_item(db, item_id)


@router.patch("/items/{item_id}/units", response_model=ItemAdminOut)
def admin_adjust_units(
    item_id: int,
    data: UnitAdjust,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Move units between available / pending / sold for multi-quantity items."""
    return item_service.adjust_units(db, item_id, data)


@router.post("/items/{item_id}/recalculate-price", response_model=ItemAdminOut)
def admin_recalculate_item_price(
    item_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Recalculate price for a single metal item using current spot price."""
    from app.services import price_sync_service
    try:
        return price_sync_service.recalculate_one(db, item_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price recalculation failed — item may not have metal pricing configured.",
        )


@router.patch("/items/{item_id}/status", response_model=ItemAdminOut)
def admin_update_status(
    item_id: int,
    data: ItemStatusUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return item_service.update_item_status(db, item_id, data.status, data.sell_price)
