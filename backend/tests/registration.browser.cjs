const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';

async function quiet(page) {
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
    await page.route('https://fonts.gstatic.com/**', r => r.abort());
    await page.route('https://cdnjs.cloudflare.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            // ---- Signup dialog ----
            let page = await browser.newPage({ viewport: { width, height: 900 } });
            const errors = [];
            page.on('pageerror', e => errors.push(e.message));
            await quiet(page);
            const signups = [];
            let signupReply = { status: 200, json: { access_token: 't' } };
            await page.route('**/api/**', route => {
                const path = new URL(route.request().url()).pathname;
                if (path === '/api/auth/signup') {
                    signups.push(route.request().postDataJSON());
                    return route.fulfill(signupReply);
                }
                return route.fulfill({ status: 500, json: { detail: 'unexpected ' + path } });
            });
            await page.goto(`${baseURL}/static/index.html`);
            const dialog = page.locator('#signup-modal');
            assert.equal(await dialog.getAttribute('role'), 'dialog');
            assert.equal(await dialog.getAttribute('aria-modal'), 'true');
            await page.locator('.hero a.btn-primary').click();
            await dialog.waitFor({ state: 'visible' });
            await page.waitForFunction(() => document.activeElement && document.activeElement.id === 'signup-name');
            await page.keyboard.press('Escape');
            assert.equal(await dialog.isVisible(), false, 'Escape closes');
            await page.locator('.hero a.btn-primary').click();
            await page.locator('.close-modal').click();
            assert.equal(await dialog.isVisible(), false, 'close button closes');
            await page.locator('.hero a.btn-primary').click();
            await page.mouse.click(5, 5);
            assert.equal(await dialog.isVisible(), false, 'backdrop closes');

            await page.locator('.hero a.btn-primary').click();
            await page.locator('#signup-email').fill('a@example.com');
            await page.locator('#signup-password').fill('a-strong-password-123');
            await page.locator('#signup-name').fill('Jordan');
            await page.locator('#signup-modal button[type="submit"]').click();
            await page.locator('#modal-message').getByText(/first and last name/).waitFor();
            assert.equal(signups.length, 0, 'one-word names are not sent');

            const field = page.locator('#signup-password');
            assert.equal(await field.getAttribute('type'), 'password');
            await page.locator('#toggle-password').click();
            assert.equal(await field.getAttribute('type'), 'text');
            await page.locator('#toggle-password').click();
            assert.equal(await field.getAttribute('type'), 'password');
            assert.equal(await dialog.locator('a[href="/static/terms.html"]').count(), 1);
            assert.equal(await dialog.locator('a[href="/static/privacy.html"]').count(), 1);

            signupReply = { status: 400, json: { detail: 'Email already registered' } };
            await page.locator('#signup-name').fill('  Jordan   Green ');
            await page.locator('#signup-modal button[type="submit"]').click();
            await page.locator('#modal-message a[href="/static/login.html"]').waitFor();
            assert.equal(await page.locator('#modal-message a[href="/static/forgot-password.html"]').count(), 1);
            assert.equal(signups[0].full_name || signups[0].name, 'Jordan Green', 'name is tidied before sending');
            assert.equal(await page.locator('#signup-modal button[type="submit"]').isDisabled(), false, 'button usable again');
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            await page.close();

            // ---- Success page ----
            for (const scenario of ['confirmed', 'late', 'never', 'signed-out']) {
                page = await browser.newPage({ viewport: { width, height: 900 } });
                await quiet(page);
                const failures = [];
                page.on('pageerror', e => failures.push(e.message));
                let calls = 0;
                const verifyCalls = [];
                if (scenario !== 'signed-out') await page.addInitScript(() => localStorage.setItem('access_token', 'tok'));
                await page.route('**/api/**', route => {
                    const path = new URL(route.request().url()).pathname;
                    if (path === '/api/payments/verify') verifyCalls.push(path);
                    if (path !== '/api/payments/status') return route.fulfill({ status: 500, json: {} });
                    calls += 1;
                    const ok = scenario === 'confirmed' || (scenario === 'late' && calls >= 2);
                    return route.fulfill({ json: ok ? { billing_available: true, managed: false, status: 'active' } : { billing_available: false } });
                });
                await page.clock.install();
                await page.goto(`${baseURL}/static/success.html?session_id=cs_test`);
                if (scenario === 'signed-out') {
                    await page.getByText('Please sign in to continue').waitFor();
                    assert.equal(calls, 0);
                } else if (scenario === 'never') {
                    await page.getByText('Confirming your payment...').first().waitFor();
                    assert.equal(await page.locator('#success-details').isVisible(), false, 'no success before confirmation');
                    for (let i = 0; i < 12; i++) await page.clock.runFor(2100);
                    await page.locator('#delayed').waitFor({ state: 'visible' });
                    assert.equal(await page.locator('#success-details').isVisible(), false, 'never claims success without payment');
                    assert.match(await page.locator('#delayed').innerText(), /info@getrootcall\.com/);
                    assert.equal(await page.getByRole('button', { name: 'Check again' }).count(), 1);
                } else {
                    if (scenario === 'late') await page.clock.runFor(2100);
                    await page.locator('#success-details').waitFor({ state: 'visible' });
                    assert.match(await page.locator('body').innerText(), /Welcome to RootCall/);
                    assert.equal(await page.locator('#success-details li').count(), 3);
                }
                assert.equal(verifyCalls.length, 0, 'does not use the wizard verify endpoint');
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
                assert.deepEqual(failures, []);
                await page.close();
            }

            // ---- Call activity ----
            page = await browser.newPage({ viewport: { width, height: 1000 } });
            const portalErrors = [];
            page.on('pageerror', e => portalErrors.push(e.message));
            await quiet(page);
            await page.addInitScript(() => localStorage.setItem('access_token', 'tok'));
            await page.route('https://esm.sh/**', r => r.fulfill({ contentType: 'application/javascript', body: 'export class RetellClient {}' }));
            const now = new Date().toISOString();
            const calls = [
                { timestamp: now, from_number: '+12025550111', caller_name: 'Mom', action: 'trusted_bypass', status: 'completed' },
                { timestamp: now, from_number: '+12025550122', caller_name: '<img src=x onerror=window.__pwn=1>', action: 'blocked', status: 'blocked' },
                { timestamp: now, from_number: '+12025550133', caller_name: 'Alex Rivera', action: 'screened', status: 'in-progress' },
                { timestamp: null, from_number: null, caller_name: null, action: 'received', status: 'weird_status' },
            ];
            await page.route('**/api/**', route => {
                const path = new URL(route.request().url()).pathname;
                const map = {
                    '/api/auth/me': { id: 1, email: 'o@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' },
                    '/api/rootcall/voice-options': { voices: [] },
                    '/api/rootcall/my-number': { has_number: true, number: '+12025550100', purchased_at: '2026-11-09T12:00:00Z' },
                    '/api/rootcall/stats/1': { spam_blocked: 1, calls_screened: 2, trusted_calls: 1, total_calls: 4 },
                    '/api/rootcall/config/1': { line_configured: true, client_cell: '+12025550199', trusted_contacts: [], trusted_routing_enabled: true, voice_id: '' },
                    '/api/rootcall/calls/1': calls,
                    '/api/rootcall/live-calls': [],
                    '/api/payments/status': { managed: true, status: 'active', needs_attention: false, cancel_at_period_end: false, service_policy: 'warnings_only' },
                };
                if (!(path in map)) return route.fulfill({ status: 500, json: {} });
                return route.fulfill({ json: map[path] });
            });
            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.waitForFunction(() => typeof dashboardLoading !== 'undefined' && !dashboardLoading && CLIENT_ID === 1);
            await page.evaluate(() => showPage('activity'));
            const rows = page.locator('#call-history tr.call-row');
            await rows.first().waitFor();
            assert.equal(await rows.count(), 4);
            const text = await page.locator('#call-history').innerText();
            assert.match(text, /Trusted contact, connected to you/);
            assert.match(text, /Blocked by your shield/);
            assert.match(text, /Screened by your assistant/);
            assert.match(text, /In progress/);
            assert.match(text, /Unknown caller/);
            assert.doesNotMatch(text, /trusted_bypass/);
            assert.equal(await page.locator('#call-history img').count(), 0);
            assert.equal(await page.evaluate(() => window.__pwn), undefined);

            await page.locator('.chip[data-filter="blocked"]').click();
            assert.equal(await rows.count(), 1);
            assert.equal(await page.locator('.chip[data-filter="blocked"]').getAttribute('aria-pressed'), 'true');
            await page.locator('.chip[data-filter="trusted"]').click();
            assert.equal(await rows.count(), 1);
            await page.locator('.chip[data-filter="all"]').click();
            await page.locator('#activity-search').fill('555-0133');
            assert.equal(await rows.count(), 1);
            await page.locator('#activity-search').fill('alex');
            assert.equal(await rows.count(), 1);
            await page.locator('#activity-search').fill('zzzz');
            assert.equal(await rows.count(), 0);
            await page.getByText('No calls match').waitFor();
            await page.locator('#activity-search').fill('');
            assert.equal(await rows.count(), 4);
            assert.deepEqual(portalErrors, []);
            await page.close();
            console.log(`PASS ${width}px: signup dialog, honest success page, call activity filters`);
        }
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
