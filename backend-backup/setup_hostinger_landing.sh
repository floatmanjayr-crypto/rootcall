#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo "RootCall Hostinger Landing Page Setup"
echo "============================================"
echo ""

# 1) Build your React/Vite project
echo "Step 1: Building production bundle..."
echo "--------------------------------------------"
npm install
npm run build
echo "[OK] Build complete (dist/ folder ready)."
echo ""

# 2) Prepare the .htaccess file for SPA routing
echo "Step 2: Creating .htaccess for Hostinger..."
echo "--------------------------------------------"

cat > dist/.htaccess <<'HTACCESS'
# --- Force HTTPS ---
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

# --- SPA Fallback ---
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^ index.html [L]

# --- MIME Types ---
AddType application/json .json
AddType image/svg+xml .svg
AddType application/javascript .js .mjs
AddType application/wasm .wasm

# --- Cache Control ---
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType text/html "access plus 1h"
  ExpiresByType text/css "access plus 7 days"
  ExpiresByType application/javascript "access plus 7 days"
  ExpiresByType image/svg+xml "access plus 7 days"
  ExpiresByType image/png "access plus 30 days"
  ExpiresByType image/jpeg "access plus 30 days"
  ExpiresByType application/json "access plus 1h"
</IfModule>

# --- Prevent Directory Listing ---
Options -Indexes
HTACCESS

echo "[OK] .htaccess ready inside dist/."
echo ""

# 3) Instructions for upload
echo "============================================"
echo "UPLOAD TO HOSTINGER"
echo "============================================"
echo ""
echo "Next steps:"
echo "1️⃣ Log into Hostinger → Files → File Manager."
echo "2️⃣ Open public_html (or your subdomain folder)."
echo "3️⃣ Upload all files INSIDE dist/ (not the folder itself)."
echo "4️⃣ Ensure index.html and .htaccess are visible at public_html root."
echo ""
echo "✅ Done. Visit https://yourdomain.com to verify."
echo ""
