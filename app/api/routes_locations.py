from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.admin_model import Admin
from app.models.item_model import Item
from app.models.purchase_location_model import PurchaseLocation
from app.schemas.purchase_location_schema import PurchaseLocationCreate, PurchaseLocationOut
from app.services.auth_service import get_current_admin

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("", response_model=List[PurchaseLocationOut])
def list_locations(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Returns all purchase locations, ordered by name."""
    return db.query(PurchaseLocation).order_by(PurchaseLocation.name).all()


@router.post("", response_model=PurchaseLocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    data: PurchaseLocationCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
    if db.query(PurchaseLocation).filter(PurchaseLocation.name == name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Location already exists")
    loc = PurchaseLocation(name=name)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    loc = db.query(PurchaseLocation).filter(PurchaseLocation.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    if db.query(Item).filter(Item.purchase_location_id == location_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a location that is assigned to items",
        )
    db.delete(loc)
    db.commit()
