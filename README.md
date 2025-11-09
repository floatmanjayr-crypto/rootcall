# RootCall - AI Call Shield Platform

Professional VoIP platform with AI-powered call screening and protection.

## Features

- Ì¥ñ AI Voice Agents (Retell AI integration)
- Ì≥û Phone Number Management (Telnyx)
- Ìª°Ô∏è Call Screening & Spam Protection
- Ì≤≥ Subscription Management (Stripe)
- Ì≥ä Real-time Dashboard
- Ì¥ê Secure Authentication

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL
- **Telephony**: Telnyx, Retell AI
- **Payments**: Stripe
- **Deployment**: Render

## Local Development

1. Clone the repo:
```bash
git clone https://github.com/yourusername/rootcall.git
cd rootcall/backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your keys
```

5. Run migrations:
```bash
alembic upgrade head
```

6. Start server:
```bash
uvicorn app.main:app --reload
```

7. Visit: http://localhost:8000

## Deployment

Deploy to Render with one click using `render.yaml`

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Secret for JWT tokens
- `TELNYX_API_KEY` - Telnyx API key
- `RETELL_API_KEY` - Retell AI API key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_ESSENTIAL_PRICE_ID` - Price ID for Essential plan
- `STRIPE_FAMILY_PRICE_ID` - Price ID for Family plan
- `STRIPE_GUARDIAN_PRICE_ID` - Price ID for Guardian plan

## License

Proprietary - All Rights Reserved
