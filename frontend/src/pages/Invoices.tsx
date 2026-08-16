import {Upload} from 'lucide-react'
import {useState} from 'react'
import {Link} from 'react-router-dom'
import {api} from '../api/client'
import {InvoiceTable} from '../components/InvoiceTable'
import {ErrorState,Loading} from '../components/Loading'
import {useLoad} from '../hooks'
import type {InvoiceStatus} from '../types'
const statuses=['ALL','UPLOADED','PROCESSING','CLEARED','NEEDS_REVIEW','APPROVED','REJECTED','FAILED'] as const
export function Invoices(){const [status,setStatus]=useState<(typeof statuses)[number]>('ALL');const {data,error,loading}=useLoad(()=>api.invoices(status==='ALL'?undefined:status as InvoiceStatus),[status]);return <><div className="page-head"><div><span className="eyebrow">ACCOUNTS PAYABLE</span><h1>Invoices</h1><p>Monitor and review every invoice in one place.</p></div><Link className="button" to="/invoices/upload"><Upload size={18}/>Upload invoice</Link></div><div className="filter-bar"><label>Status</label><select value={status} onChange={e=>setStatus(e.target.value as typeof status)}>{statuses.map(s=><option key={s} value={s}>{s.replaceAll('_',' ')}</option>)}</select></div><section className="panel">{loading?<Loading/>:error?<ErrorState message={error}/>:<InvoiceTable invoices={data??[]}/>}</section></>}

