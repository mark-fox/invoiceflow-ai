from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import PurchaseOrder
from app.schemas.models import PurchaseOrderOut

router = APIRouter()


@router.get("", response_model=list[PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db)) -> list[PurchaseOrder]:
    return list(db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor)).order_by(PurchaseOrder.created_at.desc())).all())

