# RootCall Live Calls and Upgrade Recommendations

## Implemented

The active client portal now has a Live Calls section with:

- Live text for both the AI and caller, with partial turns replaced rather than duplicated.
- Silent browser listening with the microphone off.
- Confirmed browser takeover using Retell's Web SDK. Microphone permission is requested before stopping the AI.
- Mute, disconnect, and end-call controls, with a warning before leaving a taken-over call.
- Owner-only APIs, signed Retell call webhooks, and server-side transcript streaming. The Retell API key stays on the server.

This interprets "seeing text to speech" as live captions of the conversation, not typing a message for the AI to speak. Takeover is browser audio, not forwarding to a cell phone. It permanently stops the AI for that call; Retell pauses transcription during human takeover.

## Setup and Deployment Gates

1. Install the updated backend requirements on the supported Python 3.11 deployment runtime. `websockets>=14,<16` is required for the transcript relay.
2. Set `RETELL_API_KEY` to a key with Call Edit permission. If the agent uses PII scrubbing, monitoring also requires permission to view raw data.
3. Configure the Retell agent's call-event webhook to `https://YOUR_BACKEND/retell/webhook`, with `call_started`, `call_ended`, and `call_analyzed` events. Its signing key must match `RETELL_API_KEY`. The separate inbound routing webhook is not a replacement for these events.
4. Ensure the Retell-facing phone number exists in `phone_numbers`, assigned to the correct user. Unrecognized or inactive numbers are ignored instead of guessing ownership. Separate screening DIDs must be mapped deliberately before enabling this for those calls.
5. Deploy the updated static client portal and its two live-call assets alongside the backend. The login page already points to this portal; the separate React mind-map dashboard is unchanged.
6. Serve the portal over HTTPS or localhost for microphone access. Allow outbound HTTPS/WebRTC connections to Retell and its media provider. The browser SDK is pinned to version 3.0.3 and loaded from `esm.sh`; allow that origin in CSP, or bundle and self-host it before a strict production rollout.
7. Disable proxy buffering for the transcript response and allow long-lived streaming requests. Retell currently limits each call to five transcript watchers, including its dashboard.

No provider configuration, production deployment, database migration, or real telephone call was performed as part of this change. Existing `calls` columns are reused. The existing schema must already contain the RootCall call fields.

Dependency compatibility is a rollout blocker until a supported set is locked: the local install found latest OpenAI requiring AnyIO >=4.10 while FastAPI 0.104.1 requires AnyIO <4, and latest Deepgram requiring a newer `pydantic-core` than Pydantic 2.5.0 supplies. The focused feature tests and application startup pass with the framework pins restored, but that is not proof that all provider integrations work with an inconsistent environment.

The local FastAPI preview uses a separate database under `/tmp` and dummy provider keys. Its health and unauthenticated live-call responses were checked; it cannot place or monitor real calls until configured with working provider credentials and signed webhook delivery.

## Verification

Backend regression tests use an isolated in-memory database and never contact providers:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_live_calls.py -v
```

The tests cover webhook signatures, nested event payloads, ownership assignment, event retries, live text, completed calls, cross-user access denial, failed and repeated takeover, and the AI-leg/human-call lifecycle. The existing service package initializes an OpenAI client during import; tests use a dummy key when none is set.

Browser checks use Playwright and simulated Retell sessions:

```bash
npm install --prefix /tmp/rootcall-browser @playwright/test
/tmp/rootcall-browser/node_modules/.bin/playwright install --with-deps chromium
python -m http.server 8765 --bind 127.0.0.1 --directory backend
# In another terminal:
PLAYWRIGHT_MODULE=/tmp/rootcall-browser/node_modules/@playwright/test node backend/tests/live_calls.browser.cjs
```

The static server is only a local test fixture, not a working backend or a production serving command. Do not expose its backend-directory root publicly.

Desktop and mobile checks cover turn replacement, rendering caller text without HTML execution, microphone denial, takeover, mute, and horizontal overflow. The pinned real SDK was also checked for successful loading and offline session creation.

Before enabling this for customers, place a staging call to an owned number and confirm captions, silent listening, microphone denial, takeover, two-way audio, mute, end-call behavior, multiple tabs, and recovery after a network drop. Check webhook delivery logs and ensure another account cannot access the call. Browser simulations do not verify carrier audio, firewall traversal, provider permissions, or account-level feature availability.

## Priority Recommendations

This is a targeted review of active deployment, authentication, payment, screening, call-event, and portal paths, not a comprehensive security audit.

| Priority | Finding | Recommendation |
| --- | --- | --- |
| Critical | Telnyx screening signature verification returns `True`, and the enforcement call is commented out in [rootcall_screen.py](../app/routers/rootcall_screen.py). | Implement Ed25519 verification and timestamp checks on the raw body; reject invalid or replayed events before answering, transferring, or sending SMS. Verify the other Telnyx webhook entry points too. |
| High | Existing provider-mutating routes in [retell.py](../app/routers/retell.py) lack user authentication, including agent creation, number binding, and outbound calling. | Require active-user authentication, enforce number/agent ownership and subscription permissions, and add rate and spend limits. The new live-call routes are owner-restricted, but this does not protect the older routes. |
| High | Checkout accepts a caller-supplied `user_id` without authentication and builds redirect URLs from `Origin` in [payments.py](../app/routers/payments.py). | Derive the customer from the authenticated user and use an allowlisted frontend URL. Reconcile subscription access only from verified Stripe webhooks. |
| High | [config.py](../app/config.py) has a predictable fallback JWT secret; [main.py](../app/main.py) enables wildcard credentialed CORS. | Fail startup without a strong production secret and explicitly allow only trusted frontend origins. |
| High | Live call transcripts contain raw personal information, including when provider scrubbing is enabled. | Define consent disclosures, access roles, retention/deletion rules, and audit records for listening and takeover. Avoid storing transcript content in application logs. |
| Medium | Hardcoded fallback client routing remains in [client_config.py](../app/services/client_config.py) and [retell_inbound.py](../app/routers/retell_inbound.py). | Make user-owned database configuration authoritative, remove production fallbacks after migration, and validate Retell-facing DID ownership. |
| Medium | The repo contains multiple backend copies, several portals, and many repair scripts; the login target differs from the React entry point. | Establish one supported backend and portal, archive obsolete scripts, and make the deployment build explicit. Do not delete backups until their purpose is confirmed. |
| Medium | Service imports initialize unrelated provider clients; broad/unpinned SDK requirements coexist with older framework pins. | Initialize clients on demand, use a reproducible dependency lock, align local Python with deployment, and add focused tests to CI. |
| Medium | Live sessions depend on webhook delivery and browser release notifications. An abrupt browser/process failure can leave stale status. | Add periodic provider reconciliation, an audit trail, stream concurrency limits, metrics, and alerts for webhook failures and abandoned sessions. |

## Suggested Product Roadmap

1. Ship live captions and takeover behind a staged rollout after fixing the critical/high security findings and validating real calls.
2. Add verified caller identity, the caller's stated reason, and explainable spam labels with a false-positive correction flow. Use a licensed reputation source rather than scraping another product's directory.
3. Add AI voicemail: searchable transcripts, concise summaries, callbacks, and retention controls.
4. Add per-number screening rules for trusted contacts, unknown callers, quiet hours, emergencies, and accessible large-text views.
5. Add optional caregiver alerts and delegated access, with explicit account-owner consent and independently scoped permissions.
6. Add push notifications for screened calls and a mobile-friendly entry point. Mobile browser background/audio restrictions need testing before promising native-phone-style interception.
7. Consider typed prompts for the AI to speak, multilingual captions, and scam-risk escalation after the live-call workflow is reliable. Keep warnings explainable; do not present uncertain AI judgments as verified facts.