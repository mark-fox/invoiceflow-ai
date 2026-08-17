from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditEvent, Invoice, InvoiceStatus

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


def start_invoice_processing(db: Session, invoice: Invoice) -> Invoice:
    if invoice.status != InvoiceStatus.UPLOADED:
        raise HTTPException(status_code=409, detail="Only uploaded invoices can start processing.")
    invoice.status = InvoiceStatus.PROCESSING
    db.add(
        AuditEvent(
            invoice_id=invoice.id,
            event_type="INVOICE_PROCESSING_STARTED",
            message="Automated invoice processing started.",
        )
    )
    db.commit()
    db.refresh(invoice)
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
