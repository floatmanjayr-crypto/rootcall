const API = ""; // same-origin

function saveToken(tok){
  try{ localStorage.setItem("authToken", tok); }catch(e){}
}
function getToken(){
  try{ return localStorage.getItem("authToken"); }catch(e){ return null; }
}
function clearToken(){
  try{ localStorage.removeItem("authToken"); }catch(e){}
}

async function apiFetch(path, opts={}){
  const token = getToken();
  const headers = Object.assign({"Content-Type":"application/json"}, opts.headers||{});
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch((API||"") + path, {
    method: opts.method||"GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    credentials: "include"   // allow cookie-based auth too
  });
  let data=null;
  try{ data = await res.json(); }catch(e){ /* non-json */ }
  if (!res.ok){
    const detail = data && (data.detail || data.message);
    throw new Error(detail || ("HTTP "+res.status));
  }
  return data;
}

// Flexible login: try {username,password} then {email,password}
async function loginFlex(id, password){
  // attempt 1: username/password
  try{
    const d = await apiFetch("/api/auth/login", {method:"POST", body:{username:id, password}});
    if (d && (d.access_token || d.token || d.jwt)) saveToken(d.access_token||d.token||d.jwt);
    return d;
  }catch(e1){
    // attempt 2: email/password
    const d = await apiFetch("/api/auth/login", {method:"POST", body:{email:id, password}});
    if (d && (d.access_token || d.token || d.jwt)) saveToken(d.access_token||d.token||d.jwt);
    return d;
  }
}

async function logout(){
  clearToken();
  try{ await apiFetch("/api/auth/logout", {method:"POST"}); }catch(e){}
  location.href = "./login.html";
}
