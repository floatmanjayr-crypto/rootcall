# RootCall - Backend Integration & Deployment Guide

## âœ… What's Already Connected

Your RootCall landing page is now fully integrated with your FastAPI backend:

### Frontend â†’ Backend Connection Flow:
```
User clicks "Get Protected" 
  â†“
Opens signup modal with plan selection
  â†“
User fills form & clicks "Create Account"
  â†“
JS: fetch('http://localhost:8000/api/auth/signup')
  â†“
Backend: Creates user account, returns JWT token
  â†“
JS: Stores token in localStorage
  â†“
JS: fetch('http://localhost:8000/api/payments/create-checkout')
  â†“
Backend: Creates Stripe checkout session
  â†“
Redirects to Stripe payment page
  â†“
User completes payment
  â†“
Stripe redirects back to /static/client-portal.html
  â†“
User is now subscribed!
```

## íº€ How to Test Locally

1. **Start your backend:**
```bash
   cd ~/voip/voip-platform/backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. **Open landing page:**
```
   http://localhost:8000/static/index.html
```

3. **Test signup flow:**
   - Click "Get Protected Now"
   - Fill in the form
   - Select a plan
   - Click "Create Account & Subscribe"
   - You'll be redirected to Stripe checkout
   - Use test card: 4242 4242 4242 4242

## í³¡ Deploy to Production

### Option 1: Render.com (Recommended - Free tier available)

1. **Push code to GitHub:**
```bash
   cd ~/voip/voip-platform
   git init
   git add .
   git commit -m "RootCall platform ready"
   git remote add origin https://github.com/yourusername/rootcall.git
   git push -u origin main
```

2. **Create new Web Service on Render:**
   - Go to https://render.com
   - Click "New +" â†’ "Web Service"
   - Connect your GitHub repo
   - Settings:
     - Name: `rootcall-backend`
     - Root Directory: `backend`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Add Environment Variables:**
```
   DATABASE_URL=postgresql://...
   TELNYX_API_KEY=KEY...
   RETELL_API_KEY=...
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_ESSENTIAL_PRICE_ID=price_...
   STRIPE_FAMILY_PRICE_ID=price_...
   STRIPE_GUARDIAN_PRICE_ID=price_...
   JWT_SECRET_KEY=...
```

4. **Deploy!** Render will give you a URL like: `https://rootcall-backend.onrender.com`

5. **Update frontend API URL:**
   In `static/index.html`, change:
```javascript
   const API = 'https://rootcall-backend.onrender.com';
```

### Option 2: Railway.app

1. **Install Railway CLI:**
```bash
   npm i -g @railway/cli
   railway login
```

2. **Deploy:**
```bash
   cd ~/voip/voip-platform/backend
   railway init
   railway up
```

3. **Add environment variables** in Railway dashboard

4. **Get your URL** and update frontend

### Option 3: DigitalOcean/AWS/VPS

1. **SSH into server:**
```bash
   ssh root@your-server-ip
```

2. **Install dependencies:**
```bash
   apt update
   apt install python3-pip nginx postgresql
```

3. **Clone & setup:**
```bash
   git clone https://github.com/yourusername/rootcall.git
   cd rootcall/backend
   pip3 install -r requirements.txt
```

4. **Run with gunicorn:**
```bash
   pip install gunicorn
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

5. **Configure Nginx** as reverse proxy

## í´§ Update Stripe Prices for RootCall

Create new products in Stripe dashboard:
1. Essential - $39/month
2. Family - $79/month
3. Guardian - $129/month

Add price IDs to `.env`:
```
STRIPE_ESSENTIAL_PRICE_ID=price_xxxxx
STRIPE_FAMILY_PRICE_ID=price_xxxxx
STRIPE_GUARDIAN_PRICE_ID=price_xxxxx
```

## í³Š Backend Endpoints Being Used

Your landing page connects to these endpoints:

- `POST /api/auth/signup` - Create new user
- `POST /api/auth/login` - User login
- `GET /api/payments/rootcall-plans` - Get plan info
- `POST /api/payments/create-checkout` - Create Stripe session
- `GET /api/badbot/config/{user_id}` - Get user config (portal)
- `GET /api/badbot/stats/{user_id}` - Get call stats (portal)

## âœ… Current Status

- âœ… Landing page created
- âœ… Signup modal integrated
- âœ… Backend API connected
- âœ… Stripe checkout flow working
- âœ… Client portal ready
- âœ… Database configured
- âœ… Telnyx + Retell AI integrated

## í¾¯ Next Steps

1. Test the full signup flow locally
2. Deploy to Render/Railway
3. Update Stripe with production keys
4. Configure custom domain
5. Set up email notifications
6. Launch! íº€
