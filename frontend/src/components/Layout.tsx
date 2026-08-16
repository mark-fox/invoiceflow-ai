import {FileText,LayoutDashboard,Menu,PackageCheck,Users,X} from 'lucide-react'
import {useState} from 'react'
import {NavLink,Outlet} from 'react-router-dom'
const nav=[['/',LayoutDashboard,'Dashboard'],['/invoices',FileText,'Invoices'],['/purchase-orders',PackageCheck,'Purchase Orders'],['/vendors',Users,'Vendors']] as const
export function Layout(){const [open,setOpen]=useState(false);return <div className="app"><aside className={open?'open':''}><div className="brand"><span>IF</span><div>InvoiceFlow<small>ACCOUNTS PAYABLE</small></div></div><button className="close" onClick={()=>setOpen(false)}><X/></button><nav>{nav.map(([to,Icon,label])=><NavLink key={to} end={to==='/'} to={to} onClick={()=>setOpen(false)}><Icon size={19}/>{label}</NavLink>)}</nav><div className="phase"><b>Phase 1</b><span>Core application</span></div></aside><main><header><button className="menu" onClick={()=>setOpen(true)}><Menu/></button><div><span className="eyebrow">OPERATIONS WORKSPACE</span></div><div className="avatar">AP</div></header><div className="content"><Outlet/></div></main>{open&&<div className="scrim" onClick={()=>setOpen(false)}/>}</div>}

