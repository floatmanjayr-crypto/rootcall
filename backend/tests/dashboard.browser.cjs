const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({ viewport: { width, height: 1000 } });
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            page.on('dialog', dialog => dialog.accept());
            await page.addInitScript(() => localStorage.setItem('access_token', 'dashboard-test-token'));
            await page.route('https://esm.sh/**', route => route.fulfill({
                contentType: 'application/javascript', body: 'export class RetellClient {}',
            }));
            let failStats = false;
            let failExport = true;
            let holdStats = false;
            let releaseStats;
            let hasNumber = true;
            let billingUnavailable = false;
            let billingIssue = true;
            let cancellationScheduled = false;
            let selectedVoice = 'voice-one';
            let failVoice = true;
            let contacts = [];
            const unsafeName = '<img src=x onerror="window.unsafeExecuted=true"> Mom';
            const csv = "Timestamp,From,Caller Name,Action,Status\n2026-11-09,'+12025550101,Mom,trusted_bypass,failed\n";
            await page.route('**/api/**', async route => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                assert.equal(request.headers().authorization, 'Bearer dashboard-test-token');
                let result = {};
                if (path === '/api/auth/me') {
                    result = { id: 1, email: 'owner@example.com', full_name: 'Jordan Green', next_url: '/static/client-portal.html' };
                } else if (path === '/api/rootcall/voice-options') {
                    result = { voices: [{ voice_id: 'voice-one', voice_name: 'Avery', provider: 'Test' },
                        { voice_id: 'voice-two', voice_name: 'Jordan', provider: 'Test' }] };
                } else if (path === '/api/rootcall/my-number') {
                    result = { has_number: hasNumber, number: '+12025550100', purchased_at: '2026-11-09T12:00:00Z' };
                } else if (path === '/api/rootcall/stats/1') {
                    if (holdStats) await new Promise(resolve => { releaseStats = resolve; });
                    if (failStats) return route.fulfill({ status: 503, json: { detail: 'Stats unavailable' } });
                    result = { spam_blocked: 0, calls_screened: 1, trusted_forwarded: 0, trusted_calls: 1, total_calls: 2 };
                } else if (path === '/api/rootcall/config/1') {
                    if (request.method() === 'PATCH') {
                        const body = request.postDataJSON();
                        assert.ok(body.voice_id);
                        if (failVoice) return route.fulfill({ status: 502, json: { detail: 'Voice update rejected by provider' } });
                        selectedVoice = body.voice_id;
                        return route.fulfill({ json: { success: true, voice_id: selectedVoice } });
                    }
                    if (!hasNumber) return route.fulfill({ status: 404, json: { detail: 'No phone number' } });
                    result = {
                        line_configured: true, client_cell: '+12025550102', setup_guide_available: true,
                        trusted_contacts: contacts, trusted_routing_enabled: true,
                        voice_id: selectedVoice,
                    };
                } else if (path === '/api/rootcall/calls/1') {
                    result = hasNumber ? [{
                        timestamp: '2026-11-09T12:00:00+00:00', from_number: '+12025550101',
                        caller_name: unsafeName, action: 'trusted_bypass', status: 'failed',
                    }] : [];
                } else if (path === '/api/rootcall/live-calls') {
                    result = [];
                } else if (path === '/api/payments/status') {
                    if (billingUnavailable) return route.fulfill({ status: 502, json: { detail: 'Billing offline' } });
                    result = {
                        managed: true, status: billingIssue ? 'past_due' : 'active',
                        needs_attention: billingIssue, cancel_at_period_end: cancellationScheduled,
                        current_period_end: '2027-01-15T08:00:00+00:00', service_policy: 'warnings_only',
                    };
                } else if (path === '/api/rootcall/trusted-contacts/1') {
                    const body = request.postDataJSON();
                    contacts = [{ phone_number: body.phone_number, name: body.name }];
                    result = { success: true };
                } else if (path.startsWith('/api/rootcall/trusted-contacts/1/')) {
                    assert.equal(request.method(), 'DELETE');
                    assert.equal(decodeURIComponent(path.split('/').pop()), '+12025550101');
                    contacts = [];
                    result = { success: true };
                } else if (path === '/api/rootcall/export/1') {
                    if (failExport) return route.fulfill({ status: 502, json: { detail: 'Export unavailable. Retry.' } });
                    return route.fulfill({ contentType: 'text/csv', body: csv });
                } else {
                    throw new Error(`Unexpected dashboard API: ${request.method()} ${path}`);
                }
                return route.fulfill({ json: result });
            });
            await page.goto(`${baseURL}/static/client-portal.html`);
            await page.getByText('Shield line configured', { exact: true }).first().waitFor();
            await page.waitForFunction(() => !dashboardLoading);
            assert.equal(await page.locator('#dashboard-error').isVisible(), false);
            assert.equal(await page.locator('#trusted-connected').textContent(), '1');
            assert.equal(await page.locator('#total-calls-summary').textContent(), '2');
            await page.locator('#billing-notice').waitFor({ state: 'visible' });
            assert.match(await page.locator('#billing-notice-text').textContent(), /past due.*needs attention/);
            await page.evaluate(() => showPage('settings'));
            assert.equal(await page.locator('#retell-voice-select').inputValue(), 'voice-one');
            await page.locator('#retell-voice-select').selectOption('voice-two');
            await page.locator('.toast').filter({ hasText: 'Voice update rejected by provider' }).waitFor();
            await page.waitForFunction(() => document.getElementById('retell-voice-select').value === 'voice-one');
            failVoice = false;
            await page.locator('#retell-voice-select').selectOption('voice-two');
            await page.locator('.toast').filter({ hasText: 'Your agent voice has been updated' }).waitFor();
            await page.waitForFunction(() => document.getElementById('retell-voice-select').value === 'voice-two');
            await page.locator('#setup-guide-link').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#setup-guide-link').getAttribute('href'), '/static/onboarding.html');
            billingUnavailable = true;
            await page.locator('#refresh-billing').click();
            await page.getByText('Billing status could not be verified. Please retry or contact support.', { exact: true }).first().waitFor();
            assert.equal(await page.locator('#refresh-billing').isDisabled(), false);
            billingUnavailable = false;
            billingIssue = false;
            cancellationScheduled = true;
            await page.locator('#refresh-billing').click();
            await page.locator('#billing-status').filter({ hasText: 'Cancellation scheduled for' }).waitFor();
            cancellationScheduled = false;
            await page.locator('#refresh-billing').click();
            await page.locator('#billing-notice').waitFor({ state: 'hidden' });
            assert.equal(await page.locator('#call-history img').count(), 0);
            assert.equal(await page.evaluate(() => window.unsafeExecuted), undefined);
            await page.evaluate(() => showPage('contacts'));
            await page.locator('#new-contact').fill('+12025550101');
            await page.locator('#new-contact-name').fill(unsafeName);
            await page.getByRole('button', { name: 'Save Contact', exact: true }).click();
            await page.locator('#contacts-list').getByText(unsafeName, { exact: true }).waitFor();
            assert.equal(await page.locator('#contacts-list img').count(), 0);
            await page.reload();
            await page.waitForFunction(() => !dashboardLoading && CLIENT_ID === 1);
            await page.evaluate(() => showPage('contacts'));
            await page.locator('#contacts-list').getByText(unsafeName, { exact: true }).waitFor();
            await page.locator('[data-remove-contact]').click();
            await page.locator('#contacts-list').getByText('No trusted contacts yet. Add your first contact above!', { exact: true }).waitFor();
            assert.equal(await page.locator('#contacts-list .empty-state').count(), 1);
            const nav = page.locator('nav[aria-label="Dashboard sections"]');
            assert.equal(await nav.locator('button.nav-item[data-page="contacts"]').getAttribute('aria-current'), 'page');
            assert.equal(await nav.locator('[aria-current="page"]').count(), 1);
            if (width <= 1024) {
                assert.equal(await page.locator('#sidebar').evaluate(node => getComputedStyle(node).visibility), 'hidden');
                await page.locator('.mobile-menu-btn').click();
                assert.equal(await page.locator('.mobile-menu-btn').getAttribute('aria-expanded'), 'true');
                await page.locator('#sidebar').waitFor({ state: 'visible' });
            }
            await nav.locator('button.nav-item[data-page="settings"]').focus();
            await page.keyboard.press('Enter');
            assert.equal(await nav.locator('button.nav-item[data-page="settings"]').getAttribute('aria-current'), 'page');
            assert.equal(await page.locator('#page-settings').evaluate(node => node.classList.contains('active')), true);
            for (const selector of ['.tagline', '.nav-label', '.scam-shield-badge']) {
                assert.ok(await page.locator(selector).first().evaluate(node => parseFloat(getComputedStyle(node).fontSize)) >= 12, `${selector} is at least 12px`);
            }
            await page.evaluate(() => showPage('contacts'));
            await page.evaluate(() => showPage('activity'));
            await page.locator('#export-calls').click();
            await page.locator('.toast').filter({ hasText: 'Export unavailable. Retry.' }).waitFor();
            assert.equal(await page.locator('#export-calls').isDisabled(), false);
            failExport = false;
            const downloadPromise = page.waitForEvent('download');
            await page.locator('#export-calls').click();
            const download = await downloadPromise;
            assert.equal(download.suggestedFilename(), 'rootcall_calls.csv');
            assert.equal(await fs.readFile(await download.path(), 'utf8'), csv);
            await download.delete();
            holdStats = true;
            await page.evaluate(() => { window.refreshPromise = loadData(true); });
            await page.waitForFunction(() => dashboardLoading);
            assert.equal(await page.locator('#loading-overlay').evaluate(node => node.classList.contains('active')), false);
            while (!releaseStats) await new Promise(resolve => setTimeout(resolve, 10));
            releaseStats();
            await page.evaluate(() => window.refreshPromise);
            holdStats = false;
            failStats = true;
            await page.evaluate(() => loadData(true));
            await page.locator('#dashboard-error').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#protection-status').textContent(), 'Line status unavailable');
            assert.equal(await page.locator('#total-calls-summary').textContent(), '--');
            failStats = false;
            await page.locator('#dashboard-error').getByRole('button', { name: 'Retry' }).click();
            await page.locator('#dashboard-error').waitFor({ state: 'hidden' });
            assert.equal(await page.locator('#total-calls-summary').textContent(), '2');
            hasNumber = false;
            await page.evaluate(() => loadData());
            assert.equal(await page.locator('#protection-status').textContent(), 'Choose and configure your Shield line');
            assert.equal(await page.locator('#dashboard-error').isVisible(), false);
            await page.evaluate(() => showPage('numbers'));
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: billing warning/dates/error/recovery, safe contact/history rendering, authenticated CSV, quiet refresh, honest error/retry`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
