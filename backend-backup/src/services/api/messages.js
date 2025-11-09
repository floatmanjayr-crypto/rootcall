export const inbox = ()=>fetch("/api/messages/inbox").then(r=>r.json());
export const bulkSend = (p)=>fetch("/api/messages/bulk",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
export const emailBlast = (p)=>fetch("/api/email/blast",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
