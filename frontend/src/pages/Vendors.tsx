import {Building2} from 'lucide-react'
import {api} from '../api/client'
import {ErrorState,Loading} from '../components/Loading'
import {useLoad} from '../hooks'
export function Vendors(){const {data,error,loading}=useLoad(api.vendors);return <><div className="page-head"><div><span className="eyebrow">SUPPLIERS</span><h1>Vendors</h1><p>Organizations currently registered for purchasing.</p></div></div>{loading?<Loading/>:error?<ErrorState message={error}/>:<div className="vendor-grid">{data?.map(v=><div className="vendor-card" key={v.id}><div><Building2/></div><section><b>{v.name}</b><span>Vendor code · {v.vendor_code}</span></section></div>)}</div>}</>}

