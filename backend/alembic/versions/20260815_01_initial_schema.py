"""Initial InvoiceFlow schema."""
from alembic import op
import sqlalchemy as sa

revision = "20260815_01"
down_revision = None
branch_labels = None
depends_on = None

invoice_status = sa.Enum("UPLOADED", "PROCESSING", "CLEARED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "FAILED", name="invoice_status")
po_status = sa.Enum("OPEN", "PARTIALLY_INVOICED", "CLOSED", "CANCELLED", name="purchase_order_status")
exception_type = sa.Enum("AMOUNT_MISMATCH", "UNKNOWN_PO", "DUPLICATE_INVOICE", "LOW_CONFIDENCE", "MISSING_FIELD", name="exception_type")


def upgrade() -> None:
    op.create_table("vendors", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("vendor_code", sa.String(50), nullable=False), sa.UniqueConstraint("name"), sa.UniqueConstraint("vendor_code"))
    op.create_index("ix_vendors_name", "vendors", ["name"])
    op.create_index("ix_vendors_vendor_code", "vendors", ["vendor_code"])
    op.create_table("purchase_orders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("po_number", sa.String(50), nullable=False), sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False), sa.Column("total_amount", sa.Numeric(12, 2), nullable=False), sa.Column("status", po_status, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("po_number"))
    op.create_index("ix_purchase_orders_po_number", "purchase_orders", ["po_number"])
    op.create_index("ix_purchase_orders_vendor_id", "purchase_orders", ["vendor_id"])
    op.create_table("invoices", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("invoice_number", sa.String(100)), sa.Column("vendor_name", sa.String(200)), sa.Column("po_number", sa.String(50)), sa.Column("invoice_date", sa.Date()), sa.Column("total_amount", sa.Numeric(12, 2)), sa.Column("file_path", sa.String(500), nullable=False), sa.Column("extraction_confidence", sa.Numeric(5, 4)), sa.Column("status", invoice_status, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for column in ("invoice_number", "vendor_name", "po_number", "status"):
        op.create_index(f"ix_invoices_{column}", "invoices", [column])
    op.create_table("invoice_exceptions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False), sa.Column("exception_type", exception_type, nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("expected_value", sa.String(255)), sa.Column("actual_value", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_invoice_exceptions_invoice_id", "invoice_exceptions", ["invoice_id"])
    op.create_table("audit_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_events_invoice_id", "audit_events", ["invoice_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("invoice_exceptions")
    op.drop_table("invoices")
    op.drop_table("purchase_orders")
    op.drop_table("vendors")
    exception_type.drop(op.get_bind())
    invoice_status.drop(op.get_bind())
    po_status.drop(op.get_bind())

