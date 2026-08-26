export type InvoiceStatus='UPLOADED'|'PROCESSING'|'CLEARED'|'NEEDS_REVIEW'|'APPROVED'|'REJECTED'|'FAILED'
export interface Invoice {id:number;invoice_number:string|null;vendor_name:string|null;total_amount:string|null;status:InvoiceStatus;created_at:string}
export interface Vendor {id:number;name:string;vendor_code:string}
export interface PurchaseOrder {id:number;po_number:string;vendor_id:number;total_amount:string;status:string;created_at:string;vendor:Vendor}
export interface InvoiceException {id:number;exception_type:string;description:string;expected_value:string|null;actual_value:string|null;created_at:string}
export interface AuditEvent {id:number;event_type:string;message:string;metadata:Record<string,unknown>|null;created_at:string}
export interface InvoiceDetail extends Invoice {po_number:string|null;invoice_date:string|null;extraction_confidence:string|null;updated_at:string;purchase_order:PurchaseOrder|null;exceptions:InvoiceException[];audit_events:AuditEvent[]}
export interface ProcessingDispatch {dispatched:boolean;invoice_id:number}
export interface Dashboard {total_invoices:number;automatically_cleared:number;needs_review:number;approved:number;rejected:number;failed:number;recent_invoices:Invoice[]}
export interface AutomationSummary {
  invoice_counts: {
    total: number
    uploaded: number
    processing: number
    cleared: number
    needs_review: number
    failed: number
    approved: number
    rejected: number
  }
  exception_counts: Record<'AMOUNT_MISMATCH'|'UNKNOWN_PO'|'DUPLICATE_INVOICE'|'LOW_CONFIDENCE'|'MISSING_FIELD',number>
}
export interface RecentProcessingActivity {
  invoice_id: number
  invoice_number: string|null
  vendor_name: string|null
  status: InvoiceStatus
  completed_at: string
  exception_count: number
}
export interface AutomationMetrics {
  completed_count: number
  auto_cleared_count: number
  needs_review_count: number
  failed_count: number
  auto_clear_rate: number
  review_rate: number
  failure_rate: number
  average_processing_seconds: number|null
}
