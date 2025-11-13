export const voice = ()=>fetch("/api/analytics/voice").then(r=>r.json());
export const messaging = ()=>fetch("/api/analytics/messaging").then(r=>r.json());
