# RootCall - AI Call Shield Platform

Professional VoIP platform with AI-powered call screening and protection.

## Features

- ��� AI Voice Agents (Retell AI integration)
- ��� Phone Number Management (Telnyx)
- ���️ Call Screening & Spam Protection
- ��� Subscription Management (Stripe)
- ��� Real-time Dashboard
- ��� Secure Authentication

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

4. Create `backend/.env` with the environment variables listed below:
Use development credentials; never commit production keys.

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

### Live Call Upgrades

The client portal includes live AI/caller captions, silent listening, and confirmed
browser call takeover. See [setup, verification, and upgrade recommendations](backend/docs/ROOTCALL_UPGRADES.md)
for provider configuration and production rollout requirements. Real-call staging
verification is required before customer rollout.

Deploy to Render with one click using `render.yaml`

### Paid Customer Onboarding

The single-line customer flow is **email/password account → authenticated Essential
checkout → verified payment → profile, forwarding phone, agent voice and Shield number →
optional trusted contacts → confirm automatic activation → guided call checks → dashboard**. Setup is saved and can be resumed
after signing in. Trusted callers can be added during setup or later in the dashboard.
Stripe returns directly to onboarding for payment confirmation; old success-page links
redirect there. Setup remains locked until the server verifies payment.
Family and Guardian are not offered for new checkout at launch.
Existing customers without an onboarding record keep their dashboard access.
The dashboard includes visible desktop/mobile sign-out and authenticated Stripe billing
management. Enable invoices, payment-method updates and cancellation in the Stripe portal.

New setup connects trusted-contact bypass through a signed Retell per-number inbound
webhook while keeping Telnyx SIP and the existing unknown-caller agent. Existing
customers can enable it from **Trusted Contacts → Connect trusted caller routing**.
Caller ID matching is not verified identity and can be spoofed.

Apply migrations through `e254ab76f430` before serving the updated code (including
onboarding migration `a813bc21e902` and trusted-routing migration `b921df43c107`).
Back up the database and rehearse migrations on staging first.
The final migration preserves the remote dashboard voice preference and adds its
column only when missing, so activation workers can start before any web startup hook.
It retains existing preferences on downgrade.
See the [onboarding rollout checklist](backend/docs/ROOTCALL_UPGRADES.md#paid-onboarding)
for webhook events, retry handling, limitations, and required real-call tests.
Local tests do not certify a production deployment.

Deploy the `rootcall-activation` background worker declared in `render.yaml` alongside
the web service; both must use the same PostgreSQL database and provider configuration.
After confirmation, `POST /api/onboarding/complete` returns **202 Accepted**, not an
activation-success claim. The worker continues without an open browser, saves progress,
and retries safe failures up to six attempts. The page polls status automatically.
Without the worker, requests remain queued; monitor queue age and worker logs.
The extra worker service may incur hosting costs. For local single-process development,
tests can invoke `app.services.activation_jobs.run_once`; the standalone worker refuses
SQLite because its locks cannot coordinate separate processes.

After configuration, onboarding opens a saved, customer-reported call-test checklist.
The dashboard Settings links back to it. Sharing the new Shield number directly needs
no carrier changes. Forwarding an existing number is a separate customer/carrier action;
do not forward the same number used as the approved-call destination back to Shield.
Checks are not automatic audio/provider verification and reset when line/destination changes.

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Secret for JWT tokens
- `TELNYX_API_KEY` - Telnyx API key
- `RETELL_API_KEY` - Retell AI API key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_ESSENTIAL_PRICE_ID` - Price ID for Essential plan
- `STRIPE_WEBHOOK_SECRET` - Signing secret for `/api/payments/webhook`
- `APP_BASE_URL` - Public HTTPS backend/static-app origin, without a trailing slash
- `TELNYX_SIP_USERNAME` - SIP username prefix; onboarding appends the user ID
- `TELNYX_SIP_PASSWORD` - Strong SIP trunk password
- `TELNYX_OUTBOUND_VOICE_PROFILE_ID` - Telnyx profile permitted to transfer calls
- `OPENAI_API_KEY` - Required by the existing services-package initialization
- `DEEPGRAM_API_KEY` - Existing transcription integration
- `SENDGRID_API_KEY` - Transactional email provider key
- `SENDER_EMAIL` - Verified sender for password reset email

### Account Access and Password Recovery

The served administrator page is `/static/admin-panel.html`. Sign in with an
existing active account whose database `is_superuser` flag is true, then open that
page. Administrator APIs require a bearer token; putting an administrator ID in
the URL no longer grants access. Public JWT-debug endpoints have been removed.
There is no public administrator-signup or impersonation feature.

Set a private, cryptographically random `JWT_SECRET_KEY` (at least 32 random bytes
recommended). The legacy `SECRET_KEY` environment alias is still supported when
`JWT_SECRET_KEY` is absent, but no default signing key is supplied. Missing or
known-placeholder keys return an explicit service-unavailable error for account
access. Keep the existing private key to preserve valid active-user sessions.
Plan a key rotation if the previous public debugging endpoints were exposed;
rotation intentionally signs everyone out.

Password recovery requires `SENDGRID_API_KEY`, a verified `SENDER_EMAIL`, and
`APP_BASE_URL` as an HTTPS origin without a path, query, or fragment. Missing
configuration returns an explicit unavailable message, never a logged reset link.
Requests return HTTP 202 to acknowledge receipt, not guaranteed email delivery.
Email delivery runs as an in-process background task; monitor sanitized delivery
errors and verify SendGrid delivery before rollout. A durable email queue and
rate limits remain production follow-ups.

New reset links put tokens in a URL fragment rather than a query parameter.
The reset page accepts older query links too, then clears the token from the
address bar. Existing reset tokens still expire after 30 minutes and are single-use.
Passwords must contain at least 8 characters and at most 72 UTF-8 bytes; oversized
new passwords are rejected rather than silently truncated.

### Billing Warnings and Activation Recovery

The customer dashboard shows verified Stripe subscription status, current-period
end and cancellation dates, and payment warnings. Billing failures do not
automatically stop calls, change agent routing, or release phone numbers.
Unfinished onboarding still requires an active paid subscription before setup.
Legacy accounts without a linked onboarding subscription show an unverified
billing state rather than a fabricated active subscription.

Administrators can open **Billing and setup attention** on the admin page.
That queue uses saved snapshots; customer billing checks and signed Stripe
webhooks refresh subscription data. After reconciling Telnyx orders and Retell
resources, an administrator can reopen paused or stale activation without clearing
number-order or provider-resource checkpoints. Previously confirmed background jobs
are requeued automatically after review; older setups without jobs require customer
confirmation. The review itself makes no provider changes. Setup running for less than 30 minutes,
or still protected by a running worker's lock, cannot be reopened.

If a create-resource response is lost, automatic retry is blocked until provider
review confirms there is no unmatched resource that could be duplicated.
Do not delete or detach resources used by working lines. PostgreSQL uses
per-account session advisory locks across checkpoint commits; SQLite locking is
for single-process local development only. Interrupted background jobs are reclaimed
after five minutes only if the previous worker's lock is gone. Uncertain creations,
conflicts, invalid payment and exhausted retries still require support review; this
is not an exactly-once provider-resource creation guarantee.

## License

Proprietary - All Rights Reserved
