import type {AutomationMetrics,AutomationSummary,Dashboard,Invoice,InvoiceDetail,InvoiceStatus,ProcessingDispatch,PurchaseOrder,RecentProcessingActivity,Vendor} from '../types'
const API=import.meta.env.VITE_API_URL ?? '/api'
async function request<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(`${API}${path}`,init);if(!response.ok){let message='Something went wrong.';try{const detail=(await response.json()).detail;if(typeof detail==='string')message=detail;else if(Array.isArray(detail))message=detail.map(item=>item.msg).filter(Boolean).join(', ')||message}catch{}throw new Error(message)}return response.json()}
export const api={
 dashboard:()=>request<Dashboard>('/dashboard'),
 automationSummary:()=>request<AutomationSummary>('/dashboard/automation-summary'),
 automationMetrics:()=>request<AutomationMetrics>('/dashboard/automation-metrics'),
 recentProcessing:()=>request<RecentProcessingActivity[]>('/dashboard/recent-processing'),
 invoices:(status?:InvoiceStatus)=>request<Invoice[]>(`/invoices${status?`?status=${status}`:''}`),
 invoice:(id:string|number)=>request<InvoiceDetail>(`/invoices/${id}`),
 invoiceFileUrl:(id:string|number)=>`${API}/invoices/${id}/file`,
 upload:(file:File)=>{const body=new FormData();body.append('file',file);return request<InvoiceDetail>('/invoices/upload',{method:'POST',body})},
 dispatchProcessing:(id:number)=>request<ProcessingDispatch>(`/invoices/${id}/processing/dispatch`,{method:'POST'}),
 review:(id:number,action:'approve'|'reject')=>request<InvoiceDetail>(`/invoices/${id}/${action}`,{method:'POST'}),
 purchaseOrders:()=>request<PurchaseOrder[]>('/purchase-orders'),vendors:()=>request<Vendor[]>('/vendors')}
