from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Invoice, InvoiceStatus, PurchaseOrder
from app.schemas.models import InvoiceDetail, InvoiceListItem
from app.services.invoices import review_invoice, save_upload

router = APIRouter()


@router.get("", response_model=list[InvoiceListItem])
def list_invoices(status: InvoiceStatus | None = None, db: Session = Depends(get_db)) -> list[Invoice]:
    query = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        query = query.where(Invoice.status == status)
    return list(db.scalars(query).all())


@router.post("/upload", response_model=InvoiceDetail, status_code=201)
def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)) -> InvoiceDetail:
    invoice = save_upload(db, file)
    return _detail(db, invoice.id)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    return _detail(db, invoice_id)


@router.post("/{invoice_id}/approve", response_model=InvoiceDetail)
def approve_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    invoice = _get(db, invoice_id)
    review_invoice(db, invoice, InvoiceStatus.APPROVED)
    return _detail(db, invoice_id)


@router.post("/{invoice_id}/reject", response_model=InvoiceDetail)
def reject_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    invoice = _get(db, invoice_id)
    review_invoice(db, invoice, InvoiceStatus.REJECTED)
    return _detail(db, invoice_id)


def _get(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


def _detail(db: Session, invoice_id: int) -> InvoiceDetail:
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.exceptions), selectinload(Invoice.audit_events)))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    purchase_order = db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == invoice.po_number).options(selectinload(PurchaseOrder.vendor))) if invoice.po_number else None
    payload = InvoiceDetail.model_validate(invoice)
    if purchase_order:
        from app.schemas.models import PurchaseOrderOut
        payload.purchase_order = PurchaseOrderOut.model_validate(purchase_order)
    payload.exceptions.sort(key=lambda item: item.created_at)
    payload.audit_events.sort(key=lambda item: item.created_at)
    return payload
