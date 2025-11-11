(function(){
  function getToken(){ try{return localStorage.getItem("authToken")}catch(_){return null} }
  function clearToken(){ try{localStorage.removeItem("authToken")}catch(_){ } }

  // Update legacy Sign In links to the new portal login
  function normalizeCTAs(){
    document.querySelectorAll('a[href="/static/login.html"],a[href="/client-portal.html"]').forEach(a=>{
      a.setAttribute('href','/portal/login.html');
    });
  }

  // If a page opts in with data-protected="true", require token and bounce to login
  function authGuard(){
    var must = document.body && document.body.dataset && document.body.dataset.protected === "true";
    if (!must) return;
    if (!getToken()) location.href = "/portal/login.html";
  }

  // Wire optional logout button if page provides #rc-logout
  function wireLogout(){
    var lo = document.getElementById('rc-logout');
    if (lo){ lo.addEventListener('click', function(){ clearToken(); location.href='/portal/login.html'; }); }
  }

  document.addEventListener('DOMContentLoaded', function(){
    normalizeCTAs();
    authGuard();
    wireLogout();
  });
})();
