from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.item_schema import ItemPublicOut
from app.services import item_service

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("", response_model=List[ItemPublicOut])
def list_items(
    lang: str = Query(default="en", pattern="^(en|es)$"),
    db: Session = Depends(get_db),
):
    return item_service.get_public_items(db, lang)


@router.get("/{item_id}", response_model=ItemPublicOut)
def get_item(
    item_id: int,
    lang: str = Query(default="en", pattern="^(en|es)$"),
    db: Session = Depends(get_db),
):
    return item_service.get_public_item(db, item_id, lang)
