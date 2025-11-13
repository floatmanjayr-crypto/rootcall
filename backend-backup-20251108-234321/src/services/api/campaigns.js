export const schedule = (p)=>fetch("/api/campaigns/schedule",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
export const compliance = ()=>fetch("/api/campaigns/compliance").then(r=>r.json());
