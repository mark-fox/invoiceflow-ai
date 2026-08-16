from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditEvent, Invoice, InvoiceStatus

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/tiff"}
MAX_FILE_SIZE = 15 * 1024 * 1024


def save_upload(db: Session, upload: UploadFile) -> Invoice:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload a PDF, JPEG, PNG, WebP, or TIFF file.")
    suffix = Path(upload.filename or "invoice").suffix.lower()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / f"{uuid4().hex}{suffix}"
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="File exceeds the 15 MB limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    invoice = Invoice(file_path=str(destination), status=InvoiceStatus.UPLOADED)
    db.add(invoice)
    db.flush()
    db.add(AuditEvent(invoice_id=invoice.id, event_type="INVOICE_UPLOADED", message=f"Invoice file '{upload.filename}' was uploaded.", event_metadata={"original_filename": upload.filename, "content_type": upload.content_type, "size_bytes": size}))
    db.commit()
    db.refresh(invoice)
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
