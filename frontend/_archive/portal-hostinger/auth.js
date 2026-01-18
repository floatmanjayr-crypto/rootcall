const API = "https://rootcall.onrender.com"; // Render API origin

function saveToken(tok){ try{ localStorage.setItem("authToken", tok); }catch(e){} }
function getToken(){ try{ return localStorage.getItem("authToken"); }catch(e){ return null; } }
function clearToken(){ try{ localStorage.removeItem("authToken"); }catch(e){} }

async function apiFetch(path, opts={}){
  const t = getToken();
  const headers = Object.assign({"Content-Type":"application/json"}, opts.headers||{});
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(API + path, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined
    // no cookies cross-origin
  });
  let data=null; try{ data = await res.json(); }catch(e){}
  if (!res.ok) throw new Error((data && (data.detail || data.message)) || ("HTTP "+res.status));
  return data;
}

async function login(email, password){
  const d = await apiFetch("/api/auth/login", { method:"POST", body:{ email, password } });
  const tok = d && (d.access_token || d.token || d.jwt);
  if (tok) saveToken(tok);
  return d;
}

async function logout(){
  clearToken();
  location.href = "./login.html";
}
