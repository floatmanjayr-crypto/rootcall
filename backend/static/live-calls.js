const endpoint = '/api/rootcall/live-calls';
const element = (id) => document.getElementById(`live-${id}`);
let selected = null;
let session = null;
let streamController = null;
let takenOver = false;
let busy = false;
let refreshing = false;
const turns = new Map();

function status(message) {
    element('call-status').textContent = message;
}

async function request(path, options = {}) {
    const response = await window.authFetch(path, options);
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Live call request failed');
    }
    return response;
}

function controls(state) {
    takenOver = state === 'taken_over';
    element('takeover').disabled = busy || state !== 'listening';
    element('listen').disabled = busy || takenOver || state === 'ended';
    element('end').disabled = busy || state === 'ended';
    element('mute').hidden = !takenOver;
    element('listen').textContent = state === 'listening' ? 'Stop Listening' : 'Listen';
}

function disconnect() {
    streamController?.abort();
    streamController = null;
    session?.disconnect();
    session = null;
    selected = null;
    takenOver = false;
    turns.clear();
    element('conversation').hidden = true;
}

function renderTranscript() {
    const target = element('transcript');
    const follow = target.scrollHeight - target.scrollTop - target.clientHeight < 70;
    const fragment = document.createDocumentFragment();
    const ordered = [...turns.values()].sort((first, second) => first.time_sec - second.time_sec);
    for (const turn of ordered) {
        if (!['agent', 'user'].includes(turn.role)) continue;
        const row = document.createElement('div');
        row.className = 'live-turn';
        row.dataset.role = turn.role;
        const speaker = document.createElement('strong');
        speaker.textContent = turn.role === 'agent' ? 'RootCall AI' : 'Caller';
        row.append(speaker, document.createTextNode(turn.content || ''));
        fragment.append(row);
    }
    target.replaceChildren(fragment);
    if (follow) target.scrollTop = target.scrollHeight;
}

async function followTranscript(call, controller) {
    try {
        const response = await request(`${endpoint}/${call.id}/transcript`, { signal: controller.signal });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let boundary;
            while ((boundary = buffer.indexOf('\n\n')) >= 0) {
                const frame = buffer.slice(0, boundary);
                buffer = buffer.slice(boundary + 2);
                if (!frame.startsWith('data: ')) continue;
                const event = JSON.parse(frame.slice(6));
                if (event.type === 'stream_error') throw new Error('Transcript disconnected. Select the call again to reconnect.');
                if (event.type === 'call_ended') {
                    if (event.disconnection_reason === 'call_take_over') {
                        if (!busy && !takenOver) {
                            controls('ended');
                            status('Call taken over by another session');
                        }
                        return;
                    }
                    controls('ended');
                    status('Call ended');
                    return;
                }
                for (const turn of event.transcripts || []) turns.set(turn.id, turn);
                renderTranscript();
            }
        }
        if (!controller.signal.aborted && selected?.id === call.id && !takenOver) {
            status('Transcript disconnected. Select the call again to reconnect.');
        }
    } catch (error) {
        if (error.name !== 'AbortError' && selected?.id === call.id) status(error.message);
    }
}

function selectCall(call) {
    if (busy) return;
    if (takenOver && !window.confirm('Leaving will disconnect your call. Continue?')) return;
    disconnect();
    selected = call;
    element('conversation').hidden = false;
    element('caller').textContent = `${call.from_number || 'Unknown caller'} to ${call.to_number || 'RootCall'}`;
    element('transcript').replaceChildren();
    controls('monitoring');
    status('Live transcript connected');
    const controller = new AbortController();
    streamController = controller;
    followTranscript(call, controller);
}

async function refresh() {
    if (refreshing || !window.getToken()) return;
    refreshing = true;
    try {
        const calls = await (await request(endpoint)).json();
        const rows = calls.map((call) => {
            const row = document.createElement('div');
            row.className = 'live-call-row';
            const label = document.createElement('span');
            label.textContent = `${call.from_number || 'Unknown caller'} - ${call.status === 'human-connected' ? 'Human connected' : 'In progress'}`;
            const button = document.createElement('button');
            button.className = 'btn btn-primary';
            button.textContent = 'View Call';
            button.type = 'button';
            button.onclick = () => selectCall(call);
            row.append(label, button);
            return row;
        });
        element('call-list').replaceChildren(...rows);
        if (!selected) status(calls.length ? `${calls.length} active call${calls.length === 1 ? '' : 's'}` : 'No calls in progress');
        if (selected && !calls.some((call) => call.id === selected.id) && !busy) {
            streamController?.abort();
            session?.disconnect();
            session = null;
            controls('ended');
            status('Call ended');
        }
    } catch (error) {
        status(error.message);
    } finally {
        refreshing = false;
    }
}

async function createSession(call) {
    const { RetellClient } = await import('https://esm.sh/retell-client-js-sdk@3.0.3');
    const actions = { 'listen-live-call': 'listen', 'take-over-live-call': 'takeover', 'stop-call': 'end' };
    const client = new RetellClient({
        key: 'server-proxied',
        fetch: async (url, options = {}) => {
            const parts = new URL(String(url)).pathname.split('/');
            const action = actions[parts[2]];
            if (!action || parts[3] !== call.retell_call_id || options.method !== 'POST') {
                throw new Error('Unsupported call action');
            }
            return request(`${endpoint}/${call.id}/${action}`, { method: 'POST', body: options.body });
        },
    });
    return client.monitorCall({
        call_id: call.retell_call_id,
        transcript: false,
        hooks: {
            onStatus: (state) => {
                if (selected?.id !== call.id) return;
                if (state === 'ended' && takenOver) {
                    request(`${endpoint}/${call.id}/release`, { method: 'POST' }).catch(() => {});
                }
                controls(state);
                const labels = { monitoring: 'Live transcript', listening: 'Listening live - microphone off', taken_over: 'You are on the call. AI stopped; transcription paused.', ended: 'Call ended' };
                status(labels[state] || 'Connecting audio...');
            },
            onError: () => { if (selected?.id === call.id) status('Audio connection failed. Try listening again.'); },
        },
    });
}

element('listen').onclick = async () => {
    if (busy || !selected) return;
    busy = true;
    element('listen').disabled = true;
    try {
        if (session?.status === 'listening') {
            session.stopListening();
        } else {
            if (!session) session = await createSession(selected);
            await session.listen();
        }
    } catch (error) {
        status(error.message);
    } finally {
        busy = false;
        controls(session?.status || 'monitoring');
    }
};

element('takeover').onclick = async () => {
    if (busy || !session) return;
    if (!window.confirm('Take over this call? This permanently stops the AI and connects your microphone to the caller.')) return;
    busy = true;
    element('takeover').disabled = true;
    try {
        await session.takeOver();
        streamController?.abort();
    } catch (error) {
        status(error.message || 'Takeover failed. The AI may still be handling the call.');
    } finally {
        busy = false;
        controls(session?.status || 'monitoring');
    }
};

element('mute').onclick = () => {
    const muted = element('mute').getAttribute('aria-pressed') !== 'true';
    if (muted) session?.mute(); else session?.unmute();
    element('mute').setAttribute('aria-pressed', String(muted));
    element('mute').textContent = muted ? 'Unmute' : 'Mute';
};

element('end').onclick = async () => {
    if (busy || !selected || !window.confirm('End this call for everyone?')) return;
    busy = true;
    element('end').disabled = true;
    try {
        if (takenOver && session) await session.end();
        else await request(`${endpoint}/${selected.id}/end`, { method: 'POST' });
        disconnect();
        status('End call requested');
        await refresh();
    } catch (error) {
        status(error.message);
    } finally {
        busy = false;
        if (selected) controls(session?.status || 'monitoring');
    }
};

element('leave').onclick = () => {
    if (busy || (takenOver && !window.confirm('Disconnect from your call? This ends your conversation with the caller.'))) return;
    disconnect();
    refresh();
};
element('refresh').onclick = refresh;
window.addEventListener('beforeunload', (event) => {
    if (takenOver) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('pagehide', disconnect);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
refresh();