import {AlertTriangle,CheckCircle2,FileStack,ShieldCheck,ThumbsDown,XCircle} from 'lucide-react'
import {Link} from 'react-router-dom'

import {api} from '../api/client'
import {InvoiceTable} from '../components/InvoiceTable'
import {ErrorState,Loading} from '../components/Loading'
import {StatusBadge} from '../components/StatusBadge'
import {useLoad} from '../hooks'
import type {AutomationMetrics,AutomationSummary,RecentProcessingActivity} from '../types'

const cards=[
  ['total_invoices','Total invoices',FileStack,'blue'],
  ['automatically_cleared','Auto cleared',ShieldCheck,'teal'],
  ['needs_review','Needs review',AlertTriangle,'amber'],
  ['approved','Approved',CheckCircle2,'green'],
  ['rejected','Rejected',ThumbsDown,'slate'],
  ['failed','Failed',XCircle,'red'],
] as const

const automationMetrics=[
  ['total','Total'],
  ['processing','Processing'],
  ['cleared','Cleared'],
  ['needs_review','Needs Review'],
  ['failed','Failed'],
] as const

const exceptionLabels:Array<[keyof AutomationSummary['exception_counts'],string]>=[
  ['AMOUNT_MISMATCH','Amount Mismatch'],
  ['UNKNOWN_PO','Unknown PO'],
  ['DUPLICATE_INVOICE','Duplicate Invoice'],
  ['LOW_CONFIDENCE','Low Confidence'],
  ['MISSING_FIELD','Missing Field'],
]

const percentFormatter=new Intl.NumberFormat('en-US',{style:'percent',maximumFractionDigits:1})
const secondsFormatter=new Intl.NumberFormat('en-US',{maximumFractionDigits:1})

export function Dashboard(){
  const {data,error,loading}=useLoad(api.dashboard)
  const automation=useLoad(api.automationSummary)
  const performance=useLoad(api.automationMetrics)
  const recentProcessing=useLoad(api.recentProcessing)

  if(loading)return <Loading/>
  if(error||!data)return <ErrorState message={error}/>

  return <>
    <div className="page-head">
      <div><span className="eyebrow">OVERVIEW</span><h1>Good morning, AP team</h1><p>Here’s the current state of invoice operations.</p></div>
    </div>
    <section className="metric-grid">
      {cards.map(([key,label,Icon,tone])=><div className="metric" key={key}><div className={`metric-icon ${tone}`}><Icon size={20}/></div><span>{label}</span><strong>{data[key]}</strong></div>)}
    </section>
    <AutomationOverview {...automation}/>
    <AutomationPerformance {...performance}/>
    <RecentProcessing {...recentProcessing}/>
    <section className="panel">
      <div className="panel-head"><div><h2>Recent invoices</h2><p>Latest activity across the invoice queue</p></div><a href="/invoices">View all invoices →</a></div>
      <InvoiceTable invoices={data.recent_invoices}/>
    </section>
  </>
}

function AutomationOverview({data,error,loading}:{data:AutomationSummary|null;error:string;loading:boolean}){
  return <section className="panel automation-overview">
    <div className="panel-head"><div><h2>Automation Overview</h2><p>Current workflow activity and processing exceptions</p></div></div>
    {loading&&<div className="automation-message">Loading automation summary…</div>}
    {!loading&&error&&<div className="inline-error automation-error"><b>Automation summary unavailable</b><span>{error}</span></div>}
    {!loading&&data&&<div className="automation-content">
      <div className="automation-metrics">
        {automationMetrics.map(([key,label])=><div className="automation-metric" key={key}><span>{label}</span><strong>{data.invoice_counts[key]}</strong></div>)}
      </div>
      <div className="exception-breakdown">
        <h3>Exception Breakdown</h3>
        <div>{exceptionLabels.map(([key,label])=><div key={key}><span>{label}</span><strong>{data.exception_counts[key]}</strong></div>)}</div>
      </div>
    </div>}
  </section>
}

function AutomationPerformance({data,error,loading}:{data:AutomationMetrics|null;error:string;loading:boolean}){
  const metrics=data?[
    ['Auto-clear rate',percentFormatter.format(data.auto_clear_rate),`${data.auto_cleared_count} auto-cleared`],
    ['Review rate',percentFormatter.format(data.review_rate),`${data.needs_review_count} reviewed`],
    ['Failure rate',percentFormatter.format(data.failure_rate),`${data.failed_count} failed`],
    ['Average processing time',formatProcessingTime(data.average_processing_seconds),`${data.completed_count} completed`],
  ]:[]

  return <section className="panel automation-performance">
    <div className="panel-head"><div><h2>Automation Performance</h2><p>Processing outcomes and execution speed</p></div></div>
    {loading&&<div className="automation-message">Loading performance metrics…</div>}
    {!loading&&error&&<div className="inline-error automation-error"><b>Performance metrics unavailable</b><span>{error}</span></div>}
    {!loading&&data&&<div className="performance-grid">{metrics.map(([label,value,detail])=><div className="performance-metric" key={label}>
      <span>{label}</span><strong>{value}</strong><small>{detail}</small>
    </div>)}</div>}
  </section>
}

function formatProcessingTime(seconds:number|null){
  if(seconds===null)return 'Not available'
  if(seconds<60)return `${secondsFormatter.format(seconds)} sec`
  const roundedSeconds=Math.round(seconds)
  const minutes=Math.floor(roundedSeconds/60)
  const remainingSeconds=roundedSeconds%60
  return remainingSeconds?`${minutes} min ${remainingSeconds} sec`:`${minutes} min`
}

function RecentProcessing({data,error,loading}:{data:RecentProcessingActivity[]|null;error:string;loading:boolean}){
  return <section className="panel processing-activity">
    <div className="panel-head"><div><h2>Recent Processing Activity</h2><p>Latest completed automation runs</p></div></div>
    {loading&&<div className="automation-message">Loading recent activity…</div>}
    {!loading&&error&&<div className="inline-error automation-error"><b>Recent activity unavailable</b><span>{error}</span></div>}
    {!loading&&data&&data.length===0&&<div className="empty compact">No completed processing activity yet.</div>}
    {!loading&&data&&data.length>0&&<div className="table-wrap"><table>
      <thead><tr><th>Invoice</th><th>Vendor</th><th>Status</th><th>Completed</th><th>Exceptions</th></tr></thead>
      <tbody>{data.map(item=><tr key={`${item.invoice_id}-${item.completed_at}`}>
        <td><Link className="row-link" to={`/invoices/${item.invoice_id}`}>{item.invoice_number??`Invoice #${item.invoice_id}`}</Link></td>
        <td>{item.vendor_name??'Unknown vendor'}</td>
        <td><StatusBadge status={item.status}/></td>
        <td>{new Date(item.completed_at).toLocaleString()}</td>
        <td>{item.exception_count} {item.exception_count===1?'exception':'exceptions'}</td>
      </tr>)}</tbody>
    </table></div>}
  </section>
}
