const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';
const staticDir = path.join(__dirname, '..', 'static');
const pages = ['index', 'login', 'forgot-password', 'reset-password', 'onboarding', 'client-portal', 'admin-panel', 'privacy', 'terms', '404'];

(async () => {
    for (const name of ['shield-dashboard', 'rootcall-portal', 'james-portal', 'test']) {
        assert.equal(fs.existsSync(path.join(staticDir, `${name}.html`)), false, `${name}.html was removed`);
    }
    assert.deepEqual(fs.readdirSync(staticDir).filter((file) => /\.(backup\d*|old|before-fix)$/.test(file)), []);
    assert.equal(fs.existsSync(path.join(staticDir, 'favicon.svg')), true);

    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({ viewport: { width, height: 900 } });
            const errors = [];
            page.on('pageerror', (error) => errors.push(error.message));
            await page.route('https://fonts.googleapis.com/**', (route) => route.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('https://fonts.gstatic.com/**', (route) => route.abort());
            await page.route('https://cdnjs.cloudflare.com/**', (route) => route.fulfill({ contentType: 'text/css', body: '' }));
            await page.route('**/api/**', (route) => route.fulfill({ status: 401, json: { detail: 'Unauthenticated' } }));

            for (const name of pages) {
                const html = fs.readFileSync(path.join(staticDir, `${name}.html`), 'utf8');
                assert.match(html, /<link rel="icon" href="\/static\/favicon\.svg"/, `${name} favicon`);
                assert.match(html, /<meta name="theme-color" content="#0d3d2f"/, `${name} theme color`);
                assert.match(html, /<link rel="stylesheet" href="\/static\/rootcall\.css"/, `${name} shared stylesheet`);
            }

            for (const name of ['index', 'privacy', 'terms', '404', 'login']) {
                await page.goto(`${baseURL}/static/${name}.html`);
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${name} has no horizontal overflow at ${width}px`);
            }

            await page.goto(`${baseURL}/static/login.html`);
            const loginText = await page.locator('body').innerText();
            assert.equal(/99\.8%|<1s/.test(loginText), false, 'login has no unverified performance claims');

            for (const name of ['privacy', 'terms']) {
                await page.goto(`${baseURL}/static/${name}.html`);
                assert.equal(await page.locator('main.rc-doc h1').count(), 1);
                assert.equal(await page.locator('header nav a[aria-current="page"]').count(), 1);
            }
            await page.goto(`${baseURL}/static/404.html`);
            assert.equal(await page.getByRole('link', { name: 'Back to home' }).getAttribute('href'), '/static/index.html');

            await page.goto(`${baseURL}/static/index.html`);
            assert.equal(await page.locator('.flow li').count(), 3);
            assert.equal(await page.locator('footer a[href="/static/privacy.html"]').count(), 1);
            assert.equal(await page.locator('footer a[href="/static/terms.html"]').count(), 1);
            const ctaVisible = await page.locator('.mobile-cta').isVisible();
            assert.equal(ctaVisible, width <= 640, 'sticky call-to-action only on mobile');
            if (ctaVisible) {
                await page.locator('.mobile-cta a').click();
                await page.locator('#signup-modal.active').waitFor();
            }

            await page.goto(`${baseURL}/static/privacy.html`);
            await page.keyboard.press('Tab');
            const ring = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
            assert.notEqual(ring, 'none', 'keyboard focus is visible');

            await page.emulateMedia({ reducedMotion: 'reduce' });
            await page.goto(`${baseURL}/static/index.html`);
            const duration = await page.locator('.btn').first().evaluate((node) => parseFloat(getComputedStyle(node).transitionDuration));
            assert.ok(duration < 0.01, 'reduced motion removes transitions');

            assert.deepEqual(errors, []);
            console.log(`PASS ${width}px: shared head/meta, legal and 404 pages, landing flow and mobile CTA, no unverified claims, focus ring, reduced motion`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
})().catch((error) => {
    console.error(error);
    process.exit(1);
});
