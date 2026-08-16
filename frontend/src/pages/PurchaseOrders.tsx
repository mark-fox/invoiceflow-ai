import {api} from '../api/client'
import {money,shortDate} from '../components/InvoiceTable'
import {ErrorState,Loading} from '../components/Loading'
import {StatusBadge} from '../components/StatusBadge'
import {useLoad} from '../hooks'
export function PurchaseOrders(){const {data,error,loading}=useLoad(api.purchaseOrders);return <><div className="page-head"><div><span className="eyebrow">PROCUREMENT</span><h1>Purchase orders</h1><p>Reference purchasing commitments and vendor relationships.</p></div></div><section className="panel">{loading?<Loading/>:error?<ErrorState message={error}/>:<div className="table-wrap"><table><thead><tr><th>PO number</th><th>Vendor</th><th>Total amount</th><th>Status</th><th>Created</th></tr></thead><tbody>{data?.map(po=><tr key={po.id}><td className="primary">{po.po_number}</td><td>{po.vendor.name}</td><td>{money(po.total_amount)}</td><td><StatusBadge status={po.status}/></td><td>{shortDate(po.created_at)}</td></tr>)}</tbody></table></div>}</section></>}

