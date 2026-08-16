import {Link} from 'react-router-dom'
import type {Invoice} from '../types'
import {StatusBadge} from './StatusBadge'
export const money=(value:string|null)=>value?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value)):'—'
export const shortDate=(value:string)=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric'}).format(new Date(value))
export function InvoiceTable({invoices}:{invoices:Invoice[]}){return <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Vendor</th><th>Amount</th><th>Status</th><th>Created</th><th/></tr></thead><tbody>{invoices.map(i=><tr key={i.id}><td className="primary">{i.invoice_number??'Pending details'}</td><td>{i.vendor_name??'Not available'}</td><td>{money(i.total_amount)}</td><td><StatusBadge status={i.status}/></td><td>{shortDate(i.created_at)}</td><td><Link className="row-link" to={`/invoices/${i.id}`}>View →</Link></td></tr>)}</tbody></table>{!invoices.length&&<div className="empty">No invoices match this view.</div>}</div>}

