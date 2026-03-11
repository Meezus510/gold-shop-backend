from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.schemas.admin_schema import AdminLogin, TokenOut
from app.schemas.item_schema import ItemAdminOut, ItemCreate, ItemStatusUpdate, ItemUpdate
from app.services import item_service
from app.services.auth_service import get_current_admin
from app.utils.security import create_access_token, verify_password

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Authentication ─────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
def login(payload: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == payload.username).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": str(admin.id), "username": admin.username})
    return TokenOut(access_token=token)


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


@router.patch("/items/{item_id}/status", response_model=ItemAdminOut)
def admin_update_status(
    item_id: int,
    data: ItemStatusUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return item_service.update_item_status(db, item_id, data.status, data.sell_price)
