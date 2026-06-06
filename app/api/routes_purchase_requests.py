from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.schemas.purchase_request_schema import (
    PurchaseRequestAdminOut,
    PurchaseRequestCountOut,
    PurchaseRequestCreate,
    PurchaseRequestPublicOut,
)
from app.services import purchase_request_service
from app.services.auth_service import get_current_admin

router = APIRouter(tags=["Purchase Requests"])


@router.post(
    "/purchase-requests",
    response_model=PurchaseRequestPublicOut,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_request(
    data: PurchaseRequestCreate,
    db: Session = Depends(get_db),
):
    return purchase_request_service.create_request(db, data)


@router.get("/admin/purchase-requests", response_model=List[PurchaseRequestAdminOut])
def admin_list_purchase_requests(
    status_filter: str = Query(default="pending", alias="status"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return purchase_request_service.list_admin_requests(db, status_filter)


@router.get("/admin/purchase-requests/count", response_model=PurchaseRequestCountOut)
def admin_purchase_request_count(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return PurchaseRequestCountOut(pending=purchase_request_service.pending_count(db))


@router.patch("/admin/purchase-requests/{request_id}/accept", response_model=PurchaseRequestAdminOut)
def admin_accept_purchase_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return purchase_request_service.accept_request(db, request_id, admin)


@router.patch("/admin/purchase-requests/{request_id}/decline", response_model=PurchaseRequestAdminOut)
def admin_decline_purchase_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return purchase_request_service.decline_request(db, request_id, admin)
