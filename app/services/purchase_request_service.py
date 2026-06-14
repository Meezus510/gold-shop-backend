from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admin_model import Admin
from app.models.customer_model import Customer
from app.models.item_model import Item, ItemStatus
from app.models.purchase_request_model import PurchaseRequest, PurchaseRequestStatus
from app.schemas.purchase_request_schema import PurchaseRequestAdminOut, PurchaseRequestCreate
from app.services.pii_crypto_service import decrypt_text, encrypt_text, normalize_phone, phone_hash


def _resolve_item_name(item: Item) -> str:
    translation = next((t for t in item.translations if t.language == "es"), None)
    if not translation:
        translation = next((t for t in item.translations if t.language == "en"), None)
    if not translation and item.translations:
        translation = item.translations[0]
    return translation.name if translation else f"Item {item.item_id}"


def _recompute_status(item: Item) -> None:
    if item.quantity_available > 0:
        item.status = ItemStatus.AVAILABLE
    elif item.quantity_pending > 0:
        item.status = ItemStatus.SALE_PENDING
    else:
        item.status = ItemStatus.SOLD


def _admin_out(request: PurchaseRequest) -> PurchaseRequestAdminOut:
    return PurchaseRequestAdminOut(
        id=request.id,
        status=request.status,
        item_id=request.item_id,
        item_number_prefix_snapshot=request.item_number_prefix_snapshot,
        item_number_snapshot=request.item_number_snapshot,
        item_code_snapshot=(
            f"{request.item_number_prefix_snapshot}-{request.item_number_snapshot}"
            if request.item_number_prefix_snapshot and request.item_number_snapshot is not None
            else None
        ),
        item_name_snapshot=request.item_name_snapshot,
        listed_price_snapshot=request.listed_price_snapshot,
        customer_name=decrypt_text(request.customer.name_encrypted),
        customer_phone=decrypt_text(request.customer.phone_encrypted),
        decided_by_admin_id=request.decided_by_admin_id,
        decided_at=request.decided_at,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _admin_list_out(requests: Iterable[PurchaseRequest]) -> list[PurchaseRequestAdminOut]:
    return [_admin_out(request) for request in requests]


def create_request(db: Session, data: PurchaseRequestCreate) -> PurchaseRequest:
    normalized_phone = normalize_phone(data.phone)
    if len(normalized_phone) < 7:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Phone number is too short")

    item = db.query(Item).filter(Item.item_id == data.item_id).first()
    if not item or not item.is_visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.quantity_available <= 0 or item.status != ItemStatus.AVAILABLE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is not available")

    hashed_phone = phone_hash(normalized_phone)
    customer = db.query(Customer).filter(Customer.phone_hash == hashed_phone).first()
    if customer:
        customer.name_encrypted = encrypt_text(data.name)
        customer.phone_encrypted = encrypt_text(normalized_phone)
    else:
        customer = Customer(
            name_encrypted=encrypt_text(data.name),
            phone_encrypted=encrypt_text(normalized_phone),
            phone_hash=hashed_phone,
        )
        db.add(customer)
        db.flush()

    request = PurchaseRequest(
        customer_id=customer.id,
        item_id=item.item_id,
        item_number_prefix_snapshot=item.item_number_prefix,
        item_number_snapshot=item.item_number,
        item_name_snapshot=_resolve_item_name(item),
        listed_price_snapshot=item.listed_price_flat,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_admin_requests(db: Session, status_filter: str = "pending") -> list[PurchaseRequestAdminOut]:
    query = db.query(PurchaseRequest).order_by(PurchaseRequest.created_at.desc())
    if status_filter != "all":
        try:
            request_status = PurchaseRequestStatus(status_filter.upper())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid request status")
        query = query.filter(PurchaseRequest.status == request_status)
    return _admin_list_out(query.all())


def pending_count(db: Session) -> int:
    return db.query(PurchaseRequest).filter(PurchaseRequest.status == PurchaseRequestStatus.PENDING).count()


def accept_request(db: Session, request_id: int, admin: Admin) -> PurchaseRequestAdminOut:
    request = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if request.status != PurchaseRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request has already been decided")

    item = db.query(Item).filter(Item.item_id == request.item_id).with_for_update().first()
    if not item or item.quantity_available <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is no longer available")

    item.quantity_available -= 1
    item.quantity_pending += 1
    _recompute_status(item)

    request.status = PurchaseRequestStatus.ACCEPTED
    request.decided_by_admin_id = admin.id
    request.decided_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(request)
    return _admin_out(request)


def decline_request(db: Session, request_id: int, admin: Admin) -> PurchaseRequestAdminOut:
    request = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if request.status != PurchaseRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request has already been decided")

    request.status = PurchaseRequestStatus.DECLINED
    request.decided_by_admin_id = admin.id
    request.decided_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(request)
    return _admin_out(request)
