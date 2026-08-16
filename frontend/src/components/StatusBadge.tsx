import type {InvoiceStatus} from '../types'
export function StatusBadge({status}:{status:string}){return <span className={`badge badge-${status.toLowerCase()}`}><i/>{status.replaceAll('_',' ')}</span>}

