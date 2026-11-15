const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const failing of [false, true]) {
            const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
            const errors = [];
            page.on('pageerror', e => errors.push(e.message));
            await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('https://fonts.gstatic.com/**', r => r.abort());
            await page.route('https://cdnjs.cloudflare.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('https://esm.sh/**', r => r.fulfill({ contentType: 'application/javascript', body: 'export class RetellClient {}' }));
            await page.addInitScript(() => localStorage.setItem('access_token', 'tok'));
            const state = { routing: false, contacts: [], connectCalls: 0 };
            await page.route('**/api/**', route => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                const json = (data, status = 200) => route.fulfill({ status, json: data });
                if (path === '/api/rootcall/trusted-routing/1') {
                    state.connectCalls += 1;
                    if (failing) return json({ detail: 'Retell was unavailable.' }, 502);
                    state.routing = true;
                    return json({ success: true });
                }
                if (path === '/api/rootcall/trusted-contacts/1' && request.method() === 'POST') { state.contacts.push(request.postDataJSON().phone_number); return json({ ok: true }); }
                const map = {
                    '/api/auth/me': { id: 1, email: 'o@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' },
                    '/api/rootcall/voice-options': { voices: [] },
                    '/api/rootcall/my-number': { has_number: true, number: '+12025550100' },
                    '/api/rootcall/stats/1': { spam_blocked: 0, calls_screened: 0, trusted_calls: 0, total_calls: 0 },
                    '/api/rootcall/config/1': { line_configured: true, client_cell: '+12025550199', trusted_contacts: state.contacts, trusted_routing_enabled: state.routing, voice_id: '' },
                    '/api/rootcall/calls/1': [],
                    '/api/rootcall/live-calls': [],
                    '/api/payments/status': { managed: true, status: 'active', needs_attention: false, cancel_at_period_end: false, service_policy: 'warnings_only' },
                };
                return path in map ? json(map[path]) : json({}, 500);
            });
            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.waitForFunction(() => typeof dashboardLoading !== 'undefined' && !dashboardLoading && CLIENT_ID === 1);
            await page.evaluate(() => showPage('contacts'));
            assert.equal(await page.locator('#connect-trusted-routing').isVisible(), true, 'routing starts disconnected');
            await page.locator('#new-contact-name').fill('Mom');
            await page.locator('#new-contact').fill('(202) 555-0123');
            await page.evaluate(() => addContact());
            await page.waitForFunction(() => document.querySelectorAll('.toast').length > 0);
            await page.waitForTimeout(300);
            assert.equal(state.connectCalls, 1, 'adding a contact connects routing automatically');
            if (failing) {
                assert.match(await page.locator('.toast').last().innerText(), /will not skip screening yet/);
                assert.equal(await page.locator('#connect-trusted-routing').isVisible(), true, 'manual retry stays available');
            } else {
                assert.equal(await page.locator('#connect-trusted-routing').isVisible(), false);
                assert.match(await page.locator('#trusted-routing-status').innerText(), /connected\. Saved contacts skip screening/);
                await page.evaluate(() => { document.getElementById('new-contact').value = '(202) 555-0124'; return addContact(); });
                await page.waitForTimeout(300);
                assert.equal(state.connectCalls, 1, 'already connected, so no second call');
            }
            assert.deepEqual(errors, []);
            await page.close();
        }
        console.log('PASS trusted routing connects automatically when a contact is added');
    } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
