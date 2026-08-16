export type InvoiceStatus='UPLOADED'|'PROCESSING'|'CLEARED'|'NEEDS_REVIEW'|'APPROVED'|'REJECTED'|'FAILED'
export interface Invoice {id:number;invoice_number:string|null;vendor_name:string|null;total_amount:string|null;status:InvoiceStatus;created_at:string}
export interface Vendor {id:number;name:string;vendor_code:string}
export interface PurchaseOrder {id:number;po_number:string;vendor_id:number;total_amount:string;status:string;created_at:string;vendor:Vendor}
export interface InvoiceException {id:number;exception_type:string;description:string;expected_value:string|null;actual_value:string|null;created_at:string}
export interface AuditEvent {id:number;event_type:string;message:string;metadata:Record<string,unknown>|null;created_at:string}
export interface InvoiceDetail extends Invoice {po_number:string|null;invoice_date:string|null;extraction_confidence:string|null;updated_at:string;purchase_order:PurchaseOrder|null;exceptions:InvoiceException[];audit_events:AuditEvent[]}
export interface Dashboard {total_invoices:number;automatically_cleared:number;needs_review:number;approved:number;rejected:number;failed:number;recent_invoices:Invoice[]}
