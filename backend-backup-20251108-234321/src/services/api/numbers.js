export const buy = (p)=>fetch("/api/numbers/buy",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
export const assign = (p)=>fetch("/api/numbers/assign",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
