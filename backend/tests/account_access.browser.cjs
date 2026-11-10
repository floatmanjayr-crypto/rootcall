const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({ viewport: { width, height: 1000 } });
            const errors = [];
            const resetDocumentURLs = [];
            page.on('pageerror', error => errors.push(error.message));
            page.on('request', request => {
                if (request.isNavigationRequest() && request.url().includes('/static/reset-password.html')) {
                    resetDocumentURLs.push(request.url());
                }
            });
            await page.addInitScript(() => {
                if (!sessionStorage.getItem('access-test-started')) {
                    localStorage.setItem('access_token', 'admin-browser-test-token');
                    sessionStorage.setItem('access-test-started', 'true');
                }
            });
            let adminAccess = true;
            let expired = false;
            let denyAdminAPI = false;
            let unavailable = false;
            let dashboardRequests = 0;
            let resetRequests = 0;
            let resetUnavailable = true;
            let emailUnavailable = true;
            let recoveryAttempts = 0;
            let recovered = false;
            const unsafeName = '<img src=x onerror="window.unsafeExecuted=true"> Admin';
            await page.route('**/api/**', async route => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                let result = {};
                if (path === '/api/auth/me') {
                    assert.equal(request.headers().authorization, 'Bearer admin-browser-test-token');
                    if (expired) return route.fulfill({ status: 401, json: { detail: 'Expired' } });
                    result = { id: 1, email: 'admin@example.com', is_superuser: adminAccess };
                } else if (path === '/api/admin/dashboard') {
                    dashboardRequests += 1;
                    assert.equal(request.headers().authorization, 'Bearer admin-browser-test-token');
                    if (denyAdminAPI) return route.fulfill({ status: 403, json: { detail: 'Forbidden' } });
                    if (unavailable) return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
                    result = {
                        readiness: [
                            { name: 'Database', purpose: 'Saved setup progress', ok: true, missing: [] },
                            { name: 'Phone routing', purpose: 'Buying numbers', ok: false,
                              missing: ['TELNYX_API_KEY'] },
                        ],
                        stats: { total_users: 3, total_shield_numbers: 1, total_calls: 2, spam_blocked: 0 },
                        recent_users: [{ id: 1, full_name: unsafeName, email: 'admin@example.com' }],
                    };
                } else if (path === '/api/auth/reset-password') {
                    resetRequests += 1;
                    const body = request.postDataJSON();
                    assert.equal(body.token, 'browser-reset-token');
                    assert.equal(body.new_password, 'new-password-123');
                    if (resetUnavailable) return route.fulfill({ status: 503, json: { detail: 'Account access is temporarily unavailable. Contact support.' } });
                    result = { message: 'Password updated successfully.' };
                } else if (path === '/api/admin/attention') {
                    assert.equal(request.headers().authorization, 'Bearer admin-browser-test-token');
                    result = { total: 1, items: [{
                        user_id: 3, email: 'setup@example.com', status: 'error',
                        shield_number: '+12025550100', activation_stage: 'creating your screening assistant',
                        uncertain_operation: recovered ? null : 'screening_agent',
                        can_review_recovery: !recovered,
                        error_message: unsafeName, billing: { status: 'past_due' },
                        checkpoints: { order_attempted: true, llm_id: 'llm-saved', agent_id: null },
                    }] };
                } else if (path === '/api/admin/customers/3/reopen-activation') {
                    recoveryAttempts += 1;
                    assert.equal(request.method(), 'POST');
                    assert.equal(request.postDataJSON().provider_reconciled, true);
                    assert.match(request.postDataJSON().note, /Verified/);
                    if (recoveryAttempts === 1) return route.fulfill({
                        status: 409, json: { detail: 'Activation is still running. No recovery changes were made.' },
                    });
                    recovered = true;
                    result = { success: true, message: 'Activation reopened. The customer can resume saved setup. No provider changes or purchases were made.' };
                } else if (path === '/api/auth/forgot-password') {
                    assert.equal(request.postDataJSON().email, 'admin@example.com');
                    if (emailUnavailable) return route.fulfill({ status: 503, json: { detail: 'Password recovery is temporarily unavailable. Please contact support.' } });
                    return route.fulfill({ status: 202, json: {
                        message: 'Your request was received. If an account exists for that email, check your inbox for a password reset link.',
                    } });
                } else {
                    throw new Error(`Unexpected account API: ${path}`);
                }
                return route.fulfill({ json: result });
            });

            await page.goto(`${baseURL}/static/admin-panel.html`);
            await page.locator('#dashboard').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#total-users').textContent(), '3');
            assert.equal(await page.locator('#users-table img').count(), 0);
            await page.locator('#users-table').getByText(unsafeName, { exact: true }).waitFor();
            assert.equal(await page.locator('#readiness-list li').count(), 2);
            assert.equal(await page.locator('#readiness-list li[data-ok="false"] code').allTextContents().then((names) => names.join(',')),
                'TELNYX_API_KEY');
            assert.match(await page.locator('#readiness-summary').textContent(), /1 of 2 areas need attention/);
            await page.locator('#attention-list').getByText('setup@example.com - +12025550100', { exact: true }).waitFor();
            assert.equal(await page.locator('#attention-list img').count(), 0);
            await page.locator('#attention-list').getByRole('button', { name: 'Review activation', exact: true }).click();
            await page.locator('#recovery-note').fill('Verified providers and checkpoints. No untracked resource remains.');
            await page.locator('#reopen-activation').click();
            assert.equal(recoveryAttempts, 0);
            await page.locator('#provider-reconciled').check();
            await page.locator('#reopen-activation').click();
            await page.locator('#recovery-message').filter({ hasText: 'Activation is still running' }).waitFor();
            assert.equal(await page.locator('#reopen-activation').isDisabled(), false);
            await page.locator('#reopen-activation').click();
            await page.locator('#recovery-message').filter({ hasText: 'Activation reopened' }).waitFor();
            assert.equal(recoveryAttempts, 2);
            await page.waitForFunction(() => !attentionLoading);
            assert.equal(await page.locator('#attention-list button').count(), 0);
            await page.locator('#cancel-recovery').click();
            assert.equal(await page.evaluate(() => window.unsafeExecuted), undefined);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false,
                JSON.stringify(await page.locator('body *').evaluateAll(nodes => nodes.filter(node => {
                    const box = node.getBoundingClientRect();
                    return box.width && (node.scrollWidth > node.clientWidth || box.right > innerWidth || box.left < 0);
                }).slice(0, 8).map(node => ({ tag: node.tagName, id: node.id, width: node.getBoundingClientRect().width, scroll: node.scrollWidth, client: node.clientWidth })))));
            unavailable = true;
            await page.locator('#refresh').click();
            await page.locator('#error').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#dashboard').isVisible(), false);
            assert.equal(await page.locator('#users-table tr').count(), 0);
            unavailable = false;
            await page.locator('#retry').click();
            await page.locator('#dashboard').waitFor({ state: 'visible' });
            denyAdminAPI = true;
            await page.locator('#refresh').click();
            await page.getByText('This account does not have administrator access.', { exact: true }).waitFor();
            assert.equal(await page.locator('#dashboard').isVisible(), false);
            denyAdminAPI = false;
            adminAccess = false;
            const requestsBefore = dashboardRequests;
            await page.locator('#retry').click();
            await page.waitForFunction(() => !loading);
            assert.equal(dashboardRequests, requestsBefore);
            adminAccess = true;
            await page.locator('#retry').click();
            await page.locator('#dashboard').waitFor({ state: 'visible' });
            await page.evaluate(() => localStorage.setItem('token', 'legacy-browser-test-token'));
            await page.locator('#sign-out').click();
            await page.waitForURL('**/static/login.html');
            for (const key of ['access_token', 'token', 'user', 'selected_plan']) {
                assert.equal(await page.evaluate(key => localStorage.getItem(key), key), null);
            }
            await page.goto(`${baseURL}/static/admin-panel.html`);
            await page.waitForURL('**/static/login.html');
            await page.evaluate(() => localStorage.setItem('access_token', 'admin-browser-test-token'));
            expired = true;
            await page.goto(`${baseURL}/static/admin-panel.html`);
            await page.waitForURL('**/static/login.html');
            assert.equal(await page.evaluate(() => localStorage.getItem('access_token')), null);

            await page.goto(`${baseURL}/static/reset-password.html?token=browser-reset-token`);
            assert.equal(new URL(page.url()).searchParams.has('token'), false);
            await page.goto(`${baseURL}/static/forgot-password.html`);
            await page.goto(`${baseURL}/static/reset-password.html#token=browser-reset-token`);
            assert.equal(new URL(page.url()).hash, '');
            assert.equal(resetDocumentURLs.at(-1).includes('token='), false);
            assert.equal(await page.locator('meta[name="referrer"]').getAttribute('content'), 'no-referrer');
            await page.locator('#password').fill('x'.repeat(73));
            await page.locator('#confirm').fill('x'.repeat(73));
            await page.locator('#submit-btn').click();
            await page.locator('#message').filter({ hasText: '72 UTF-8 bytes' }).waitFor();
            assert.equal(resetRequests, 0);
            await page.locator('#password').fill('\u00e9'.repeat(37));
            await page.locator('#confirm').fill('\u00e9'.repeat(37));
            await page.locator('#submit-btn').click();
            assert.equal(resetRequests, 0);
            await page.locator('#password').fill('new-password-123');
            await page.locator('#confirm').fill('new-password-123');
            await page.locator('#submit-btn').click();
            await page.locator('#message').filter({ hasText: 'temporarily unavailable' }).waitFor();
            assert.equal(await page.locator('#submit-btn').isDisabled(), false);
            resetUnavailable = false;
            await page.locator('#submit-btn').click();
            await page.locator('#done-state').waitFor({ state: 'visible' });
            assert.equal(resetRequests, 2);
            await page.reload();
            await page.locator('#invalid-state').waitFor({ state: 'visible' });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);

            await page.goto(`${baseURL}/static/forgot-password.html`);
            await page.locator('#email').fill('admin@example.com');
            await page.locator('#submit-btn').click();
            await page.locator('#message').filter({ hasText: 'temporarily unavailable' }).waitFor();
            assert.equal(await page.locator('#submit-btn').isDisabled(), false);
            assert.equal(await page.locator('#sent-state').isVisible(), false);
            emailUnavailable = false;
            await page.locator('#submit-btn').click();
            await page.locator('#sent-state').waitFor({ state: 'visible' });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: signed admin access/denial/retry/sign-out, safe names, reset URL cleanup/password limits/error retry, recovery errors`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
