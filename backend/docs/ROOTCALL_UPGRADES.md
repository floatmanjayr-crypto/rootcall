# RootCall Live Calls and Upgrade Recommendations

## Dashboard reliability upgrade

The customer dashboard now reads a shared activity view of `calls` and
`rootcall_call_logs` for history, totals, and CSV export. Exact provider identifiers
on the same owned line deduplicate overlapping records; caller/time guesses are
never used. Legacy logs remain visible. Recent history remains limited to 20 rows;
export includes all saved activity. Existing naive database timestamps are treated
as UTC when returned to the browser.

Signed Retell events identify trusted calls by the line's saved trusted agent ID,
not metadata provided by a caller. A trusted bypass is an attempt, not a confirmed
connection: only Retell's `call_transfer` outcome counts as trusted-forwarded.
Provider-reported error outcomes stay failed after analysis. No telephone routing,
agent prompt, SIP connection, or provider configuration is changed by this upgrade.
Past events that did not persist a trusted classification are not guessed/backfilled.

Contact names now use the existing `trusted_contacts` detail table, while
`rootcall_configs.trusted_contacts` remains the phone-only routing list. Saving the
same number updates its name; removal clears the saved name. Existing unnamed
onboarding contacts work unchanged. The existing migration `40508a9fb685` creates
the detail table; no additional migration is needed for this upgrade.

CSV downloads now send the account bearer token, report errors, and allow retry.
Formula-like CSV cells are prefixed with an apostrophe to avoid spreadsheet
execution; phone cells intentionally retain this protective prefix. Contact names,
caller names, and notification text are escaped in the dashboard.

The dashboard reports **Shield line configured**, **Line setup needs attention**,
or an explicit unavailable state rather than claiming live protection. This checks
saved configuration only, not current provider health, subscription entitlement,
carrier forwarding, or audio quality. Customers must still place a test call.
Failed dashboard loads show a retry banner and unknown totals rather than zeros.
Periodic refresh no longer displays the full-screen loading overlay.

Validation commands (from the repository root):

```sh
cd backend
../.venv/bin/python -m pytest tests/test_customer_activity.py tests/test_trusted_inbound.py tests/test_onboarding.py tests/test_call_routing.py tests/test_retell_service.py tests/test_live_calls.py tests/test_password_reset.py -q --disable-warnings
```

Browser regression scripts are `tests/dashboard.browser.cjs`,
`tests/live_calls.browser.cjs`, and `tests/onboarding.browser.cjs`. They use
Playwright against a local static server with mocked APIs at 1440px and 390px.
Set `ROOTCALL_PREVIEW_URL` and, if installed outside the project,
`PLAYWRIGHT_MODULE`. These checks do not certify live calls or Stripe payments.

Remaining production phases include broader authentication/webhook hardening,
accurate privacy disclosures and retention controls, any future payment suspension
policy and phone/email verification. Background activation and guided carrier
forwarding are described below; neither changes the saved billing restriction policy.

## Automatic activation and guided service setup

Apply migration `d143fa65e329` after `c032ef54d218`, then `e254ab76f430`, before starting updated web/worker
processes. It adds `activation_jobs` and a nullable JSON field for customer-reported
setup checks. It does not enqueue old drafts or trigger purchases during migration.
Back up and rehearse migrations on staging first.
The deployment log attached for this support report shows PostgreSQL
`UndefinedTable: relation "customer_onboarding" does not exist`; the deployed
database has not received the onboarding migrations. This is a schema/deployment
failure, not customer-entered onboarding data. Do not have the UI create tables or
bypass paid setup. On Render, run `cd backend && alembic upgrade head` against the
intended PostgreSQL database after a backup and staging rehearsal, verify the revision
reaches `e254ab76f430`, then restart the web and activation worker. Until then, the
onboarding status endpoint returns a clear `503` and the page offers retry/support;
it does not report a false success or initiate provider setup.

The web service applies pending migrations itself at startup (`app/schema_upgrade.py`), so no Render
pre-deploy command or shell access is needed. It runs only on PostgreSQL, takes a database advisory lock so
concurrent instances cannot race, and applies everything in a single transaction: either all migrations apply
or none do. It never stops the app from booting; on failure it logs `Automatic schema upgrade failed and was
rolled back` with the cause. Cases it handles:

- Existing Alembic history: runs `upgrade head`.
- Core tables exist but there is no Alembic history (how production was created, because the first migration
  `f6236c21f2cd` is an empty placeholder): records baseline `40508a9fb685`, then runs `upgrade head`.
- Empty database: creates the full schema and records the latest revision.
- Anything else (for example a `users` table without the other core tables): logs an error and changes nothing.

Set `AUTO_MIGRATE=false` to disable it and run `cd backend && alembic upgrade head` yourself. Do not use
`alembic upgrade head` as a Render pre-deploy command on a database without Alembic history: the empty first
migration means it fails from scratch and would block every deploy. Verified on PostgreSQL 15 with a
database shaped like production (opt-in test: set `TEST_SCHEMA_POSTGRES_URL` for `test_schema_upgrade.py`).
The activation worker may log missing-table errors until the web service finishes migrating.

The merged dashboard supports live Retell voice selection, editable account-holder
names and explicit identity sync. New activations save their selected voice into the
same configuration and use the recipient-first greeting/owner-routing gate while
retaining screening instructions. Existing agent handbooks are preserved on identity
sync; syncing does not republish the agent. Voice updates use the returned draft
version and publish only that version. Transfer updates preserve existing LLM tools
and SIP-auth headers while retaining SIP INVITE cold-transfer mode.

Migration `e254ab76f430` adds the voice-preference column only if absent, accommodating
databases already upgraded by the remote version's web startup hook. It does not change
existing voices and retains the column/preferences on downgrade. Apply it before
starting activation workers, which must not depend on a web process running first.

Deploy the separate `rootcall-activation` Render worker from `render.yaml`, using
the web service's PostgreSQL database and matching Telnyx, Retell, Stripe and public
URL configuration. The existing services package also initializes OpenAI clients at
import, so the worker inherits that key as well. This adds a hosting service/cost.
Start command: `cd backend && python -m app.activation_worker`.
No new queue broker or package is required. The standalone worker explicitly rejects
SQLite, whose per-process development locks cannot protect shared provider operations.

The customer confirms their selected profile, voice, number and optional contacts once.
`POST /api/onboarding/complete` verifies eligibility and saves one idempotent job per
account, returning **202 Accepted**. This acknowledges a saved request, not configured
service. The compatibility `/api/rootcall/provision` endpoint uses the same queue
for onboarded accounts; legacy provisioning is unchanged.
Queued/running/retry jobs lock profile/contact/number edits. Status reads
include job state, attempts and next-attempt time. During automatic activation, polling
reads saved payment state instead of repeatedly fetching Stripe; the worker re-verifies
payment before each attempt. A closed browser or lost HTTP response does not cancel
the committed request. On return, progress resumes from the saved job.

The worker polls every five seconds, processing up to 25 due accounts per batch.
Each account uses the existing PostgreSQL advisory lock across commits. Safe failures
(502/503 and explicitly pending number inventory) retry up to six total attempts,
with 30/60/120/240/480-second delays. Inventory reconciliation never reorders an
already-attempted number. Resource-create uncertainty, routing conflicts, invalid
payment, inactive accounts, unexpected errors and exhausted attempts pause for support.
Unexpected exceptions are logged and surfaced as paused jobs, never success.
Database errors stop the worker for supervisor restart; committed running jobs remain.

Interrupted running jobs become eligible for reclamation after five minutes. A live
worker's session lock prevents concurrent execution even if timestamps are old.
After process death, a new worker preserves order/provider IDs and uncertainty markers:
it resumes safe checkpoints, or pauses uncertain creation for reconciliation.
The worker is not an exactly-once creation guarantee. No arbitrary provider resources
are deleted or silently rebound. A reviewed paused job is requeued automatically using
the customer's original activation confirmation; pre-worker setups still require a
customer confirmation. No payment restriction policy changes are introduced.

Operations: monitor the worker's ready/completed/retry/paused logs and the admin
attention queue, which now includes queued/running/retry/paused jobs and their next
attempt times. A queued request older than two minutes shows an explicit customer
delay message. Restart a stopped worker rather than asking customers to repurchase.
Allow graceful shutdown to finish the current activation; a forced stop is recovered by
the same guarded logic. There is no email-notification queue in this upgrade.

On completion, onboarding automatically shows direct-number usage and a call-test
checklist; dashboard Settings links back to it. Owner-authenticated
`GET/PUT /api/onboarding/service-setup` persist customer-reported screening, trusted
transfer, two-way audio and carrier-forwarding checks. A stale save for a changed
line/destination is rejected; old checks are cleared from the displayed state when
either changes. This guide applies to accounts created through paid onboarding;
legacy accounts keep their existing dashboard flow.

Direct use of the Shield number requires no carrier changes. Existing-number
forwarding cannot be switched on by RootCall automatically. The guide requires the
customer to arrange a separate, unforwarded approved-call destination first, then
consult their carrier about forwarding, fees and disabling it. No universal dialing
codes are guessed. It warns against forwarding the approved-call destination back
to Shield, which would loop. Tests are explicitly self-reported, not live provider
health/audio verification, and do not change routing or place calls.

Validation includes job idempotency, fresh-session execution, bounded retries,
closed-browser progress, lost-create blocking, safe restart and reviewed automatic
resume, account/payment checks, owner-scoped guide persistence, stale-save rejection
and data-preserving migration round trips. Run the existing customer regression suite
including `tests/test_onboarding.py`. For real PostgreSQL process-lock/crash tests,
set `TEST_ACTIVATION_POSTGRES_URL` to an isolated test database and run
`pytest tests/test_activation_postgres.py -q`; each test uses a unique temporary schema.
Use an explicit `postgresql+psycopg2://` URL with the declared PostgreSQL driver.
Browser tests exercise desktop/mobile queued/retry polling and saved guide state.
Providers and Stripe remain mocked; live staging payment/call tests and the pinned
production runtime/dependency installation remain deployment gates.

## Billing visibility and guarded activation recovery

Apply migration `c032ef54d218` after `b921df43c107`, then `d143fa65e329`, **before** starting this version
of the application. It adds subscription snapshots, activation progress/uncertain
operation checkpoints, and the latest administrator recovery review. Existing
setup, order flags, and provider IDs are preserved. Rehearse upgrade/downgrade on
a backed-up staging database; do not run migrations against a live call database
without a deployment plan.

The approved launch policy is **warnings and administrator review only**:
no automatic call restrictions, hangups, number releases, or routing changes.
An active subscription scheduled to cancel remains active until Stripe changes
its actual status. New/unfinished setup still requires an active paid subscription.
Current-period end is shown as a billing period date, not proof an invoice was paid.

`GET /api/payments/status` refreshes the signed-in account's linked subscription
from Stripe, checks customer ownership, and saves status, current-period end,
scheduled/actual cancellation dates, first observed non-active time, and last
verification time. Active recovery clears the issue timestamp. Dates support
Stripe's subscription-level and subscription-item period schema. Existing signed
webhooks use the same snapshot update, retrieving current Stripe state so an old
event cannot restore an expired subscription. Failed verification is explicit and
does not replace the previous snapshot with a fabricated active status. Legacy
accounts without a linked onboarding subscription remain explicitly unverified.

The customer dashboard shows warnings/cancellation dates and separate
verification-failure/retry messaging without hiding working call controls.
Billing management continues to use the account-owned Stripe portal.
Administrators see a paginated, role-protected `/api/admin/attention` queue for
paused/running setup, non-active subscriptions, and scheduled cancellations.
This queue reads saved snapshots and does not make provider calls.

Activation now persists a last-stage timestamp independent of billing writes.
Retell LLM, screening-agent, trusted-flow and trusted-agent creation each persist
an uncertain-operation marker before creation. Only a response with a resource ID
and saved checkpoint clears that marker. If creation times out/crashes, customer
retry is blocked pending reconciliation instead of creating another resource.
Number ordering retains its existing `order_attempted` protection; uncertain
imports continue to reconcile against provider inventory. Existing customers'
live number bindings and telephone routing are not modified by the recovery API.

The activation request and administrator recovery share a per-user nonblocking
PostgreSQL session advisory lock held on a separate connection across checkpoint
commits. A live worker prevents reopening even if its timestamp is stale.
Worker/process exit releases the session lock; stale `provisioning` rows become
eligible for administrator review after 30 minutes. SQLite uses an in-process
per-engine/user lock for single-process local development only; do not use
multi-process SQLite for this flow. Size the PostgreSQL pool for the additional
activation lock connection.

**Recovery procedure:**

1. Open **Administration -> Billing and setup attention**.
2. Compare the Shield number/order, connection, LLM and agent IDs with Telnyx and
   Retell, including the displayed trusted-flow/agent checkpoints.
   Resolve any unmatched resource in the provider console before retrying.
   Do not delete/reassign resources that serve a working line.
3. Use **Review activation**, document the reconciliation, and confirm no
   unmatched resource remains that could be duplicated.
4. `POST /api/admin/customers/{user_id}/reopen-activation` rechecks eligibility and
   active account/worker lock, preserves all saved order/provider IDs, clears only
   the reviewed uncertainty marker, and records the latest reviewer, timestamp
   and note. An operational log records administrator/account IDs. This is not a
   full immutable audit ledger.
5. Previously confirmed background jobs resume automatically after the review;
   older setups without jobs require the customer to confirm activation.
   No second number order is allowed when `order_attempted` is already set.

Completed/recently running/inactive accounts cannot be reopened, and a missing
reconciliation confirmation/note is rejected. Unfinished onboarding cannot bypass
these checks through the dashboard trusted-routing connection API.

Validation adds `tests/test_billing_recovery.py`, including snapshot ownership,
dates, warning/recovery policy, webhook duplicates/out-of-order state, role gates,
stale/live-worker recovery, checkpoint preservation, and PostgreSQL lock-call
contracts. Onboarding tests cover preserved-data migration round trips, lost
screening/trusted creation responses, and a reviewed stale setup finishing without
another purchase. Browser tests cover warning/dates/verification retry, operator
review validation/busy retry, and customer setup stage/review state at both sizes.

Limitations: PostgreSQL process-lock/crash behavior has isolated integration coverage,
not certification against a live production database. Stripe/providers are mocked. No live
payment, provider mutation, migration, key change, deployment, or push was done.
Background jobs and guarded automatic retries are described above; uncertain
provider creation still needs operator reconciliation, not an exactly-once guarantee.
Provider spend monitoring, further reconciliation, privacy/retention, and any future service-restriction
policy remain production follow-ups.

## Account and administrator access upgrade

- Both administrator APIs now use the shared authenticated, active-user and
  administrator dependencies. The canonical paths are `/api/admin/dashboard`
  and `/api/admin/users`. Older paths with an administrator ID remain compatible
  only when that ID matches the signed-in administrator. Role/activity checks
  read the database on every request. User listing has bounded pagination.
- The served administrator page uses same-origin bearer requests, safe text
  rendering, explicit denial/error/retry states, and sign-out. It no longer uses
  localhost or a hardcoded administrator ID, nor offers a nonfunctional
  impersonation link. Its call counters are explicitly labeled as legacy logs;
  they have not been migrated into platform-wide provider analytics.
- Public `/api/auth/debug-jwt` and `/api/auth/test-token-decode` routes are removed.
  `/api/auth/me` uses the shared access-token validation and includes the current
  `is_superuser` flag for navigation only; the server still authorizes each API.
- Access tokens must have expiration and a valid positive integer account
  subject. Reset-purpose tokens, inactive accounts, invalid signatures and
  malformed subjects cannot access customer or administrator APIs. Inactive
  accounts also cannot log in or reset/reactivate themselves.
- Signing/verification rejects missing and known-placeholder JWT keys rather than
  using a predictable fallback. The `SECRET_KEY` environment alias still works
  when `JWT_SECRET_KEY` is absent. Existing correctly signed active-user sessions
  remain valid; the customer login token lifetime remains 24 hours.
- Password recovery requires configured SendGrid, sender, and an HTTPS public
  origin before account lookup; missing configuration returns 503 consistently.
  It does not derive email links from the request Host header or log reset links.
  HTTP 202 acknowledges receipt, not successful delivery. Actual delivery runs
  after response as an in-process background task; provider failures/rejections
  produce sanitized operational errors and do not disclose account existence.
  Monitor these logs. Delivery is not durable across process crashes; a durable
  queue, delivery monitoring/alerts, and abuse rate limits are still required.
- New email links use `#token=...`, which is not sent to the server in the page
  request. The page accepts legacy query tokens, removes the token from browser
  history, and uses `no-referrer`. Legacy query links can still reach HTTP access
  logs before the page cleans them; do not retain/share those URLs. Reloading a
  cleaned page requires reopening the original email link.
- Reset passwords use the same 8-character minimum/72-UTF-8-byte maximum as
  signup. Reset updates lock the user row on databases supporting row locks.
  Thirty-minute expiry and password-hash-fingerprint single-use checks remain.
  Password reset does not yet revoke previously issued access tokens.

No schema migration, key rotation, account-role change, live email, provider
configuration, or call-routing change is performed by this upgrade. Before
deployment, confirm the private signing key and SendGrid/sender/public URL on
staging. If the former debugging endpoints were public, schedule a deliberate
signing-key rotation and notify users that they will need to sign in again.

Backend coverage adds `tests/test_account_access.py` to the customer regression
command above. `tests/account_access.browser.cjs` covers administrator
authentication, denial/retry/sign-out, safe names, fragment and legacy reset links,
UTF-8 password bounds, and recovery errors at desktop/mobile sizes. SendGrid is
mocked; real email delivery and the Python 3.11 deployment environment still need
staging verification.

This is not a full security certification. CORS restrictions, legacy Telnyx
signature enforcement, rate limiting, MFA/session revocation, privacy/retention,
automatic billing enforcement, and durable activation jobs remain separate
production gates.

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

## Forwarding and Trusted-Contact Verification

Saving a forwarding number now updates the Retell LLM's transfer tool using
`transfer_destination` and `transfer_option`, preserves unrelated tools, and publishes
the agent. A rejected update is surfaced to the dashboard and does not change the saved
forwarding number. If publishing fails after the LLM update, inspect the agent's draft
and published version before retrying.

Trusted-contact additions and removals replace the JSON list so edits persist after
database reload. In the Telnyx screening webhook, trusted callers are checked before
CNAM spam labels and bypass the screening question. Transfer rejection is surfaced
instead of reporting that the caller was forwarded.

**Direct-to-Retell routing is now implemented:** imported Telnyx Shield numbers use
the signed per-number `/retell/rootcall-inbound` webhook. It looks up the active
number, account, config and saved caller list in the database on each call.
Unknown/anonymous callers retain the existing screening agent. Matching trusted
callers select a separate published conversation-flow agent whose first node is
a silent cold transfer to the database forwarding number—no screening question,
LLM classification, or shared-agent prompt mutation. Transfer failure follows an
explicit apology/end node instead of claiming connection.

The Telnyx SIP connection and default Retell screening agent binding are unchanged.
The transfer flow uses the imported trunk's actual SIP username when present; it
does not guess credentials for older accounts. Caller-supplied variables, metadata,
agent IDs and SIP headers cannot choose the forwarding destination. Normalized
contact additions/removals and forwarding updates affect subsequent calls without
rebuilding the trusted agent.

New paid onboarding creates/publishes the trusted transfer flow and connects the
number webhook before marking setup complete. Apply migration `b921df43c107` first.
For an existing line, open **Trusted Contacts → Connect trusted caller routing**.
The owner-only endpoint `/api/rootcall/trusted-routing/{client_id}` checkpoints flow
and agent IDs for retries and only sets `trusted_routing_enabled` after publishing
and webhook update succeed. It refuses to overwrite an unrelated inbound webhook
or a number bound to another/multiple agents. Resolve those configurations with
support rather than silently replacing them.

The legacy `/retell/inbound` campaign/business-hours router is intentionally unchanged.
The new number webhook is separate from `/retell/webhook` (call events). Do not
repoint Telnyx to the legacy screening webhook or replace existing call-event URLs.
Existing configurations start with trusted routing disabled until connected.

Operational limits: Retell retries failed inbound webhooks, then uses the existing
default screening agent if all attempts fail. This preserves screening but may
screen a trusted caller during an outage. A successful trusted match uses caller
ID, not verified identity; spoofed caller ID can impersonate a saved number. Transfer
still traverses Retell and may incur provider charges. Checkpoints cannot prevent
orphan resources if a provider creates a flow/agent but its response is lost.

Provider contracts: [inbound webhooks](https://docs.retellai.com/features/inbound-call-webhook),
[transfer nodes](https://docs.retellai.com/build/conversation-flow/call-transfer-node),
and [phone-number webhook configuration](https://docs.retellai.com/api-references/update-phone-number).

Before a real call test, check the number's Telnyx connection and Retell inbound
webhook settings. Then test:

1. Save the intended forwarding number and confirm the published agent has the
   `transfer_call` tool pointing to it.
2. Call from an unknown test number, identify a legitimate reason, and verify that
   the forwarding phone rings and two-way audio works.
3. Start another screened call; select **View Call**, **Listen**, then **Take Over**.
   Allow microphone permission and verify two-way audio. The AI stops; this is not a
   three-way conference, and disconnecting ends the human conversation.
4. Add a trusted test number, reload the contacts page, and call from that number.
   Verify there is no screening question and the forwarding phone rings with two-way
   audio. Remove the contact and confirm the next call uses the original screening
   agent. Update forwarding and confirm the next trusted call reaches the new phone.
   Confirm the signed inbound webhook and published trusted transfer flow in Retell.

Local regression tests use mocked provider responses. Passing them does not verify
production SIP transfer, microphone/WebRTC connectivity, or the deployed inbound route.

Dependency compatibility is a rollout blocker until a supported set is locked: the local install found latest OpenAI requiring AnyIO >=4.10 while FastAPI 0.104.1 requires AnyIO <4, and latest Deepgram requiring a newer `pydantic-core` than Pydantic 2.5.0 supplies. The focused feature tests and application startup pass in the available local environment, but that does not certify the production requirements or deployment runtime.

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
| High | Legacy provider mutation/provisioning routes are now operator-restricted, but the wider administrative surface still needs a launch review. | Review administrator authentication, remove auth-debug endpoints, enforce resource ownership and add rate/spend limits. |
| Addressed locally | [payments.py](../app/routers/payments.py) now derives account ownership from authentication, uses configured HTTPS redirects, verifies Stripe checkout/subscription state, validates webhook signatures and provides authenticated billing portal sessions. | Configure and live-test the Stripe portal/webhooks; add ongoing entitlement enforcement for phone service. |
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

## Paid Onboarding

### Customer Journey

1. Register with email and password on the landing page. No full profile is requested yet.
2. Complete authenticated Stripe subscription checkout. Stripe returns directly to
   onboarding with its checkout session ID. Onboarding verifies payment on the server
   before opening setup; neither the redirect URL nor a browser flag grants access.
   Failed/unconfirmed payment stays on an inline confirmation step with retry and sign-out.
   The session ID is removed from the URL after successful verification. Old success
   URLs redirect to onboarding while retaining query parameters. If sign-in is required,
   onboarding recovers the account's saved checkout after login.
3. Enter first name, last name, account email (read-only), forwarding phone and an agent
   voice from Retell's live catalog. Voice samples appear when the provider supplies one.
4. Search US numbers by area code and select an available Shield number.
5. Optionally add trusted callers, or choose **Do this later**. The list is normalized
   and deduplicated, saved with setup, and copied into the existing protection config
   on activation. Returning to setup restores the list; it remains editable until
   activation is confirmed. Bypass uses the connected Retell inbound webhook; adding
   contacts does not reconfigure the Telnyx carrier connection.
6. Review and confirm automatic activation: the worker purchases the selected number, configures Telnyx SIP routing, creates/publishes
   the selected Retell voice agent, configure forwarding, import the number, and save
   the customer's phone/config records, and connect trusted inbound routing. The
   guided service setup opens after configuration, with a dashboard link and saved call checks.

Signing in resumes incomplete setup. Closing or cancelling checkout does not lose the
account. Profile, number selection, payment IDs and provisioning checkpoints are saved
server-side. Existing users without an onboarding record retain their existing portal.
Account email changes require a separate verified-email workflow; setup cannot change
the identity used for checkout.

Launch is **Essential, one Shield line per account**. New Family/Guardian checkout is
disabled server-side and the landing page marks those products as unavailable.
Existing checkout/subscription verification remains compatible with historical tiers.
The old pricing-page URL redirects to the supported pricing section rather than its
obsolete localhost checkout. Desktop/mobile dashboard headers expose Sign out; signing
out clears both token keys, cached user information and the selected plan.

### Deployment Checklist

- Back up PostgreSQL. Rehearse the existing migration chain on staging, then apply
  `cd backend && alembic upgrade head` before serving the new authentication code.
  The onboarding table is migration `a813bc21e902`; trusted routing columns follow in
  `b921df43c107`. The isolated migration round-trip tests are
  not certification of the complete historical migration chain.
- Set `APP_BASE_URL` to the public HTTPS origin serving both backend and static pages.
  Use the Stripe secret and price IDs for the same account and mode.
- Configure `/api/payments/webhook` in Stripe and set its `STRIPE_WEBHOOK_SECRET`.
  Subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
  `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`,
  and `invoice.payment_failed`. Signed duplicate/out-of-order events read current
  subscription state rather than trusting old event status. Setup requires `active`;
  trials and unpaid invoices do not qualify.
- Enable Stripe's customer billing portal in the same mode/account. Allow invoices,
  payment-method changes and the intended cancellation policy; do not enable switches
  into unsupported Family/Guardian products. `/api/payments/billing-portal` derives
  customer ownership from the signed-in account, never browser-supplied customer IDs.
  Settings offers **Manage billing**. Unpaid setup with an existing verified customer
  also exposes billing recovery rather than asking for a second subscription.
- Set `TELNYX_API_KEY`, `RETELL_API_KEY`, `TELNYX_SIP_USERNAME` (a username prefix),
  `TELNYX_SIP_PASSWORD`, and `TELNYX_OUTBOUND_VOICE_PROFILE_ID`. Generated SIP usernames
  append `_<user_id>` to the prefix. The voice profile must permit the destination
  countries you intend to support; set fraud/spend limits before enabling transfers.
- Configure `OPENAI_API_KEY` and `DEEPGRAM_API_KEY` for existing module-level clients,
  even though the new onboarding flow uses Retell. Configure SendGrid and a verified
  sender before enabling password reset for customers. Missing configuration now
  returns an explicit unavailable error; reset links are never an application-log fallback.
- New agents receive the signed Retell call-event webhook and a cold-transfer tool
  with `X-Telnyx-Username`. Verify the published agent, credentials, SIP REFER behavior
  and carrier permissions in staging; mocked provider responses do not prove audio.
- New configurations leave SMS disabled until sender registration, consent and
  opt-out/compliance handling are ready.

### Retry and Support Handling

Activation claims the account atomically so concurrent clicks cannot place two orders.
The number-order-attempt flag is saved **before** calling Telnyx: an uncertain response
never automatically buys another number. Retry checks Telnyx inventory first and resumes
saved connection, LLM, agent, publication and import checkpoints. Changes to setup are
locked once background activation is confirmed, even before ordering starts.

If a number stays pending or an order definitively fails, support must reconcile the
provider order before resetting anything. Background workers reclaim safe interrupted
jobs under the session lock; old activations without jobs still use reviewed recovery.
Never manually clear database checkpoints. Lost responses during LLM/agent creation
can leave untracked provider resources and block retry pending review. Do not promise
exactly-once creation; further provider reconciliation and operation IDs remain
large-scale rollout work. Unsold draft number selections currently have no expiry.

### Verification

```bash
cd backend
python -m pytest tests/test_onboarding.py tests/test_trusted_inbound.py tests/test_password_reset.py \
  tests/test_call_routing.py tests/test_retell_service.py tests/test_live_calls.py -q
```

Using the local static-server/Playwright setup described above:

```bash
PLAYWRIGHT_MODULE=/tmp/rootcall-browser/node_modules/@playwright/test \
  node backend/tests/onboarding.browser.cjs
```

Browser mocks cover desktop/mobile payment gates, signup before checkout, authenticated
checkout headers, login/resume, profile/voice persistence, unavailable numbers and API
errors, selection, optional contacts (add/remove/duplicate/skip/edit/resume), refresh,
pending activation/retry, verified-payment success, billing failure/retry/navigation
and visible sign-out/session cleanup. Dashboard checks include the active single-line
card and settings without horizontal overflow.
They never contact Stripe or purchase a number.

Before customer rollout, use a real staging account to exercise payment success,
cancellation, expired checkout, signed webhook retries, subscription cancellation,
number purchase and recovery. Then call the Shield number and verify screening,
forwarding, two-way audio, live captions and browser takeover.

### Remaining Production Work and Product Recommendations

1. Close the launch gates in the recommendation table: legacy Telnyx webhook authentication,
   administrator/debug surfaces, strong secrets/CORS, rate limits and data retention.
   Direct SIP trusted-contact routing is implemented locally; deploy, connect existing
   numbers and verify a real trusted/unknown pair of calls before claiming live bypass.
2. Configure and live-test the implemented Stripe billing portal, including cancellation.
   Add refunds/support handling and continuing subscription enforcement for already-active
   phone service. Current paid checks protect setup, not the full ongoing call lifecycle.
3. Add email verification, forwarding-number OTP verification and a guided test call
   before describing a line as verified. Include carrier-forwarding instructions.
4. Keep launch single-line: Family/caregiver multi-line provisioning and delegated access
   are not implemented and new checkout for those plans is disabled. Build and verify
   those benefits before making them available.
5. Lock and certify dependencies on the deployed Python runtime, add CI, durable
   provisioning jobs, provider-spend alerts, error monitoring and restore-tested backups.
6. Add quiet hours, explainable screening outcomes, accessible caregiver controls,
   optional voicemail summaries and consent-based notifications after core routing is
   verified. Never advertise AI screening as guaranteed scam detection.
## Design System and Frontend Polish

- [rootcall.css](../static/rootcall.css) is the shared foundation: `--rc-*` colour, spacing, radius, shadow and type-scale tokens, a visible `:focus-visible` ring, `prefers-reduced-motion` support, a skip link, and the legal/404 page components. Load it before page styles; page styles may override tokens. Keep readable text at 12px (`--rc-text-xs`) or larger.
- Every page ships the shared SVG favicon (`favicon.svg`) and `theme-color`. Signed-in pages (dashboard, onboarding, admin) are `noindex`.
- The dashboard sidebar uses real `<nav>`/`<button>` elements with `aria-current`, and the mobile drawer is hidden from keyboard and screen readers while closed.
- Empty states use the shared `.empty-state` pattern with one next action. Live-call refresh failures show a plain-language message and a "last updated" time.
- Removed the unreferenced legacy pages (`shield-dashboard`, `rootcall-portal`, `james-portal`, `test`) and the tracked `.backup`/`.old` copies. The login page no longer shows unverified "99.8% block rate" or "<1s response" figures; only claim numbers you can measure.
- Browser tests (`backend/tests/*.browser.cjs`) need Playwright and a static preview: from `backend/` run `python -m http.server 8765 --bind 127.0.0.1 --directory .`, then `PLAYWRIGHT_MODULE=<path to @playwright/test> node tests/design.browser.cjs` (also `dashboard`, `live_calls`, `onboarding`, `account_access`).
- Not yet done: moving login/forgot/reset/portal onto the shared tokens (each still defines its own copy), replacing the portal's remaining inline `onclick` handlers, and a dark theme.

## Customer Journey Fixes and Production Checklist

Reported symptom: after registering and choosing a plan, Stripe did not open, no success page appeared, and the onboarding page asked for a name but nothing could be pressed.

Fixed in code:

- **Signup button did nothing.** The plan field was a required dropdown that started on "Choose your plan…". The hero "Get Protected Now" button opens the form without choosing a plan, so the browser silently blocked submit. Essential is the only launch plan, so the form now shows it as a fixed summary. The earlier mocked browser test hid this by calling `selectPlan('essential')` directly.
- **Landing page failed on non-JSON replies.** A server error produced "Unexpected token…". Signup and checkout now show plain-language messages and a "Continue to payment step" link.
- **Activation depended on a second Render service.** Jobs were only processed by the `rootcall-activation` worker, so customers waited forever if that service did not exist (Render creates new blueprint services only after a blueprint sync). The web service now also runs the same polling loop in a background thread. PostgreSQL advisory locks stop two runners activating the same account. Set `ACTIVATION_EMBEDDED_WORKER=false` to turn this off once the dedicated worker is confirmed running.
- **Database schema errors surface as clear JSON 503s** on every endpoint, and the web service logs `Database is missing tables ... run alembic upgrade head` at startup.
- **`APP_BASE_URL` falls back to Render's `RENDER_EXTERNAL_URL`** when unset, and startup logs a warning if `APP_BASE_URL` is empty, not https, or on a different host than the Render service.
- Each onboarding step now has its own heading and subtitle (the success page no longer shows the first step's subtitle).

Check in the Render dashboard (cannot be verified from the repository):

1. `getrootcall.com` currently serves a Hostinger "Your domain is expired" page and has no backend. Renew it, or do not use it as `APP_BASE_URL` or in Stripe settings. Stripe return links, password-reset emails and the Retell webhook are all built from `APP_BASE_URL`; if it points at a dead domain, customers pay but never see the success page. The working URL is `https://rootcall.onrender.com`.
2. Set these on the web service (the dashboard's Setup checks card on the admin page lists exactly which are missing; names only, never values): `STRIPE_SECRET_KEY`, `STRIPE_ESSENTIAL_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `TELNYX_API_KEY`, `RETELL_API_KEY`, `TELNYX_SIP_PASSWORD` and `TELNYX_OUTBOUND_VOICE_PROFILE_ID`. A missing value gives customers "Phone routing is not configured… no number was purchased" and logs `Activation blocked … set <names>`. These were introduced by automated onboarding and are not in the older `render_env_vars.txt` list.
   - `TELNYX_SIP_PASSWORD`: any long random secret you choose (for example `openssl rand -base64 24`). The app sets the same password on each customer's Telnyx SIP connection and on the matching Retell trunk, so no existing credential has to match it.
   - `TELNYX_OUTBOUND_VOICE_PROFILE_ID`: the ID of your Telnyx Outbound Voice Profile (Telnyx portal > Voice > Outbound Voice Profiles; the automation's default profile is named "RootCall US Outbound"). It is required because it is what attaches the SIP credentials to the connection.
   - `TELNYX_SIP_USERNAME` is optional and defaults to `rootcall` (each customer gets `rootcall_<id>`).
3. Confirm the startup log shows `Database schema upgraded to revision e254ab76f430` (first deploy only). If it shows `Automatic schema upgrade failed`, send the error that follows.

Regression test: `backend/tests/journey.browser.cjs` drives the real app (only Stripe, Retell and Telnyx faked by `backend/tests/e2e_journey_server.py`) from the landing page through activation and the success screen at 1280px and 390px. Start `python backend/tests/e2e_journey_server.py`, then run `PLAYWRIGHT_MODULE=<path> node backend/tests/journey.browser.cjs`.
