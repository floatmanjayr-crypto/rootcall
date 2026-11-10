const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({ viewport: { width, height: 1000 } });
            const errors = [];
            page.on('pageerror', (error) => errors.push(error.message));
            await page.addInitScript(() => {
                if (!sessionStorage.getItem('test-initialized')) {
                    localStorage.setItem('access_token', 'browser-test-token');
                    sessionStorage.setItem('test-initialized', 'true');
                }
            });
            let state = {
                legacy: false, status: 'draft', payment_status: 'pending', tier: 'essential',
                email: 'owner@example.com', first_name: '', last_name: '', forwarding_number: '',
                voice_id: '', shield_number: '', number_locked: false, error_message: null,
                trusted_contacts: [], contacts_completed: false,
            };
            let searchMode = 'empty';
            let paymentVerified = false;
            let verificationAttempts = 0;
            let activationAttempts = 0;
            let checkoutAttempts = 0;
            let guideUnavailable = false;
            let guideChecks = { mode: 'direct', screening_tested: false, trusted_tested: false,
                audio_tested: false, carrier_forwarding_confirmed: false };
            await page.route('**/api/**', async (route) => {
                const request = route.request();
                const path = new URL(request.url()).pathname;
                assert.equal(request.headers().authorization, 'Bearer browser-test-token');
                let result = {};
                let status = 200;
                if (path === '/api/onboarding/status') result = state;
                else if (path === '/api/onboarding/voices') result = {
                    voices: [{ voice_id: 'voice-test', name: 'Avery', accent: 'American', gender: 'female', preview_url: null }],
                };
                else if (path === '/api/payments/create-checkout') {
                    checkoutAttempts += 1;
                    assert.equal(request.postDataJSON().tier, 'essential');
                    status = 502;
                    result = { detail: 'Checkout is unavailable. Please retry.' };
                } else if (path === '/api/payments/verify') {
                    verificationAttempts += 1;
                    assert.equal(request.postDataJSON().session_id, 'cs-test');
                    status = paymentVerified ? 200 : 402;
                    result = paymentVerified ? { paid: true } : { detail: 'Payment is not confirmed yet.' };
                    if (paymentVerified) state.payment_status = 'active';
                } else if (path === '/api/payments/billing-portal') {
                    status = 502;
                    result = { detail: 'Billing management is unavailable. Please retry.' };
                } else if (path === '/api/onboarding/profile') {
                    const profile = request.postDataJSON();
                    assert.equal(profile.first_name, 'Jordan');
                    assert.equal(profile.last_name, 'Green');
                    assert.equal(profile.voice_id, 'voice-test');
                    state = { ...state, ...profile, forwarding_number: '+12025550123' };
                } else if (path === '/api/onboarding/numbers') {
                    if (searchMode === 'error') {
                        status = 502;
                        result = { detail: 'Number search is unavailable.' };
                    } else result = { numbers: searchMode === 'empty' ? [] : [
                        { phone_number: '+12025550100', locality: 'Washington' },
                    ] };
                } else if (path === '/api/onboarding/number') {
                    assert.equal(request.postDataJSON().phone_number, '+12025550100');
                    state.shield_number = '+12025550100';
                } else if (path === '/api/onboarding/trusted-contacts') {
                    state.trusted_contacts = request.postDataJSON().phone_numbers;
                    state.contacts_completed = true;
                } else if (path === '/api/onboarding/complete') {
                    activationAttempts += 1;
                    state.error_message = null;
                    state.activation_job = { status: 'queued', attempts: 0, next_attempt_at: new Date().toISOString() };
                    status = 202;
                    result = { accepted: true, job: state.activation_job };
                } else if (path === '/api/onboarding/service-setup') {
                    if (guideUnavailable) {
                        status = 502;
                        result = { detail: 'Call checks could not be loaded.' };
                    } else {
                        if (request.method() === 'PUT') {
                            const body = request.postDataJSON();
                            assert.equal(body.shield_number, '+12025550100');
                            assert.equal(body.forwarding_number, '+12025550123');
                            guideChecks = { ...guideChecks, ...body };
                        }
                        result = { shield_number: '+12025550100', forwarding_number: '+12025550123',
                            has_trusted_contacts: true, checks: guideChecks, self_reported: true };
                    }
                } else throw new Error(`Unexpected API request: ${path}`);
                await route.fulfill({ status, json: result });
            });
            await page.goto(`${baseURL}/static/onboarding.html?payment=cancelled`);
            await page.locator('#payment').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#profile').isVisible(), false);
            await page.locator('#pay').click();
            await page.getByText('Checkout is unavailable. Please retry.', { exact: true }).waitFor();
            assert.equal(checkoutAttempts, 1);
            state.billing_available = true;
            await page.locator('#check-payment').click();
            await page.locator('#manage-billing').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#pay').isVisible(), false);
            await page.locator('#manage-billing').click();
            await page.getByText('Billing management is unavailable. Please retry.', { exact: true }).waitFor();
            await page.goto(`${baseURL}/static/onboarding.html?session_id=cs-test`);
            await page.getByText('Payment is not confirmed yet.', { exact: true }).waitFor();
            assert.equal(await page.locator('#profile').isVisible(), false);
            assert.equal(await page.locator('#payment').isVisible(), false);
            assert.match(page.url(), /session_id=cs-test/);
            paymentVerified = true;
            await page.locator('#retry-payment').click();
            await page.locator('#profile').waitFor({ state: 'visible' });
            assert.equal(new URL(page.url()).searchParams.has('session_id'), false);
            assert.equal(verificationAttempts, 2);
            await page.locator('#voice option[value="voice-test"]').waitFor({ state: 'attached' });
            await page.locator('#first-name').fill('Jordan');
            await page.locator('#last-name').fill('Green');
            await page.locator('#forwarding-number').fill('(202) 555-0123');
            await page.locator('#voice').selectOption('voice-test');
            assert.equal(await page.locator('#email').inputValue(), 'owner@example.com');
            assert.equal(await page.locator('#email').getAttribute('readonly'), '');
            await page.locator('#profile-form button[type="submit"]').click();
            await page.locator('#number').waitFor({ state: 'visible' });
            await page.locator('#area-code').fill('202');
            await page.locator('#number-search button').click();
            await page.getByText('No numbers available. Try a nearby area code.', { exact: true }).waitFor();
            assert.equal(await page.locator('#save-number').isDisabled(), true);
            searchMode = 'error';
            await page.locator('#number-search button').click();
            await page.getByText('Number search is unavailable.', { exact: true }).waitFor();
            searchMode = 'available';
            await page.locator('#number-search button').click();
            await page.locator('input[name="shield-number"]').check();
            await page.locator('#save-number').click();
            await page.locator('#contacts').waitFor({ state: 'visible' });
            await page.reload();
            await page.locator('#contacts').waitFor({ state: 'visible' });
            await page.locator('#back-number').click();
            await page.locator('#keep-number').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#keep-number').textContent(), 'Keep +12025550100');
            await page.locator('#keep-number').click();
            await page.locator('#contacts').waitFor({ state: 'visible' });
            if (width === 1440) {
                await page.locator('#contact-number').fill('(202) 555-0145');
                await page.locator('#contact-form button').click();
                await page.locator('#contact-number').fill('+12025550145');
                await page.locator('#contact-form button').click();
                await page.getByText('This contact is already in your list.', { exact: true }).waitFor();
                await page.locator('#contact-number').fill('+12025550146');
                await page.locator('#contact-form button').click();
                await page.getByRole('button', { name: 'Remove +12025550146', exact: true }).click();
                await page.screenshot({ path: `/tmp/rootcall-contacts-${width}.png`, fullPage: true });
                await page.locator('#save-contacts').click();
            } else {
                await page.screenshot({ path: `/tmp/rootcall-contacts-${width}.png`, fullPage: true });
                await page.locator('#skip-contacts').click();
            }
            await page.locator('#review').waitFor({ state: 'visible' });
            assert.match(await page.locator('#review-details').innerText(), /Avery/);
            assert.deepEqual(state.trusted_contacts, width === 1440 ? ['+12025550145'] : []);
            await page.reload();
            await page.getByText('Avery', { exact: true }).waitFor();
            assert.equal(await page.locator('#review').isVisible(), true);
            await page.locator('#edit-contacts').click();
            await page.locator('#contacts').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#setup-contacts li').count(), state.trusted_contacts.length);
            await page.locator('#save-contacts').click();
            await page.locator('#review').waitFor({ state: 'visible' });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            state.support_review_required = true;
            state.activation_stage = 'creating your screening assistant';
            await page.reload();
            await page.locator('#activation-status').filter({ hasText: 'provider review by support' }).waitFor();
            assert.equal(await page.locator('#activate').isVisible(), false);
            state.support_review_required = false;
            state.status = 'provisioning';
            await page.locator('#refresh-setup').click();
            await page.locator('#activation-status').filter({ hasText: 'Setup is running: creating your screening assistant' }).waitFor();
            assert.equal(await page.locator('#activate').isVisible(), false);
            state.status = 'error';
            await page.locator('#refresh-setup').click();
            await page.locator('#activate').waitFor({ state: 'visible' });
            await page.screenshot({ path: `/tmp/rootcall-onboarding-${width}.png`, fullPage: true });
            await page.locator('#activate').click();
            await page.locator('#activation-status').filter({ hasText: 'Your activation is queued' }).waitFor();
            assert.equal(activationAttempts, 1);
            assert.equal(await page.locator('#activate').isVisible(), false);
            await page.reload();
            await page.locator('#activation-status').filter({ hasText: 'Your activation is queued' }).waitFor();
            assert.equal(await page.locator('#edit-details').isVisible(), false);
            assert.equal(await page.locator('#edit-contacts').isVisible(), false);
            state.number_locked = true;
            state.status = 'error';
            state.activation_job = { status: 'retry', attempts: 1, next_attempt_at: new Date().toISOString() };
            await page.locator('#activation-status').filter({ hasText: 'Automatic retry' }).waitFor();
            state.status = 'completed';
            state.activation_job.status = 'completed';
            await page.locator('#done').waitFor({ state: 'visible' });
            assert.equal(activationAttempts, 1);
            assert.equal(await page.locator('#active-number').textContent(), '+12025550100');
            await page.locator('#service-setup-form').waitFor({ state: 'visible' });
            await page.locator('#setup-mode').selectOption('carrier');
            await page.locator('#carrier-guide').waitFor({ state: 'visible' });
            assert.match(await page.locator('#carrier-guide').textContent(), /Avoid a forwarding loop/);
            await page.locator('#screening-tested').check();
            await page.locator('#audio-tested').check();
            await page.locator('#service-setup-form button[type="submit"]').click();
            await page.locator('#service-setup-status').filter({ hasText: 'Your call checks are saved' }).waitFor();
            await page.reload();
            await page.locator('#service-setup-form').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#audio-tested').isChecked(), true);
            assert.equal(await page.locator('#setup-mode').inputValue(), 'carrier');
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            guideUnavailable = true;
            await page.reload();
            await page.locator('#service-setup-error').filter({ hasText: 'Call checks could not be loaded' }).waitFor();
            guideUnavailable = false;
            await page.locator('#reload-service-setup').click();
            await page.locator('#service-setup-form').waitFor({ state: 'visible' });
            paymentVerified = false;
            await page.goto(`${baseURL}/static/success.html?session_id=cs-test`);
            await page.getByText('Payment is not confirmed yet.', { exact: true }).waitFor();
            assert.equal(new URL(page.url()).pathname, '/static/onboarding.html');
            assert.equal(await page.locator('#done').isVisible(), false);
            paymentVerified = true;
            await page.locator('#retry-payment').click();
            await page.locator('#done').waitFor({ state: 'visible' });
            assert.equal(new URL(page.url()).searchParams.has('session_id'), false);
            const verifiedAttempts = verificationAttempts;
            await page.reload();
            await page.locator('#done').waitFor({ state: 'visible' });
            assert.equal(verificationAttempts, verifiedAttempts);
            await page.locator('#sign-out').click();
            await page.waitForURL('**/static/login.html');
            assert.equal(await page.evaluate(() => localStorage.getItem('access_token')), null);
            await page.evaluate(() => localStorage.setItem('access_token', 'browser-test-token'));
            await page.goto(`${baseURL}/static/onboarding.html`);
            await page.locator('#done').waitFor({ state: 'visible' });
            await page.locator('#sign-out').click();
            await page.waitForURL('**/static/login.html');
            assert.equal(await page.evaluate(() => localStorage.getItem('access_token')), null);
            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: payment gate, profile/voice, contacts, durable activation/reload/automatic retry/progress, saved call checks, carrier-loop guidance, guide retry, sign out, no overflow`);
            await page.close();
        }
        const page = await browser.newPage();
        const requests = [];
        await page.route('**/api/**', async (route) => {
            const request = route.request();
            const path = new URL(request.url()).pathname;
            requests.push(path);
            let result;
            if (path === '/api/auth/signup') {
                assert.deepEqual(request.postDataJSON(), { email: 'new@example.com', password: 'test-password' });
                result = { access_token: 'signup-token', user: { id: 1, email: 'new@example.com' } };
            } else if (path === '/api/payments/create-checkout') {
                assert.equal(request.headers().authorization, 'Bearer signup-token');
                assert.deepEqual(request.postDataJSON(), { tier: 'essential' });
                result = { checkout_url: `${baseURL}/static/onboarding.html?payment=cancelled` };
            } else if (path === '/api/auth/login') {
                const form = new URLSearchParams(request.postData());
                assert.equal(form.get('username'), 'new@example.com');
                assert.equal(form.get('password'), ' test-password ');
                result = { access_token: 'signup-token', next_url: '/static/onboarding.html' };
            } else if (path === '/api/auth/me') {
                result = { id: 1, email: 'new@example.com', next_url: '/static/onboarding.html' };
            } else if (path === '/api/onboarding/status') {
                result = { legacy: false, status: 'draft', payment_status: 'pending', email: 'new@example.com' };
            } else if (path === '/api/rootcall/live-calls') {
                result = [];
            } else throw new Error(`Unexpected API request: ${path}`);
            await route.fulfill({ json: result });
        });
        await page.goto(`${baseURL}/static/index.html`);
        assert.equal(await page.locator('#signup-plan option').count(), 2);
        assert.equal(await page.locator('[aria-label="Family plan"] button').isDisabled(), true);
        assert.equal(await page.locator('[aria-label="Guardian plan"] button').isDisabled(), true);
        await page.evaluate(() => window.selectPlan('essential'));
        await page.locator('#signup-email').fill('new@example.com');
        await page.locator('#signup-password').fill('test-password');
        await page.locator('#signup-modal button[type="submit"]').click();
        await page.locator('#payment').waitFor({ state: 'visible' });
        assert.deepEqual(requests.slice(0, 3), [
            '/api/auth/signup', '/api/payments/create-checkout', '/api/onboarding/status',
        ]);
        await page.evaluate(() => localStorage.clear());
        await page.goto(`${baseURL}/static/login.html`);
        await page.locator('#email').fill('new@example.com');
        await page.locator('#password').fill(' test-password ');
        await page.locator('#login-btn').click();
        await page.locator('#payment').waitFor({ state: 'visible' });
        await page.goto(`${baseURL}/static/client-portal.html`);
        await page.waitForURL('**/static/onboarding.html');
        await page.locator('#payment').waitFor({ state: 'visible' });
        await page.evaluate(() => localStorage.clear());
        await page.goto(`${baseURL}/static/onboarding.html`);
        await page.waitForURL('**/static/login.html');
        await page.goto(`${baseURL}/static/success.html?session_id=cs-test`);
        await page.waitForURL('**/static/login.html');
        assert.equal(requests.filter((path) => path === '/api/payments/verify').length, 0);
        await page.goto(`${baseURL}/static/success.html`);
        await page.waitForURL('**/static/login.html');
        await page.goto(`${baseURL}/static/shield-pricing.html?success=true`);
        await page.waitForURL('**/static/index.html#pricing');
        console.log('PASS account flow: signup before authenticated checkout, login/resume, dashboard setup gate, anonymous setup/success gates');
        await page.close();
    } finally {
        await browser.close();
    }
})().catch((error) => { console.error(error); process.exitCode = 1; });
