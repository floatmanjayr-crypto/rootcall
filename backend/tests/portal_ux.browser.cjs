const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';
const shots = process.env.ROOTCALL_SHOTS || '';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({ viewport: { width, height: 1000 } });
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.addInitScript(() => localStorage.setItem('access_token', 'ux-test-token'));
            await page.route('https://esm.sh/**', route => route.fulfill({
                contentType: 'application/javascript', body: 'export class RetellClient {}',
            }));
            await page.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('https://fonts.gstatic.com/**', route => route.abort());
            await page.route('https://cdnjs.cloudflare.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));

            let hasNumber = false;
            let forwarding = '';
            let totalCalls = 0;
            let syncStatus = 200;
            const saved = { phones: [], contacts: [], names: [], syncs: 0 };
            await page.route('**/api/**', async route => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                let result = {};
                if (path === '/api/auth/me') {
                    result = { id: 1, email: 'owner@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' };
                } else if (path === '/api/rootcall/voice-options') {
                    result = { voices: [{ voice_id: 'voice-one', voice_name: 'Avery', provider: 'Test' }] };
                } else if (path === '/api/rootcall/my-number') {
                    result = hasNumber ? { has_number: true, number: '+12025550100', purchased_at: '2026-11-09T12:00:00Z' } : { has_number: false };
                } else if (path === '/api/rootcall/stats/1') {
                    result = { spam_blocked: 0, calls_screened: totalCalls, trusted_calls: 0, total_calls: totalCalls };
                } else if (path === '/api/rootcall/config/1') {
                    if (request.method() === 'PATCH') {
                        const body = request.postDataJSON();
                        if (body.client_cell) { saved.phones.push(body.client_cell); forwarding = body.client_cell; }
                        if (body.full_name) saved.names.push(body.full_name);
                        return route.fulfill({ json: { success: true } });
                    }
                    if (!hasNumber) return route.fulfill({ status: 404, json: { detail: 'No phone number' } });
                    result = { line_configured: Boolean(forwarding), client_cell: forwarding, trusted_contacts: [], trusted_routing_enabled: true, voice_id: 'voice-one' };
                } else if (path === '/api/rootcall/sync-agent-identity/1') {
                    saved.syncs += 1;
                    return route.fulfill({ status: syncStatus, json: syncStatus === 200 ? { success: true } : { detail: 'No Retell screening agent is configured' } });
                } else if (path === '/api/rootcall/trusted-contacts/1') {
                    saved.contacts.push(request.postDataJSON().phone_number);
                    result = { success: true };
                } else if (path === '/api/rootcall/calls/1') {
                    result = [];
                } else if (path === '/api/rootcall/live-calls') {
                    result = [];
                } else if (path === '/api/payments/status') {
                    result = { managed: true, status: 'active', needs_attention: false, cancel_at_period_end: false, service_policy: 'warnings_only' };
                } else {
                    throw new Error(`Unexpected API: ${request.method()} ${path}`);
                }
                return route.fulfill({ json: result });
            });

            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.waitForFunction(() => typeof dashboardLoading !== 'undefined' && !dashboardLoading && CLIENT_ID === 1);

            // New customer: checklist shows all three steps, none done.
            const steps = page.locator('#get-started-steps li');
            assert.equal(await page.locator('#get-started').isVisible(), true);
            assert.equal(await steps.count(), 3);
            assert.equal(await page.locator('#get-started-steps li.done').count(), 0);
            assert.equal(await page.locator('#get-started-progress').textContent(), '0 of 3 done');
            if (shots) await page.screenshot({ path: `${shots}/dashboard-new-${width}.png`, fullPage: true });

            // Empty state tucks the recovery form away until asked for.
            await page.evaluate(() => showPage('numbers'));
            assert.equal(await page.locator('#recovery-number').isVisible(), false);
            await page.getByText('Already bought a number? Finish setup').click();
            assert.equal(await page.locator('#recovery-number').isVisible(), true);
            if (shots) await page.screenshot({ path: `${shots}/numbers-empty-${width}.png`, fullPage: true });

            // Number but no phone: step 1 done, step 2 shows an action that jumps to Settings.
            hasNumber = true;
            await page.evaluate(() => loadData(true));
            await page.waitForFunction(() => document.getElementById('get-started-progress').textContent === '1 of 3 done');
            await page.evaluate(() => showPage('dashboard'));
            await page.getByRole('button', { name: 'Add my phone' }).click();
            assert.equal(await page.locator('#page-settings').evaluate(node => node.classList.contains('active')), true);
            assert.equal(await page.evaluate(() => document.activeElement.id), 'client-cell');
            assert.match(await page.locator('#get-started-steps').textContent(), /\(202\) 555-0100/);

            // Phones accept normal formats and are saved in international format.
            await page.locator('#client-cell').fill('(407) 555-0100');
            await page.getByRole('button', { name: 'Save forwarding number' }).click();
            await page.locator('.toast').filter({ hasText: 'Saved. Screened calls will ring this phone.' }).waitFor();
            assert.deepEqual(saved.phones, ['+14075550100']);
            assert.equal(await page.locator('#client-cell').inputValue(), '+14075550100');
            await page.waitForFunction(() => document.getElementById('get-started-progress').textContent === '2 of 3 done');
            await page.locator('#client-cell').fill('12345');
            await page.getByRole('button', { name: 'Save forwarding number' }).click();
            await page.locator('.toast').filter({ hasText: 'Enter a full phone number, like (407) 555-0100.' }).waitFor();
            assert.deepEqual(saved.phones, ['+14075550100']);
            await page.evaluate(() => showPage('contacts'));
            await page.locator('#new-contact').fill('1-202-555-0188');
            await page.getByRole('button', { name: 'Save Contact', exact: true }).click();
            await page.waitForFunction(() => document.getElementById('new-contact').value === '');
            assert.deepEqual(saved.contacts, ['+12025550188']);

            // Changing the name updates the agent too; a missing line is explained, not an error.
            await page.evaluate(() => showPage('settings'));
            await page.locator('#user-fullname').fill('Jordan Bo');
            await page.getByRole('button', { name: 'Save name' }).click();
            await page.locator('.toast').filter({ hasText: 'Name saved. Your agent now recognizes it.' }).waitFor();
            assert.deepEqual(saved.names, ['Jordan Bo']);
            assert.equal(saved.syncs, 1);
            syncStatus = 409;
            await page.locator('#user-fullname').fill('Jordan Bo Jr');
            await page.getByRole('button', { name: 'Save name' }).click();
            await page.locator('.toast').filter({ hasText: 'It will apply when your Shield line is set up.' }).waitFor();

            // No vendor names in anything a customer reads on the settings page.
            const settingsText = await page.locator('#page-settings').innerText();
            assert.doesNotMatch(settingsText, /retell|telnyx/i);
            assert.doesNotMatch(await page.locator('#provision-modal').innerText(), /retell|telnyx/i);

            // First call placed: checklist completes and disappears.
            totalCalls = 1;
            await page.evaluate(() => loadData(true));
            await page.waitForFunction(() => document.getElementById('get-started').hidden === true);
            if (shots) { await page.evaluate(() => showPage('settings')); await page.screenshot({ path: `${shots}/settings-${width}.png`, fullPage: true }); }
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: setup checklist, friendly phone input, name updates agent, plain-language copy`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
