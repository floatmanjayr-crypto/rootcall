const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';
const sdkMock = `
export class RetellClient {
    constructor(options) { this.options = options; }
    monitorCall(options) {
        const emit = (state) => { session.status = state; options.hooks.onStatus(state); };
        const session = {
            status: 'monitoring',
            listen: async () => {
                await this.options.fetch('https://api.retellai.com/v2/listen-live-call/call_test', { method: 'POST' });
                emit('listening');
            },
            stopListening: () => emit('monitoring'),
            takeOver: async () => {
                if (window.denyMicrophone) throw new Error('Microphone access denied');
                await this.options.fetch('https://api.retellai.com/v2/take-over-live-call/call_test', {
                    method: 'POST', body: JSON.stringify({ participant_id: 'listener_test' })
                });
                emit('taken_over');
            },
            disconnect: () => emit('ended'), end: async () => emit('ended'), mute() {}, unmute() {},
        };
        return session;
    }
}`;

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
            const page = await browser.newPage({ viewport });
            const errors = [];
            page.on('pageerror', (error) => errors.push(error.message));
            let takeovers = 0;
            let billingAttempts = 0;
            let routingAttempts = 0;
            let trustedRouting = false;
            const call = { id: 1, retell_call_id: 'call_test', from_number: '+12025550101', to_number: '+12025550100', status: 'in-progress' };
            await page.addInitScript(() => {
                if (!sessionStorage.getItem('test-initialized')) {
                    const payload = btoa(JSON.stringify({ sub: '1', email: 'owner@example.com' }));
                    localStorage.setItem('access_token', `test.${payload}.test`);
                    sessionStorage.setItem('test-initialized', 'true');
                }
            });
            await page.route('https://esm.sh/retell-client-js-sdk@3.0.3', (route) => route.fulfill({ contentType: 'application/javascript', body: sdkMock }));
            await page.route('**/billing-test', (route) => route.fulfill({ contentType: 'text/html', body: '<h1>Test billing portal</h1>' }));
            await page.route('**/api/**', async (route) => {
                const path = new URL(route.request().url()).pathname;
                let result = {};
                if (path === '/api/auth/me') result = { id: 1, email: 'owner@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' };
                else if (path === '/api/rootcall/my-number') result = { has_number: true, number: '+12025550100', purchased_at: '2026-11-09T12:00:00Z' };
                else if (path === '/api/payments/billing-portal') {
                    billingAttempts += 1;
                    if (billingAttempts === 1) return route.fulfill({ status: 502, json: { detail: 'Billing management is unavailable. Please retry.' } });
                    result = { portal_url: `${baseURL}/billing-test` };
                }
                else if (path === '/api/rootcall/live-calls') result = [call];
                else if (path === '/api/rootcall/trusted-routing/1') {
                    routingAttempts += 1;
                    if (routingAttempts === 1) return route.fulfill({ status: 502, json: { detail: 'Trusted routing could not be connected.' } });
                    trustedRouting = true;
                    result = { success: true, trusted_routing_enabled: true };
                }
                else if (path.endsWith('/transcript')) {
                    const events = [
                        { type: 'transcript_snapshot', transcripts: [{ id: 'agent_0', role: 'agent', time_sec: 0, content: 'Who is' }] },
                        { type: 'transcript_updated', transcripts: [{ id: 'agent_0', role: 'agent', time_sec: 0, content: 'Who is calling?' }] },
                        { type: 'transcript_updated', transcripts: [{ id: 'user_0', role: 'user', time_sec: 1, content: '<img src=x onerror=alert(1)> Sam' }] },
                    ];
                    return route.fulfill({ contentType: 'text/event-stream', body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('') });
                } else if (path.endsWith('/takeover')) { takeovers += 1; result = { success: true }; }
                else if (path.includes('/stats/')) result = { spam_blocked: 0, calls_screened: 1, trusted_forwarded: 0 };
                else if (path.includes('/config/')) result = { trusted_contacts: [], trusted_routing_enabled: trustedRouting };
                else if (path.includes('/calls/')) result = [];
                await route.fulfill({ json: result });
            });
            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.locator('#live-call-list button').click();
            await page.locator('.live-turn').filter({ hasText: 'Who is calling?' }).waitFor();
            assert.equal(await page.locator('.live-turn[data-role="agent"]').count(), 1);
            assert.equal(await page.locator('#live-transcript img').count(), 0);
            await page.locator('#live-listen').click();
            await page.getByText('Listening live - microphone off', { exact: true }).waitFor();
            await page.evaluate(() => { window.denyMicrophone = true; });
            page.on('dialog', (dialog) => dialog.accept());
            await page.locator('#live-takeover').click();
            await page.getByText('Microphone access denied', { exact: true }).waitFor();
            assert.equal(takeovers, 0);
            await page.evaluate(() => { window.denyMicrophone = false; });
            await page.locator('#live-takeover').click();
            await page.getByText('You are on the call. AI stopped; transcription paused.', { exact: true }).waitFor();
            assert.equal(takeovers, 1);
            assert.equal(await page.locator('#live-takeover').isDisabled(), true);
            await page.locator('#live-mute').click();
            assert.equal(await page.locator('#live-mute').getAttribute('aria-pressed'), 'true');
            const overflow = await page.locator('.live-calls').evaluate((node) => node.scrollWidth > node.clientWidth);
            assert.equal(overflow, false);
            await page.locator('.live-calls').screenshot({ path: `/tmp/rootcall-live-${viewport.width}.png` });
            await page.locator('#live-leave').click();
            await page.evaluate(() => window.showPage('contacts'));
            await page.locator('#connect-trusted-routing').waitFor({ state: 'visible' });
            await page.locator('#connect-trusted-routing').click();
            await page.locator('.toast').filter({ hasText: 'Trusted routing could not be connected.' }).waitFor();
            assert.equal(await page.locator('#connect-trusted-routing').isDisabled(), false);
            await page.locator('#connect-trusted-routing').click();
            await page.getByText('Trusted caller routing is connected. Saved contacts skip screening and transfer to your forwarding phone.', { exact: true }).waitFor();
            assert.equal(await page.locator('#connect-trusted-routing').isVisible(), false);
            assert.equal(routingAttempts, 2);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            await page.evaluate(() => window.showPage('numbers'));
            assert.equal(await page.locator('#get-shield-number').isVisible(), false);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            await page.evaluate(() => window.showPage('settings'));
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            await page.screenshot({ path: `/tmp/rootcall-account-${viewport.width}.png`, fullPage: true });
            await page.locator('#manage-billing').click();
            await page.locator('.toast').filter({ hasText: 'Billing management is unavailable. Please retry.' }).waitFor();
            assert.equal(await page.locator('#manage-billing').isDisabled(), false);
            await page.locator('#manage-billing').click();
            await page.waitForURL('**/billing-test');
            assert.equal(billingAttempts, 2);
            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.locator('#live-call-list button').waitFor();
            await page.evaluate(() => {
                localStorage.setItem('token', 'old-token');
                localStorage.setItem('user', '{"id":1}');
                localStorage.setItem('selected_plan', 'essential');
            });
            const signout = page.locator('#account-signout');
            assert.equal(await signout.isVisible(), true);
            assert.equal(await signout.evaluate((node) => {
                const bounds = node.getBoundingClientRect();
                return bounds.left >= 0 && bounds.right <= innerWidth && bounds.top >= 0 && bounds.bottom <= innerHeight;
            }), true);
            await signout.click();
            await page.waitForURL('**/static/login.html');
            for (const key of ['access_token', 'token', 'user', 'selected_plan']) {
                assert.equal(await page.evaluate((name) => localStorage.getItem(name), key), null);
            }
            assert.deepEqual(errors, []);
            console.log(`PASS ${viewport.width}px: takeover, trusted-routing connect/failure/retry, billing, visible sign out/session cleanup, no overflow`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch((error) => { console.error(error); process.exitCode = 1; });