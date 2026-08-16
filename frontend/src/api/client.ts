import type {Dashboard,Invoice,InvoiceDetail,InvoiceStatus,PurchaseOrder,Vendor} from '../types'
const API=import.meta.env.VITE_API_URL ?? '/api'
async function request<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(`${API}${path}`,init);if(!response.ok){let message='Something went wrong.';try{message=(await response.json()).detail??message}catch{}throw new Error(message)}return response.json()}
export const api={
 dashboard:()=>request<Dashboard>('/dashboard'),
 invoices:(status?:InvoiceStatus)=>request<Invoice[]>(`/invoices${status?`?status=${status}`:''}`),
 invoice:(id:string|number)=>request<InvoiceDetail>(`/invoices/${id}`),
 upload:(file:File)=>{const body=new FormData();body.append('file',file);return request<InvoiceDetail>('/invoices/upload',{method:'POST',body})},
 review:(id:number,action:'approve'|'reject')=>request<InvoiceDetail>(`/invoices/${id}/${action}`,{method:'POST'}),
 purchaseOrders:()=>request<PurchaseOrder[]>('/purchase-orders'),vendors:()=>request<Vendor[]>('/vendors')}

