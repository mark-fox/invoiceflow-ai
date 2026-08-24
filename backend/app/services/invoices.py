from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditEvent, Invoice, InvoiceException, InvoiceStatus
from app.schemas.models import ProcessingResultIn

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/tiff"}
ALLOWED_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "image/tiff": {".tif", ".tiff"},
}
MAX_FILE_SIZE = 15 * 1024 * 1024


def save_upload(db: Session, upload: UploadFile) -> Invoice:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload a PDF, JPEG, PNG, WebP, or TIFF file.")
    suffix = Path(upload.filename or "invoice").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS[upload.content_type]:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The filename extension does not match the uploaded file type.")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / f"{uuid4().hex}{suffix}"
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := upload.file.read(1024 * 1024):
                if size == 0 and not _has_expected_signature(chunk, upload.content_type):
                    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The file contents do not match the declared file type.")
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="File exceeds the 15 MB limit.")
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    invoice = Invoice(file_path=str(destination), status=InvoiceStatus.UPLOADED)
    db.add(invoice)
    db.flush()
    db.add(AuditEvent(invoice_id=invoice.id, event_type="INVOICE_UPLOADED", message=f"Invoice file '{upload.filename}' was uploaded.", event_metadata={"original_filename": upload.filename, "content_type": upload.content_type, "size_bytes": size}))
    try:
        db.commit()
        db.refresh(invoice)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return invoice


def review_invoice(db: Session, invoice: Invoice, new_status: InvoiceStatus) -> Invoice:
    if invoice.status != InvoiceStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail="Only invoices needing review can be approved or rejected.")
    invoice.status = new_status
    verb = "approved" if new_status == InvoiceStatus.APPROVED else "rejected"
    db.add(AuditEvent(invoice_id=invoice.id, event_type=f"INVOICE_{new_status.value}", message=f"Invoice was manually {verb}."))
    db.commit()
    db.refresh(invoice)
    return invoice


def start_invoice_processing(
    db: Session, invoice: Invoice, idempotency_key: str
) -> Invoice:
    if invoice.status == InvoiceStatus.PROCESSING:
        if invoice.processing_idempotency_key == idempotency_key:
            return invoice
        raise HTTPException(
            status_code=409,
            detail="Invoice processing was already started with a different idempotency key.",
        )
    if invoice.status != InvoiceStatus.UPLOADED:
        raise HTTPException(status_code=409, detail="Only uploaded invoices can start processing.")
    invoice.processing_idempotency_key = idempotency_key
    invoice.status = InvoiceStatus.PROCESSING
    db.add(
        AuditEvent(
            invoice_id=invoice.id,
            event_type="INVOICE_PROCESSING_STARTED",
            message="Automated invoice processing started.",
            event_metadata={"idempotency_key": idempotency_key},
        )
    )
    try:
        db.commit()
        db.refresh(invoice)
    except Exception:
        db.rollback()
        raise
    return invoice


def apply_processing_result(
    db: Session,
    invoice: Invoice,
    result: ProcessingResultIn,
    idempotency_key: str,
) -> Invoice:
    automation_terminal_statuses = {
        InvoiceStatus.CLEARED,
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.FAILED,
    }
    if invoice.processing_idempotency_key != idempotency_key:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key does not match the active invoice processing run.",
        )
    if invoice.status in automation_terminal_statuses:
        return invoice
    if invoice.status != InvoiceStatus.PROCESSING:
        raise HTTPException(
            status_code=409,
            detail="Processing results can only be applied to invoices currently processing.",
        )

    invoice.invoice_number = result.invoice_number
    invoice.vendor_name = result.vendor_name
    invoice.po_number = result.po_number
    invoice.invoice_date = result.invoice_date
    invoice.total_amount = result.total_amount
    invoice.extraction_confidence = result.extraction_confidence
    invoice.status = result.status

    db.add_all(
        [
            InvoiceException(
                invoice_id=invoice.id,
                exception_type=processing_exception.exception_type,
                description=processing_exception.description,
                expected_value=processing_exception.expected_value,
                actual_value=processing_exception.actual_value,
            )
            for processing_exception in result.exceptions
        ]
    )
    db.add(
        AuditEvent(
            invoice_id=invoice.id,
            event_type="INVOICE_PROCESSING_COMPLETED",
            message=f"Invoice processing completed with status {result.status.value}.",
            event_metadata={
                "resulting_status": result.status.value,
                "exception_count": len(result.exceptions),
            },
        )
    )

    try:
        db.commit()
        db.refresh(invoice)
    except Exception:
        db.rollback()
        raise
    return invoice


def _has_expected_signature(content: bytes, content_type: str) -> bool:
    if content_type == "application/pdf":
        return content.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if content_type == "image/tiff":
        return content.startswith((b"II*\x00", b"MM\x00*"))
    return False
