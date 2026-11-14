const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';
const shots = process.env.ROOTCALL_SHOTS || '';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            for (const hasNumber of [true, false]) {
                const context = await browser.newContext({ viewport: { width, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] });
                const page = await context.newPage();
                const errors = [];
                page.on('pageerror', e => errors.push(e.message));
                await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
                await page.route('https://fonts.gstatic.com/**', r => r.abort());
                await page.route('https://cdnjs.cloudflare.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
                await page.route('https://esm.sh/**', r => r.fulfill({ contentType: 'application/javascript', body: 'export class RetellClient {}' }));
                await page.addInitScript(() => localStorage.setItem('access_token', 'tok'));
                const now = new Date().toISOString();
                const calls = Array.from({ length: 7 }, (_, i) => ({
                    timestamp: now, from_number: `+1202555010${i}`, caller_name: i === 0 ? '<b>Mom</b>' : `Caller ${i}`,
                    action: i % 2 ? 'blocked' : 'trusted_bypass', status: i % 2 ? 'blocked' : 'completed',
                }));
                await page.route('**/api/**', route => {
                    const path = new URL(route.request().url()).pathname;
                    const map = {
                        '/api/auth/me': { id: 1, email: 'o@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' },
                        '/api/rootcall/voice-options': { voices: [] },
                        '/api/rootcall/my-number': hasNumber ? { has_number: true, number: '+12025550100', purchased_at: '2026-11-09T12:00:00Z' } : { has_number: false },
                        '/api/rootcall/stats/1': { spam_blocked: 3, calls_screened: 4, trusted_calls: 4, total_calls: 7 },
                        '/api/rootcall/config/1': { line_configured: true, client_cell: '+12025550199', trusted_contacts: [], trusted_routing_enabled: true, voice_id: '' },
                        '/api/rootcall/calls/1': hasNumber ? calls : [],
                        '/api/rootcall/live-calls': [],
                        '/api/payments/status': { managed: true, status: 'active', needs_attention: false, cancel_at_period_end: false, service_policy: 'warnings_only' },
                    };
                    if (path === '/api/rootcall/config/1' && !hasNumber) return route.fulfill({ status: 404, json: { detail: 'No phone number' } });
                    if (!(path in map)) return route.fulfill({ status: 500, json: {} });
                    return route.fulfill({ json: map[path] });
                });
                await page.goto(`${baseURL}/static/client-portal.html`);
                await page.waitForFunction(() => typeof dashboardLoading !== 'undefined' && !dashboardLoading && CLIENT_ID === 1);

                if (hasNumber) {
                    assert.equal(await page.locator('#hero-number').innerText(), '+1 (202) 555-0100');
                    assert.match(await page.locator('#hero-sub').innerText(), /555-0199/);
                    await page.locator('#copy-number').click();
                    await page.getByText('Copied').waitFor();
                    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), '+12025550100');
                    assert.equal(await page.locator('#recent-calls-list .recent-row').count(), 5, 'preview shows 5 newest');
                    assert.equal(await page.locator('#recent-calls-list b').count(), 0, 'names are not rendered as HTML');
                    await page.locator('#recent-calls .btn').click();
                    await page.locator('#page-activity.active').waitFor();
                    assert.equal(await page.locator('#call-history tr.call-row').count(), 7);
                } else {
                    assert.equal(await page.locator('#hero-number').innerText(), 'No Shield number yet');
                    await page.locator('#copy-number').click();
                    await page.locator('#provision-modal.active').waitFor();
                    assert.match(await page.locator('#recent-calls-list').innerText(), /No calls yet/);
                }

                await page.evaluate(() => showPage('settings'));
                const labels = await page.locator('#page-settings .settings-section-label').allInnerTexts();
                assert.deepEqual(labels.map(t => t.trim().toLowerCase()), ['your assistant', 'call handling & account', 'subscription']);
                const order = await page.evaluate(() => ['sync-agent-identity-btn', 'client-cell', 'user-email', 'manage-billing']
                    .map(id => document.getElementById(id).getBoundingClientRect().top + scrollY));
                assert.deepEqual([...order].sort((a, b) => a - b), order, 'settings read assistant, then calls, then account, then billing');
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal overflow');
                if (shots && hasNumber) {
                    await page.evaluate(() => showPage('dashboard'));
                    await page.waitForTimeout(500);
                    await page.screenshot({ path: `${shots}/home-${width}.png`, fullPage: true });
                    await page.evaluate(() => showPage('settings'));
                    await page.waitForTimeout(500);
                    await page.screenshot({ path: `${shots}/settings-${width}.png`, fullPage: true });
                }
                assert.deepEqual(errors, []);
                await context.close();
            }
            console.log(`PASS ${width}px: hero + copy, recent calls, test tips, regrouped settings`);
        }
    } finally {
        await browser.close();
    }
})().catch(e => { console.error(e); process.exit(1); });
