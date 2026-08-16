import {Navigate,Route,Routes} from 'react-router-dom'
import {Layout} from './components/Layout'
import {Dashboard} from './pages/Dashboard'
import {InvoiceDetailPage} from './pages/InvoiceDetail'
import {Invoices} from './pages/Invoices'
import {PurchaseOrders} from './pages/PurchaseOrders'
import {UploadInvoice} from './pages/UploadInvoice'
import {Vendors} from './pages/Vendors'
export default function App(){return <Routes><Route element={<Layout/>}><Route path="/" element={<Dashboard/>}/><Route path="/invoices" element={<Invoices/>}/><Route path="/invoices/upload" element={<UploadInvoice/>}/><Route path="/invoices/:id" element={<InvoiceDetailPage/>}/><Route path="/purchase-orders" element={<PurchaseOrders/>}/><Route path="/vendors" element={<Vendors/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Route></Routes>}

