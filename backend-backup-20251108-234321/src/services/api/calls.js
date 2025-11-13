export const start = (p)=>fetch("/api/calls/start",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
export const listRecordings = ()=>fetch("/api/calls/recordings").then(r=>r.json());
