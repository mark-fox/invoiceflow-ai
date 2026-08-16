import {ArrowLeft, CalendarDays, Check, Download, FileText, Landmark, ReceiptText, X} from 'lucide-react'
import {useState} from 'react'
import {Link, useParams} from 'react-router-dom'

import {api} from '../api/client'
import {money, shortDate} from '../components/InvoiceTable'
import {ErrorState, Loading} from '../components/Loading'
import {StatusBadge} from '../components/StatusBadge'
import {useLoad} from '../hooks'

export function InvoiceDetailPage() {
  const {id = ''} = useParams()
  const {data, error, loading, setData} = useLoad(() => api.invoice(id), [id])
  const [busy, setBusy] = useState(false)
  const [reviewError, setReviewError] = useState('')

  async function review(action: 'approve' | 'reject') {
    if (!data) return
    setBusy(true)
    setReviewError('')
    try {
      setData(await api.review(data.id, action))
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : 'Unable to update the invoice.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error} />

  const confidence = data.extraction_confidence
    ? `${Math.round(Number(data.extraction_confidence) * 100)}%`
    : 'Not available'

  return <>
    <Link className="back" to="/invoices"><ArrowLeft size={16}/>Back to invoices</Link>
    <div className="detail-head">
      <div><span className="eyebrow">INVOICE RECORD</span><h1>{data.invoice_number ?? `Invoice #${data.id}`}</h1><p>Created {shortDate(data.created_at)}</p></div>
      <div className="detail-actions">
        <a className="button secondary" href={api.invoiceFileUrl(data.id)}><Download size={17}/>Source file</a>
        <StatusBadge status={data.status}/>
        {data.status === 'NEEDS_REVIEW' && <>
          <button disabled={busy} className="button danger" onClick={() => review('reject')}><X size={17}/>Reject</button>
          <button disabled={busy} className="button success" onClick={() => review('approve')}><Check size={17}/>Approve</button>
        </>}
      </div>
    </div>
    {reviewError && <div className="inline-error review-error">{reviewError}</div>}
    <div className="detail-grid">
      <div>
        <section className="panel info-panel">
          <div className="panel-head"><h2>Invoice information</h2><FileText size={19}/></div>
          <div className="facts">
            <Fact label="Vendor" value={data.vendor_name}/><Fact label="Invoice number" value={data.invoice_number}/>
            <Fact label="Invoice date" value={data.invoice_date ? shortDate(data.invoice_date) : null}/><Fact label="Total amount" value={money(data.total_amount)}/>
            <Fact label="PO number" value={data.po_number}/><Fact label="Extraction confidence" value={confidence}/>
          </div>
        </section>
        {data.purchase_order && <section className="panel info-panel">
          <div className="panel-head"><h2>Matching purchase order</h2><Landmark size={19}/></div>
          <div className="facts">
            <Fact label="PO number" value={data.purchase_order.po_number}/><Fact label="Vendor" value={data.purchase_order.vendor.name}/>
            <Fact label="PO total" value={money(data.purchase_order.total_amount)}/><Fact label="Status" value={data.purchase_order.status.replaceAll('_', ' ')}/>
          </div>
        </section>}
        <section className="panel info-panel">
          <div className="panel-head"><h2>Exceptions</h2><ReceiptText size={19}/></div>
          {data.exceptions.length ? data.exceptions.map(exception => <div className="exception" key={exception.id}>
            <b>{exception.exception_type.replaceAll('_', ' ')}</b><p>{exception.description}</p>
            {(exception.expected_value || exception.actual_value) && <div><span>Expected: {exception.expected_value ?? '—'}</span><span>Actual: {exception.actual_value ?? '—'}</span></div>}
          </div>) : <div className="empty compact">No exceptions recorded.</div>}
        </section>
      </div>
      <section className="panel timeline-panel">
        <div className="panel-head"><div><h2>Audit history</h2><p>Complete chronological record</p></div><CalendarDays size={19}/></div>
        <div className="timeline">{data.audit_events.map(event => <div className="timeline-item" key={event.id}>
          <i/><div><b>{event.event_type.replaceAll('_', ' ')}</b><p>{event.message}</p><span>{new Date(event.created_at).toLocaleString()}</span></div>
        </div>)}</div>
      </section>
    </div>
  </>
}

function Fact({label, value}: {label: string; value: string | null | undefined}) {
  return <div><span>{label}</span><b>{value ?? 'Not available'}</b></div>
}
