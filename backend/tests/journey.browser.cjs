const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

// Drives the real app started by e2e_journey_server.py (no mocked API routes).
const base = process.env.ROOTCALL_E2E_URL || 'http://127.0.0.1:8770';

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const [index, width] of [1280, 390].entries()) {
            const page = await browser.newPage({ viewport: { width, height: 900 } });
            const errors = [];
            page.on('pageerror', (error) => errors.push(error.message));
            await page.route('https://fonts.googleapis.com/**', (route) => route.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('https://cdnjs.cloudflare.com/**', (route) => route.fulfill({ contentType: 'text/css', body: '' }));

            // The hero button opens the signup form without choosing a plan; it must still submit.
            await page.goto(`${base}/static/index.html`);
            await page.locator('.hero a.btn-primary').click();
            await page.locator('#signup-email').fill(`customer${index}@example.com`);
            await page.locator('#signup-password').fill('a-strong-password-123');
            await Promise.all([
                page.waitForURL('**/__fake_stripe?session_id=*', { timeout: 15000 }),
                page.locator('#signup-modal button[type="submit"]').click(),
            ]);
            const sessionId = new URL(page.url()).searchParams.get('session_id');

            await page.goto(`${base}/static/onboarding.html?session_id=${sessionId}`);
            await page.locator('#profile').waitFor({ state: 'visible', timeout: 15000 });
            assert.equal(new URL(page.url()).searchParams.has('session_id'), false);
            await page.locator('#first-name').fill('Jordan');
            await page.locator('#last-name').fill('Green');
            await page.locator('#forwarding-number').fill('(202) 555-0123');
            await page.locator('#voice option[value="v1"]').waitFor({ state: 'attached', timeout: 15000 });
            await page.locator('#voice').selectOption('v1');
            await page.locator('#profile-form button[type="submit"]').click();

            await page.locator('#number').waitFor({ state: 'visible', timeout: 15000 });
            await page.locator('#area-code').fill('202');
            await page.locator('#number-search button').click();
            await page.locator('input[name="shield-number"]').check();
            await page.locator('#save-number').click();

            await page.locator('#contacts').waitFor({ state: 'visible', timeout: 15000 });
            await page.locator('#skip-contacts').click();
            await page.locator('#review').waitFor({ state: 'visible', timeout: 15000 });
            await page.reload();
            await page.locator('#review').waitFor({ state: 'visible', timeout: 15000 });

            await page.locator('#activate').click();
            await page.locator('#done').waitFor({ state: 'visible', timeout: 60000 });
            assert.equal(await page.locator('#page-title').textContent(), 'Your RootCall line is ready');
            assert.match(await page.locator('#done').innerText(), /\+1202555\d{4}/);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: register -> Stripe -> verified setup -> number -> automatic activation -> success`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch((error) => {
    console.error(error);
    process.exit(1);
});
