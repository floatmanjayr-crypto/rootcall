const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');

const baseURL = process.env.ROOTCALL_PREVIEW_URL || 'http://127.0.0.1:8765';
const shots = process.env.ROOTCALL_SHOTS || '';

async function newPage(browser, width, world) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
    await page.route('https://fonts.gstatic.com/**', r => r.abort());
    await page.addInitScript(() => localStorage.setItem('access_token', 'tok'));
    await page.route('**/api/**', async route => {
        const request = route.request();
        const path = new URL(request.url()).pathname;
        const method = request.method();
        const body = request.postData() ? JSON.parse(request.postData()) : {};
        world.calls.push(`${method} ${path}`);
        const json = (data, status = 200) => route.fulfill({ status, json: data });
        if (path === '/api/auth/me') return json({ id: 7, email: 'o@example.com', full_name: world.fullName });
        if (path === '/api/payments/status') return json(world.paid ? { billing_available: true } : { billing_available: false });
        if (path === '/api/rootcall/my-number') return json(world.number ? { has_number: true, number: world.number } : { has_number: false });
        if (path === '/api/rootcall/available-numbers') return json({ numbers: [
            { phone_number: '+14075550101', locality: 'Orlando', region: 'FL' },
            { phone_number: '+14075550102', locality: 'Orlando', region: 'FL' }] });
        if (path === '/api/rootcall/provision') {
            world.provisionBodies.push(body);
            if (world.failProvision) { world.failProvision = false; return json({ detail: 'Retell was unavailable' }, 502); }
            world.number = body.phone_number;
            return json({ rootcall_number: body.phone_number });
        }
        if (path === '/api/rootcall/config/7' && method === 'GET') return json(world.number ? { client_cell: world.cell, trusted_contacts: world.contacts.map(c => c.phone_number), voice_id: world.voice } : {}, world.number ? 200 : 404);
        if (path === '/api/rootcall/config/7' && method === 'PATCH') {
            world.patches.push(body);
            if (body.full_name) world.fullName = body.full_name;
            if (body.client_cell) world.cell = body.client_cell;
            if (body.voice_id) world.voice = body.voice_id;
            return json({ ok: true });
        }
        if (path === '/api/rootcall/sync-agent-identity/7') return json({ ok: true });
        if (path === '/api/rootcall/voice-options') return json({ voices: [
            { voice_id: 'v-adrian', voice_name: 'Adrian', gender: 'male', accent: 'American', preview_audio_url: 'https://example.com/a.mp3' },
            { voice_id: 'v-grace', voice_name: 'Grace', gender: 'female', accent: '', preview_audio_url: null }] });
        if (path === '/api/rootcall/trusted-contacts/7' && method === 'POST') { world.contacts.push(body); return json({ ok: true }); }
        return json({ detail: 'unexpected ' + path }, 500);
    });
    return { page, errors, context };
}

const fresh = () => ({ paid: true, number: '', cell: '', voice: '', fullName: 'Jordan Green', contacts: [], patches: [], provisionBodies: [], calls: [], failProvision: false });

(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        for (const width of [1440, 390]) {
            // ---- Happy path, with a failed activation first ----
            const world = fresh();
            world.failProvision = true;
            let { page, errors, context } = await newPage(browser, width, world);
            await page.goto(`${baseURL}/static/setup.html`);
            await page.getByRole('heading', { name: 'Pick your Shield number' }).waitFor();
            assert.equal(await page.locator('#steps li[aria-current="step"]').innerText(), 'Your number');
            assert.match(await page.locator('#guide').innerText(), /Choosing your Shield number/);

            await page.locator('#area').fill('4');
            await page.getByRole('button', { name: 'Find numbers' }).click();
            await page.getByText('Enter a 3-digit area code').waitFor();
            await page.locator('#area').fill('407');
            await page.getByRole('button', { name: 'Find numbers' }).click();
            await page.locator('.pick').first().waitFor();
            assert.equal(await page.locator('.pick').count(), 2);
            assert.equal(await page.getByRole('button', { name: 'Activate this number' }).isDisabled(), true);
            await page.locator('.pick', { hasText: '(407) 555-0102' }).click();
            await page.getByRole('button', { name: 'Activate this number' }).click();
            await page.getByText(/Retell was unavailable/).waitFor();
            const finishButton = page.getByRole('button', { name: /Finish activating \+1 \(407\) 555-0102/ });
            await finishButton.waitFor();
            await finishButton.click();
            await page.getByRole('heading', { name: /What name should callers ask for/ }).waitFor();
            assert.equal(world.provisionBodies.at(-1).recover_existing, true, 'retry finishes the same purchase');
            assert.equal(world.provisionBodies.at(-1).phone_number, '+14075550102');
            if (shots && width === 1440) await page.screenshot({ path: `${shots}/setup-name.png`, fullPage: true });

            // name
            await page.locator('#full-name').fill('Jordan');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByText('Please enter your first and last name.').waitFor();
            await page.locator('#full-name').fill('  Jordan   Q Green ');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByRole('heading', { name: /Choose your assistant/ }).waitFor();
            assert.deepEqual(world.patches.at(-1), { full_name: 'Jordan Q Green' });
            assert.ok(world.calls.includes('POST /api/rootcall/sync-agent-identity/7'));

            // voice
            await page.locator('#voice option').first().waitFor({ state: 'attached' });
            assert.equal(await page.getByRole('button', { name: 'Play sample' }).isVisible(), true);
            await page.locator('#voice').selectOption('v-grace');
            assert.equal(await page.getByRole('button', { name: 'Play sample' }).isVisible(), false, 'no sample without a preview');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByRole('heading', { name: /Which phone should ring/ }).waitFor();
            assert.deepEqual(world.patches.at(-1), { voice_id: 'v-grace' });

            // reload mid-setup resumes at the same step
            await page.reload();
            await page.getByRole('heading', { name: /Which phone should ring/ }).waitFor();

            // phone
            await page.locator('#cell').fill('555');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByText('Enter a full phone number, like (407) 555-0100.').waitFor();
            await page.locator('#cell').fill('(407) 555-0102');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByText('That is your Shield number').waitFor();
            await page.locator('#cell').fill('(407) 555-0199');
            await page.getByRole('button', { name: 'Save and continue' }).click();
            await page.getByRole('heading', { name: /Add people who skip screening/ }).waitFor();
            assert.deepEqual(world.patches.at(-1), { client_cell: '+14075550199' });

            // contacts (optional)
            assert.match(await page.locator('.actions .btn').innerText(), /Skip and finish/);
            await page.locator('#contact-name').fill('Mom');
            await page.locator('#contact-phone').fill('(407) 555-0123');
            await page.getByRole('button', { name: 'Add contact' }).click();
            await page.getByText('Contact added.').waitFor();
            assert.deepEqual(world.contacts.at(-1), { phone_number: '+14075550123', name: 'Mom' });
            assert.match(await page.locator('.actions .btn').innerText(), /Finish setup/);
            await page.getByRole('button', { name: 'Finish setup' }).click();

            // done
            await page.getByRole('heading', { name: 'Your line is ready' }).waitFor();
            assert.equal(await page.locator('.big-number').innerText(), '+1 (407) 555-0102');
            const summary = await page.locator('dl.summary').innerText();
            assert.match(summary, /Jordan Q Green/);
            assert.match(summary, /\(407\) 555-0199/);
            await page.getByText('Grace').first().waitFor();
            assert.equal(await page.locator('a.btn', { hasText: 'Open my dashboard' }).getAttribute('href'), '/static/client-portal.html');
            assert.equal(await page.locator('#steps').isHidden(), true);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal overflow');
            if (shots) await page.screenshot({ path: `${shots}/setup-done-${width}.png`, fullPage: true });
            assert.deepEqual(errors, []);
            await context.close();

            // ---- Unpaid and nothing purchased ----
            const unpaid = fresh();
            unpaid.paid = false;
            ({ page, errors, context } = await newPage(browser, width, unpaid));
            await page.goto(`${baseURL}/static/setup.html`);
            await page.getByRole('heading', { name: /not confirmed your payment/ }).waitFor();
            assert.equal(unpaid.provisionBodies.length, 0);
            await context.close();

            // ---- Names are never rendered as HTML ----
            const odd = fresh();
            odd.number = '+14075550102';
            odd.fullName = '<img src=x onerror=window.__pwn=1> Smith';
            ({ page, errors, context } = await newPage(browser, width, odd));
            await page.addInitScript(() => localStorage.setItem('rootcall_setup_step_7', '1'));
            await page.goto(`${baseURL}/static/setup.html`);
            await page.getByRole('heading', { name: /What name should callers ask for/ }).waitFor();
            assert.equal(await page.locator('#panel img').count(), 0);
            assert.equal(await page.evaluate(() => window.__pwn), undefined);
            await context.close();
            console.log(`PASS ${width}px: setup wizard, retry after failed activation, resume, validation, unpaid guard`);
        }
    } finally {
        await browser.close();
    }
})().catch(e => { console.error(e); process.exit(1); });
