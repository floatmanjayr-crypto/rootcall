const byId = (id) => document.getElementById(id);
let saved = null;
let voiceChoices = [];
let busy = false;
let draftContacts = [];
let progressTimer;
let signedOut = false;
let serviceSetup = null;
const token = localStorage.getItem('access_token') || localStorage.getItem('token');
let checkoutSession = new URLSearchParams(location.search).get('session_id');

async function api(path, method = 'GET', body) {
    const response = await fetch(path, {
        method,
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
        ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    });
    if (response.status === 401) {
        signedOut = true;
        location.replace('/static/login.html');
        throw new Error('Please sign in again.');
    }
    let data;
    try { data = await response.json(); }
    catch { throw new Error('The server returned an invalid response. Please retry.'); }
    if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(' ') : data.detail;
        throw new Error(detail || `Request failed (${response.status}).`);
    }
    return data;
}

function message(text) {
    byId('message').textContent = text;
    byId('message').hidden = !text;
}

async function run(action) {
    if (busy) return;
    busy = true;
    message('');
    const buttons = [...document.querySelectorAll('button')];
    const states = buttons.map((button) => button.disabled);
    buttons.forEach((button) => { button.disabled = true; });
    try { await action(); }
    catch (error) {
        if (byId('load-error').hidden) message(error.message || 'Unable to connect. Please try again.');
    }
    finally {
        busy = false;
        buttons.forEach((button, index) => { button.disabled = states[index]; });
        byId('save-number').disabled = !document.querySelector('input[name="shield-number"]:checked');
    }
}

function show(step) {
    const copy = {
        confirmation: ['Confirming your payment', 'Secure check', 'We’re confirming your payment with Stripe. This usually takes a few seconds.'],
        'load-error': ['Let’s get your setup back', 'Setup paused', 'Your saved details have not changed.'],
        payment: ['Start with your subscription', 'Step 1 · Payment', 'RootCall Essential protects one line. Pay securely with Stripe, then personalize your setup.'],
        profile: ['Let’s set up your call shield', 'Step 2 · Your details', 'Tell us where approved calls should reach you and choose a voice for your AI assistant.'],
        number: ['Choose your Shield number', 'Step 3 · Shield number', 'Pick the number your callers will dial to reach your assistant.'],
        contacts: ['Choose who can reach you', 'Step 4 · Trusted contacts', 'Trusted callers skip screening and ring straight through. You can change this any time.'],
        review: ['Ready to connect your Shield?', 'Step 5 · Review & activate', 'Check your choices. Activation runs automatically and continues if you close this page.'],
        done: ['Your RootCall line is ready', 'Step 6 · Connect & test', 'Your number and assistant are connected. Finish the quick checks below before relying on the service.'],
    };
    const [title, eyebrow, intro] = copy[step] || copy.profile;
    byId('page-title').textContent = title;
    byId('page-eyebrow').textContent = eyebrow;
    byId('page-intro').textContent = intro;
    if (step === 'number') {
        byId('keep-number').hidden = !saved.shield_number;
        byId('keep-number').textContent = `Keep ${saved.shield_number}`;
    }
    const steps = ['payment', 'profile', 'number', 'contacts', 'review', 'done'];
    for (const id of ['confirmation', 'load-error', ...steps]) byId(id).hidden = id !== step;
    document.querySelectorAll('[data-step]').forEach((item) => {
        if (item.dataset.step === step) item.setAttribute('aria-current', 'step');
        else item.removeAttribute('aria-current');
        const index = steps.indexOf(item.dataset.step);
        item.dataset.complete = String(index !== -1 && index < steps.indexOf(step));
    });
    byId('page-title').focus();
}

function previewVoice() {
    const choice = voiceChoices.find((voice) => voice.voice_id === byId('voice').value);
    const preview = byId('voice-preview');
    preview.pause();
    preview.removeAttribute('src');
    preview.hidden = true;
    if (choice?.preview_url && /^https:\/\//.test(choice.preview_url)) {
        preview.src = choice.preview_url;
        preview.hidden = false;
    }
}

async function loadVoices() {
    const data = await api('/api/onboarding/voices');
    voiceChoices = data.voices;
    const select = byId('voice');
    select.replaceChildren(new Option('Choose an agent voice', ''));
    for (const voice of voiceChoices) {
        select.add(new Option([voice.name, voice.accent, voice.gender].filter(Boolean).join(' · '), voice.voice_id));
    }
    select.value = saved.voice_id || '';
    byId('voice-hint').textContent = voiceChoices.length ? 'Listen to a sample before choosing.' : 'No voices are available. Contact support before proceeding.';
    previewVoice();
}

function review() {
    const voice = voiceChoices.find((choice) => choice.voice_id === saved.voice_id);
    const fields = [
        ['Name', `${saved.first_name} ${saved.last_name}`], ['Email', saved.email],
        ['Forwarding phone', saved.forwarding_number], ['Shield number', saved.shield_number],
        ['Agent voice', voice?.name || saved.voice_id], ['Subscription', saved.tier],
        ['Trusted contacts', saved.trusted_contacts?.length ? saved.trusted_contacts.join(', ') : 'None yet — add them later in your dashboard'],
    ];
    const nodes = [];
    for (const [label, value] of fields) {
        const term = document.createElement('dt');
        term.textContent = label;
        const detail = document.createElement('dd');
        detail.textContent = value;
        nodes.push(term, detail);
    }
    byId('review-details').replaceChildren(...nodes);
    renderActivation();
    show('review');
}

function automaticActivation() {
    return ['queued', 'running', 'retry'].includes(saved?.activation_job?.status);
}

function renderActivation() {
    const automatic = automaticActivation();
    byId('edit-details').hidden = saved.number_locked || saved.status === 'provisioning' || automatic;
    byId('edit-contacts').hidden = saved.number_locked || saved.status === 'provisioning' || automatic;
    byId('activate').hidden = saved.status === 'provisioning' || saved.support_review_required || automatic;
    const job = saved.activation_job;
    byId('activation-status').textContent = saved.support_review_required
        ? 'Setup needs a provider review by support before retrying. Your number-order checkpoints are saved; do not purchase another number. Previously confirmed setup resumes automatically after support reopens it.'
        : automatic
            ? job.status === 'retry'
                ? `Your progress is saved. Automatic retry ${job.next_attempt_at ? `after ${new Date(job.next_attempt_at).toLocaleTimeString()}` : 'shortly'}. You can close this page; no second number will be purchased.`
                : job.status === 'queued'
                    ? Date.now() - new Date(job.next_attempt_at).getTime() > 120000
                        ? 'Activation is taking longer than expected to start. Your request is saved. Contact support if this continues; do not purchase another number.'
                        : 'Your activation is queued. Setup continues automatically, even if you close this page.'
                    : `Setup is running${saved.activation_stage ? `: ${saved.activation_stage}` : ''}. You can close this page and return later.`
        : saved.status === 'provisioning'
            ? `Setup is running${saved.activation_stage ? `: ${saved.activation_stage}` : ''}. Refresh status shortly. If it stays here, contact support rather than starting a new purchase.`
            : saved.activation_stage ? `Last step: ${saved.activation_stage}. Your progress is saved.` : '';
}

function scheduleProgress(delay = 4000) {
    clearTimeout(progressTimer);
    if (signedOut || !automaticActivation()) return;
    progressTimer = setTimeout(async () => {
        if (busy) { scheduleProgress(); return; }
        try {
            saved = await api('/api/onboarding/status');
            message('');
            if (saved.status === 'completed') {
                await showCompleted();
                return;
            }
            renderActivation();
            if (saved.error_message) message(saved.error_message);
            scheduleProgress();
        } catch (error) {
            message(`Progress could not be refreshed: ${error.message} Your saved activation has not been restarted.`);
            scheduleProgress(15000);
        }
    }, delay);
}

function updateSetupMode() {
    const carrier = byId('setup-mode').value === 'carrier';
    byId('carrier-guide').hidden = !carrier;
    byId('direct-guide').hidden = carrier;
}

async function loadServiceSetup() {
    byId('service-setup-form').hidden = true;
    byId('service-setup-error').hidden = true;
    byId('reload-service-setup').hidden = true;
    try {
        const data = await api('/api/onboarding/service-setup');
        serviceSetup = data;
        byId('test-destination').textContent = data.forwarding_number;
        byId('setup-mode').value = data.checks.mode;
        for (const [id, key] of [
            ['screening-tested', 'screening_tested'], ['trusted-tested', 'trusted_tested'],
            ['audio-tested', 'audio_tested'], ['carrier-confirmed', 'carrier_forwarding_confirmed'],
        ]) byId(id).checked = data.checks[key];
        updateSetupMode();
        byId('service-setup-status').textContent = 'Your saved, customer-reported checks are shown below. You can update them any time.';
        byId('service-setup-form').hidden = false;
    } catch (error) {
        byId('service-setup-error').textContent = `Call checks are unavailable: ${error.message}`;
        byId('service-setup-error').hidden = false;
        byId('reload-service-setup').hidden = false;
    }
}

async function showCompleted() {
    byId('active-number').textContent = saved.shield_number;
    show('done');
    await loadServiceSetup();
}

function renderContacts() {
    const list = byId('setup-contacts');
    list.replaceChildren();
    draftContacts.forEach((phone, index) => {
        const row = document.createElement('li');
        const label = document.createElement('span');
        label.textContent = phone;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'text-button';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', `Remove ${phone}`);
        remove.onclick = () => {
            draftContacts.splice(index, 1);
            renderContacts();
        };
        row.append(label, remove);
        list.append(row);
    });
    byId('contacts-empty').hidden = draftContacts.length > 0;
    byId('skip-contacts').hidden = draftContacts.length > 0;
}

function showContacts() {
    draftContacts = [...(saved.trusted_contacts || [])];
    byId('contact-number').value = '';
    renderContacts();
    show('contacts');
}

async function load() {
    clearTimeout(progressTimer);
    byId('load-error').hidden = true;
    byId('loading').hidden = false;
    try {
        if (checkoutSession) {
            show('confirmation');
            byId('retry-payment').hidden = true;
            byId('confirmation-status').textContent = 'Checking your checkout securely with Stripe before opening setup.';
            try {
                await api('/api/payments/verify', 'POST', {session_id: checkoutSession});
            } catch (error) {
                byId('confirmation-status').textContent = 'Payment could not be confirmed. Retry here, or sign out and sign in with the account used for checkout.';
                byId('retry-payment').hidden = false;
                throw error;
            }
            checkoutSession = null;
            const url = new URL(location.href);
            url.searchParams.delete('session_id');
            history.replaceState(null, '', url.pathname + url.search + url.hash);
        }
        saved = await api('/api/onboarding/status');
        if (saved.legacy) { location.replace('/static/client-portal.html'); return; }
        byId('account-email').textContent = saved.email;
        byId('email').value = saved.email;
        if (saved.status === 'completed') {
            await showCompleted();
        } else if (saved.payment_status !== 'active') {
            byId('plan').value = 'essential';
            byId('manage-billing').hidden = !saved.billing_available;
            byId('pay').hidden = Boolean(saved.billing_available);
            show('payment');
        } else {
            byId('first-name').value = saved.first_name;
            byId('last-name').value = saved.last_name;
            byId('forwarding-number').value = saved.forwarding_number;
            const ready = saved.shield_number && saved.voice_id;
            if (ready && !saved.contacts_completed && !saved.number_locked && !automaticActivation()) showContacts();
            else if (ready) review();
            else show('profile');
            if (!automaticActivation() && saved.status !== 'provisioning' && !saved.number_locked) await loadVoices();
            if (ready && (saved.contacts_completed || saved.number_locked)) review();
            scheduleProgress();
        }
        if (saved.error_message) message(saved.error_message);
    } catch (error) {
        if (!checkoutSession && !signedOut) {
            show('load-error');
            byId('load-error-message').textContent = 'Your saved progress has not changed. The setup service may be temporarily unavailable. Try again, and contact support if the problem continues.';
        }
        throw error;
    } finally { byId('loading').hidden = true; }
}

byId('pay').onclick = () => run(async () => {
    const checkout = await api('/api/payments/create-checkout', 'POST', {tier: byId('plan').value});
    location.assign(checkout.checkout_url);
});
byId('check-payment').onclick = () => run(load);
byId('retry-payment').onclick = () => run(load);
byId('manage-billing').onclick = () => run(async () => {
    const portal = await api('/api/payments/billing-portal', 'POST');
    location.assign(portal.portal_url);
});
byId('refresh-setup').onclick = () => run(load);
byId('retry-setup-load').onclick = () => run(load);
byId('reload-voices').onclick = () => run(loadVoices);
byId('voice').onchange = previewVoice;
byId('voice-preview').onerror = () => { byId('voice-hint').textContent = 'This preview could not play. Try another voice or reload the choices.'; };
byId('profile-form').onsubmit = (event) => {
    event.preventDefault();
    run(async () => {
        const profile = {
            first_name: byId('first-name').value.trim(), last_name: byId('last-name').value.trim(),
            email: byId('email').value, forwarding_number: byId('forwarding-number').value,
            voice_id: byId('voice').value,
        };
        await api('/api/onboarding/profile', 'PUT', profile);
        saved = await api('/api/onboarding/status');
        show('number');
    });
};
byId('number-search').onsubmit = (event) => {
    event.preventDefault();
    run(async () => {
        byId('search-status').textContent = 'Searching available numbers…';
        byId('number-options').replaceChildren();
        byId('number-options').hidden = true;
        try {
            const data = await api(`/api/onboarding/numbers?area_code=${encodeURIComponent(byId('area-code').value)}`);
            const legend = document.createElement('legend');
            legend.textContent = data.nearby ? 'Nearby Shield numbers' : 'Available Shield numbers';
            byId('number-options').append(legend);
            for (const number of data.numbers) {
                const label = document.createElement('label');
                label.className = 'choice';
                const radio = document.createElement('input');
                radio.type = 'radio'; radio.name = 'shield-number'; radio.value = number.phone_number;
                radio.onchange = () => { byId('save-number').disabled = false; };
                const text = document.createElement('span');
                text.textContent = [number.phone_number, number.locality].filter(Boolean).join(' · ');
                label.append(radio, text);
                byId('number-options').append(label);
            }
            byId('number-options').hidden = !data.numbers.length;
            byId('search-status').textContent = data.numbers.length
                ? (data.nearby
                    ? `No numbers are available in ${byId('area-code').value} right now. Showing ${data.numbers.length} nearby numbers. Choose one to continue.`
                    : `${data.numbers.length} numbers available. Choose one to continue.`)
                : 'No numbers available. Try a nearby area code.';
        } catch (error) { byId('search-status').textContent = 'Search failed. Please try again.'; throw error; }
    });
};
byId('save-number').onclick = () => run(async () => {
    const choice = document.querySelector('input[name="shield-number"]:checked');
    if (!choice) throw new Error('Choose a Shield number.');
    await api('/api/onboarding/number', 'PUT', {phone_number: choice.value, search_area_code: byId('area-code').value});
    saved = await api('/api/onboarding/status');
    showContacts();
});
byId('contact-form').onsubmit = (event) => {
    event.preventDefault();
    message('');
    let phone = byId('contact-number').value.replace(/[\s().-]/g, '');
    if (/^\d{10}$/.test(phone)) phone = `+1${phone}`;
    if (!/^\+[1-9]\d{1,14}$/.test(phone)) {
        message('Enter a phone number with country code, such as +12025550145.');
        return;
    }
    if (phone === saved.shield_number) { message('Your Shield number cannot be a trusted contact.'); return; }
    if (draftContacts.includes(phone)) { message('This contact is already in your list.'); return; }
    if (draftContacts.length >= 100) { message('You can add up to 100 trusted contacts.'); return; }
    draftContacts.push(phone);
    byId('contact-number').value = '';
    renderContacts();
};
async function saveContacts() {
    if (byId('contact-number').value.trim()) {
        throw new Error('Add the phone number to your list, or clear the field before continuing.');
    }
    await api('/api/onboarding/trusted-contacts', 'PUT', {phone_numbers: draftContacts});
    saved = await api('/api/onboarding/status');
    review();
}
byId('save-contacts').onclick = () => run(saveContacts);
byId('skip-contacts').onclick = () => run(saveContacts);
byId('back-number').onclick = () => show('number');
byId('keep-number').onclick = showContacts;
byId('edit-contacts').onclick = showContacts;
byId('back-profile').onclick = () => show('profile');
byId('edit-details').onclick = () => show('profile');
byId('activate').onclick = () => run(async () => {
    byId('activation-status').textContent = 'Saving your activation request. Setup will continue in the background.';
    try {
        await api('/api/onboarding/complete', 'POST');
        await load();
    } catch (error) {
        await load();
        throw error;
    }
});
byId('setup-mode').onchange = updateSetupMode;
byId('reload-service-setup').onclick = () => run(loadServiceSetup);
byId('service-setup-form').onsubmit = (event) => {
    event.preventDefault();
    run(async () => {
        await api('/api/onboarding/service-setup', 'PUT', {
            shield_number: serviceSetup.shield_number,
            forwarding_number: serviceSetup.forwarding_number,
            mode: byId('setup-mode').value,
            screening_tested: byId('screening-tested').checked,
            trusted_tested: byId('trusted-tested').checked,
            audio_tested: byId('audio-tested').checked,
            carrier_forwarding_confirmed: byId('carrier-confirmed').checked,
        });
        byId('service-setup-status').textContent = 'Your call checks are saved to your account. These are your reported results, not an automatic health check.';
    });
};
byId('sign-out').onclick = () => {
    signedOut = true;
    clearTimeout(progressTimer);
    for (const key of ['access_token', 'token', 'user', 'selected_plan']) localStorage.removeItem(key);
    location.assign('/static/login.html');
};
if (!token) location.replace('/static/login.html');
else run(load);
