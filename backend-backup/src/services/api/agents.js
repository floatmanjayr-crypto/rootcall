export const list = ()=>fetch("/api/agents").then(r=>r.json());
