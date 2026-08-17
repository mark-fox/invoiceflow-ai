from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import PurchaseOrder
from app.schemas.models import PurchaseOrderOut

router = APIRouter()


@router.get("", response_model=list[PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db)) -> list[PurchaseOrder]:
    return list(db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor)).order_by(PurchaseOrder.created_at.desc())).all())


@router.get("/by-number/{po_number}", response_model=PurchaseOrderOut)
def get_purchase_order_by_number(
    po_number: str, db: Session = Depends(get_db)
) -> PurchaseOrder:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number == po_number)
        .options(selectinload(PurchaseOrder.vendor))
    )
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return purchase_order
