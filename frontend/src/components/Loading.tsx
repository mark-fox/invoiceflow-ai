export function Loading(){return <div className="loading"><span/>Loading workspace…</div>}
export function ErrorState({message}:{message:string}){return <div className="error"><b>Unable to load this view</b><span>{message}</span></div>}

