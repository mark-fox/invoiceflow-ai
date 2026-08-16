import {AlertTriangle,CheckCircle2,FileStack,ShieldCheck,ThumbsDown,XCircle} from 'lucide-react'
import {api} from '../api/client'
import {InvoiceTable} from '../components/InvoiceTable'
import {ErrorState,Loading} from '../components/Loading'
import {useLoad} from '../hooks'
const cards=[['total_invoices','Total invoices',FileStack,'blue'],['automatically_cleared','Auto cleared',ShieldCheck,'teal'],['needs_review','Needs review',AlertTriangle,'amber'],['approved','Approved',CheckCircle2,'green'],['rejected','Rejected',ThumbsDown,'slate'],['failed','Failed',XCircle,'red']] as const
export function Dashboard(){const {data,error,loading}=useLoad(api.dashboard);if(loading)return <Loading/>;if(error||!data)return <ErrorState message={error}/>;return <><div className="page-head"><div><span className="eyebrow">OVERVIEW</span><h1>Good morning, AP team</h1><p>Here’s the current state of invoice operations.</p></div></div><section className="metric-grid">{cards.map(([key,label,Icon,tone])=><div className="metric" key={key}><div className={`metric-icon ${tone}`}><Icon size={20}/></div><span>{label}</span><strong>{data[key]}</strong></div>)}</section><section className="panel"><div className="panel-head"><div><h2>Recent invoices</h2><p>Latest activity across the invoice queue</p></div><a href="/invoices">View all invoices →</a></div><InvoiceTable invoices={data.recent_invoices}/></section></>}

