import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models import Invoice, InvoiceStatus, PurchaseOrder
from app.schemas.models import (
    DuplicateCheckOut,
    InvoiceDetail,
    InvoiceListItem,
    ProcessingDispatchOut,
    ProcessingResultIn,
)
from app.services.invoices import (
    apply_processing_result,
    dispatch_invoice_uploaded,
    review_invoice,
    save_upload,
    start_invoice_processing,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[InvoiceListItem])
def list_invoices(status: InvoiceStatus | None = None, db: Session = Depends(get_db)) -> list[Invoice]:
    query = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        query = query.where(Invoice.status == status)
    return list(db.scalars(query).all())


@router.post("/upload", response_model=InvoiceDetail, status_code=201)
async def upload_invoice(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> InvoiceDetail:
    invoice = save_upload(db, file)
    try:
        await dispatch_invoice_uploaded(invoice.id)
    except httpx.HTTPError:
        logger.exception(
            "Failed to dispatch uploaded invoice %s to n8n; invoice remains uploaded.",
            invoice.id,
        )
    return _detail(db, invoice.id)


@router.get("/duplicate-check", response_model=DuplicateCheckOut)
def check_duplicate_invoice(
    invoice_number: str,
    vendor_name: str,
    exclude_invoice_id: int | None = None,
    db: Session = Depends(get_db),
) -> DuplicateCheckOut:
    query = select(Invoice).where(
        Invoice.invoice_number == invoice_number,
        Invoice.vendor_name == vendor_name,
    )
    if exclude_invoice_id is not None:
        query = query.where(Invoice.id != exclude_invoice_id)
    matching_invoice = db.scalar(query.order_by(Invoice.id.asc()).limit(1))
    return DuplicateCheckOut(
        is_duplicate=matching_invoice is not None,
        matching_invoice_id=matching_invoice.id if matching_invoice else None,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    return _detail(db, invoice_id)


@router.get("/{invoice_id}/file", response_class=FileResponse)
def download_invoice_file(invoice_id: int, db: Session = Depends(get_db)) -> FileResponse:
    invoice = _get(db, invoice_id)
    upload_root = settings.upload_dir.resolve()
    file_path = Path(invoice.file_path).resolve()
    if not file_path.is_relative_to(upload_root) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Invoice file is not available.")
    return FileResponse(file_path, filename=file_path.name)


@router.post(
    "/{invoice_id}/processing/dispatch", response_model=ProcessingDispatchOut
)
async def dispatch_processing(
    invoice_id: int, db: Session = Depends(get_db)
) -> ProcessingDispatchOut:
    invoice = _get(db, invoice_id)
    if invoice.status != InvoiceStatus.UPLOADED:
        raise HTTPException(
            status_code=409,
            detail="Only uploaded invoices can be dispatched for processing.",
        )
    try:
        await dispatch_invoice_uploaded(invoice.id)
    except httpx.HTTPError as exc:
        logger.exception(
            "Failed to dispatch invoice %s to n8n; invoice remains uploaded for retry.",
            invoice.id,
        )
        raise HTTPException(
            status_code=502,
            detail="Invoice workflow dispatch failed.",
        ) from exc
    return ProcessingDispatchOut(dispatched=True, invoice_id=invoice.id)


@router.post("/{invoice_id}/processing/start", response_model=InvoiceDetail)
def start_processing(
    invoice_id: int,
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=1, max_length=255
    ),
    db: Session = Depends(get_db),
) -> InvoiceDetail:
    invoice = _get(db, invoice_id, for_update=True)
    start_invoice_processing(db, invoice, idempotency_key)
    return _detail(db, invoice_id)


@router.post("/{invoice_id}/processing/result", response_model=InvoiceDetail)
def submit_processing_result(
    invoice_id: int,
    result: ProcessingResultIn,
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=1, max_length=255
    ),
    db: Session = Depends(get_db),
) -> InvoiceDetail:
    invoice = _get(db, invoice_id, for_update=True)
    apply_processing_result(db, invoice, result, idempotency_key)
    return _detail(db, invoice_id)


@router.post("/{invoice_id}/approve", response_model=InvoiceDetail)
def approve_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    invoice = _get(db, invoice_id, for_update=True)
    review_invoice(db, invoice, InvoiceStatus.APPROVED)
    return _detail(db, invoice_id)


@router.post("/{invoice_id}/reject", response_model=InvoiceDetail)
def reject_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDetail:
    invoice = _get(db, invoice_id, for_update=True)
    review_invoice(db, invoice, InvoiceStatus.REJECTED)
    return _detail(db, invoice_id)


def _get(db: Session, invoice_id: int, *, for_update: bool = False) -> Invoice:
    query = select(Invoice).where(Invoice.id == invoice_id)
    if for_update:
        query = query.with_for_update()
    invoice = db.scalar(query)
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
