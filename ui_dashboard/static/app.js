// Shelly Virtual Waiter — frontend (Pass 2: text + voice + auto-TTS)

const state = {
    menu: null,
    current: {
        state: 'STATE_GREETING',
        session_id: null,
        table_no: null,
        order: null,
    },
};

let currentAudio = null;
let currentAudioUrl = null;

// ---------- DOM helpers ----------
const $ = (id) => document.getElementById(id);
const chatLog = () => $('chat-log');
const chatDrawer = () => $('chat-drawer');
const chatInput = () => $('chat-input');

function setStatus(text) {
    const pill = $('status-pill');
    pill.textContent = text;
    pill.classList.remove('idle', 'listening', 'thinking', 'speaking');
    const t = text.toLowerCase();
    if (t.includes('listen')) pill.classList.add('listening');
    else if (t.includes('think')) pill.classList.add('thinking');
    else if (t.includes('speak')) pill.classList.add('speaking');
    else pill.classList.add('idle');
}

// ---------- API helper ----------
async function api(path, method = 'GET', body = null) {
    const opts = { method, headers: {} };
    if (body !== null) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    let res;
    try { res = await fetch(path, opts); }
    catch (e) { return { status: 'error', message: 'Network error.' }; }
    let data;
    try { data = await res.json(); }
    catch { data = { status: 'error', message: 'Invalid server response.' }; }
    return data;
}

// ---------- Menu ----------
async function loadMenu() {
    const data = await api('/api/menu');
    if (data.status !== 'success') return;
    state.menu = data.items;
    renderMenu(data.items);
}

function renderMenu(items) {
    const container = $('menu-content');
    container.innerHTML = '';
    const grouped = {};
    for (const it of items) {
        (grouped[it.category] = grouped[it.category] || []).push(it);
    }
    for (const [cat, arr] of Object.entries(grouped)) {
        const group = document.createElement('div');
        group.className = 'menu-group';
        const h3 = document.createElement('h3');
        h3.textContent = cat;
        group.appendChild(h3);
        const ul = document.createElement('ul');
        for (const it of arr) {
            const li = document.createElement('li');
            if (it.stock_qty === 0) li.classList.add('out');
            const name = document.createElement('span');
            name.className = 'item-name';
            name.textContent = it.stock_qty === 0 ? `${it.name} (out)` : it.name;
            const price = document.createElement('span');
            price.className = 'item-price';
            price.textContent = `₱${Number(it.price).toFixed(2)}`;
            li.appendChild(name);
            li.appendChild(price);
            ul.appendChild(li);
        }
        group.appendChild(ul);
        container.appendChild(group);
    }
}

// ---------- Layout / state application ----------
function applyState(snapshot) {
    if (snapshot.state) state.current.state = snapshot.state;
    if ('session_id' in snapshot) state.current.session_id = snapshot.session_id;
    if ('table_no' in snapshot) state.current.table_no = snapshot.table_no;
    if ('order' in snapshot) state.current.order = snapshot.order;
    renderLayout();
}

function renderLayout() {
    const s = state.current.state;
    const showOrder = state.current.session_id && s !== 'STATE_GREETING';
    $('welcome-panel').hidden = !!showOrder;
    $('order-panel').hidden = !showOrder;
    if (showOrder) renderOrder(state.current.order);
}

function renderOrder(order) {
    const s = state.current.state;
    const locked = (s === 'STATE_CONFIRMED' || s === 'STATE_COMPLETED');

    $('table-label').textContent = state.current.table_no
        ? `(Table ${state.current.table_no})` : '';
    $('state-badge').textContent = s.replace('STATE_', '').replace('_', ' ');

    const linesEl = $('order-lines');
    linesEl.innerHTML = '';

    if (!order || !order.lines || order.lines.length === 0) {
        const p = document.createElement('p');
        p.className = 'muted';
        p.textContent = 'Your cart is empty. Add items via chat.';
        linesEl.appendChild(p);
    } else {
        for (const ln of order.lines) {
            const div = document.createElement('div');
            div.className = 'order-line';
            div.dataset.itemName = ln.name;

            const nameEl = document.createElement('div');
            nameEl.className = 'line-name';
            nameEl.textContent = ln.name;
            if (ln.instructions) {
                const badge = document.createElement('span');
                badge.className = 'line-badge';
                badge.textContent = ln.instructions;
                nameEl.appendChild(badge);
            }

            const qtyEl = document.createElement('div');
            qtyEl.className = 'line-qty';
            qtyEl.textContent = `× ${ln.quantity}`;

            const ctrl = document.createElement('div');
            ctrl.className = 'line-controls';
            const dec = document.createElement('button');
            dec.textContent = '−';
            dec.dataset.action = 'dec';
            dec.disabled = locked;
            const inc = document.createElement('button');
            inc.textContent = '+';
            inc.dataset.action = 'inc';
            inc.disabled = locked;
            ctrl.appendChild(dec);
            ctrl.appendChild(inc);

            const unit = document.createElement('div');
            unit.className = 'line-unit';
            unit.textContent = `₱${Number(ln.price).toFixed(2)} ea`;

            const total = document.createElement('div');
            total.className = 'line-total';
            total.textContent = `₱${Number(ln.line_total).toFixed(2)}`;

            div.appendChild(nameEl);
            div.appendChild(qtyEl);
            div.appendChild(ctrl);
            div.appendChild(unit);
            div.appendChild(total);
            linesEl.appendChild(div);
        }
    }

    const subtotal = order ? Number(order.subtotal) : 0;
    const fee = order ? Number(order.service_fee) : 0;
    const gt = order ? Number(order.grand_total) : 0;
    $('subtotal').textContent = `₱${subtotal.toFixed(2)}`;
    $('service-fee').textContent = `₱${fee.toFixed(2)}`;
    $('grand-total').textContent = `₱${gt.toFixed(2)}`;

    const btn = $('confirm-button');
    const empty = !order || !order.lines || order.lines.length === 0;
    btn.disabled = locked || empty;
    btn.textContent = locked ? 'Order Confirmed' : 'Confirm my Order';
}

// ---------- Chat ----------
function appendChat(who, text) {
    const log = chatLog();
    const div = document.createElement('div');
    div.className = `chat-msg ${who}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function openChat() {
    chatDrawer().hidden = false;
    chatInput().focus();
}
function closeChat() { chatDrawer().hidden = true; }
function toggleChat() {
    if (chatDrawer().hidden) openChat(); else closeChat();
}

// ---------- TTS ----------
function stopAudio() {
    if (currentAudio) {
        try { currentAudio.pause(); } catch (e) {}
        currentAudio = null;
    }
    if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
    }
}

async function speak(text) {
    if (!text) { setStatus('Idle'); return; }
    stopAudio();
    setStatus('Speaking…');
    try {
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        if (!res.ok) { setStatus('Idle'); return; }
        const blob = await res.blob();
        currentAudioUrl = URL.createObjectURL(blob);
        currentAudio = new Audio(currentAudioUrl);
        currentAudio.onended = () => {
            URL.revokeObjectURL(currentAudioUrl);
            currentAudioUrl = null;
            currentAudio = null;
            setStatus('Idle');
        };
        currentAudio.onerror = () => {
            URL.revokeObjectURL(currentAudioUrl);
            currentAudioUrl = null;
            currentAudio = null;
            setStatus('Idle');
        };
        try {
            await currentAudio.play();
        } catch (e) {
            console.warn('TTS playback blocked:', e);
            setStatus('Idle');
        }
    } catch (e) {
        console.error(e);
        setStatus('Idle');
    }
}

// ---------- Shared chat submission (text + voice) ----------
async function submitUserText(text) {
    appendChat('user', text);
    setStatus('Thinking…');
    const res = await api('/api/chat', 'POST', { message: text });
    if (res.status === 'success') {
        appendChat('shelly', res.reply);
        applyState({
            state: res.state,
            session_id: res.session_id,
            table_no: res.table_no,
            order: res.order,
        });
        await speak(res.reply);
    } else {
        setStatus('Idle');
        appendChat('shelly', res.message || 'Something went wrong.');
    }
}

async function sendMessage(text) {
    text = (text || '').trim();
    if (!text) return;
    chatInput().value = '';
    await submitUserText(text);
}

// ---------- Cart ----------
async function cartUpdate(itemName, action) {
    const res = await api('/api/cart/update', 'POST', { item_name: itemName, action });
    if (res.status === 'success') {
        applyState({ order: res.order, state: res.state });
    } else {
        appendChat('shelly', res.message || 'Could not update cart.');
        openChat();
    }
}

// ---------- Confirm flow ----------
function openConfirmModal() { $('confirm-modal').hidden = false; }
function closeConfirmModal() { $('confirm-modal').hidden = true; }

async function doConfirm() {
    setStatus('Thinking…');
    const rev = await api('/api/review', 'POST');
    if (rev.status === 'success') {
        applyState({ order: rev.order, state: rev.state });
        if (rev.reply) appendChat('shelly', rev.reply);
    }
    const res = await api('/api/confirm', 'POST', { yes: true });
    if (res.status === 'success') {
        if (res.reply) appendChat('shelly', res.reply);
        applyState({ order: res.order, state: res.state });
        closeConfirmModal();
        await speak(res.reply);
    } else {
        setStatus('Idle');
        appendChat('shelly', res.message || 'Could not confirm order.');
        closeConfirmModal();
    }
}

// ---------- Voice recording ----------
const voice = {
    mediaStream: null,
    audioContext: null,
    sourceNode: null,
    processorNode: null,
    chunks: [],
    recording: false,
    sampleRate: 16000,
    supported: false,

    async init() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.supported = false;
            return false;
        }
        this.supported = true;
        return true;
    },

    async start() {
        if (this.recording) return { ok: false, message: 'Already recording.' };
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });
        } catch (e) {
            return { ok: false, message: 'Microphone permission denied.' };
        }

        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            this._cleanup();
            return { ok: false, message: 'Audio context unavailable.' };
        }
        this.sampleRate = this.audioContext.sampleRate || 48000;

        this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
        this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
        this.chunks = [];
        this.processorNode.onaudioprocess = (e) => {
            if (!this.recording) return;
            this.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
        };
        this.sourceNode.connect(this.processorNode);
        this.processorNode.connect(this.audioContext.destination);
        this.recording = true;
        return { ok: true };
    },

    async stop() {
        this.recording = false;
        const sr = this.sampleRate;
        this._cleanup();
        const total = this.chunks.reduce((s, c) => s + c.length, 0);
        if (total < sr * 0.3) {
            this.chunks = [];
            return null;
        }
        const combined = new Float32Array(total);
        let offset = 0;
        for (const c of this.chunks) { combined.set(c, offset); offset += c.length; }
        this.chunks = [];
        return { samples: combined, sampleRate: sr };
    },

    _cleanup() {
        if (this.processorNode) {
            try { this.processorNode.disconnect(); } catch (e) {}
            this.processorNode = null;
        }
        if (this.sourceNode) {
            try { this.sourceNode.disconnect(); } catch (e) {}
            this.sourceNode = null;
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(t => t.stop());
            this.mediaStream = null;
        }
        if (this.audioContext) {
            try { this.audioContext.close(); } catch (e) {}
            this.audioContext = null;
        }
    },
};

function encodeWAV(samples, sampleRate) {
    const len = samples.length;
    const buffer = new ArrayBuffer(44 + len * 2);
    const view = new DataView(buffer);
    const writeStr = (o, s) => {
        for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i));
    };
    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + len * 2, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, 'data');
    view.setUint32(40, len * 2, true);
    let offset = 44;
    for (let i = 0; i < len; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

async function startRecording() {
    stopAudio();
    setStatus('Listening…');
    const r = await voice.start();
    if (!r.ok) {
        setStatus('Idle');
        appendChat('shelly', r.message || 'Could not start recording.');
        return;
    }
    const mic = $('mic-button');
    mic.classList.add('recording');
    mic.title = 'Click to stop recording';
}

async function stopRecordingAndTranscribe() {
    const captured = await voice.stop();
    const mic = $('mic-button');
    mic.classList.remove('recording');
    mic.title = 'Click to speak';

    if (!captured) {
        setStatus('Idle');
        return;
    }
    setStatus('Thinking…');
    try {
        const wavBlob = encodeWAV(captured.samples, captured.sampleRate);
        const b64 = await blobToBase64(wavBlob);
        const stt = await api('/api/stt', 'POST', { audio_b64: b64 });
        if (stt.status !== 'success' || !stt.text) {
            const errMsg = stt.message || "I didn't catch that. Please try again.";
            appendChat('shelly', errMsg);
            await speak(errMsg);
            return;
        }
        await submitUserText(stt.text);
    } catch (e) {
        console.error(e);
        const errMsg = 'Could not process the recording.';
        appendChat('shelly', errMsg);
        await speak(errMsg);
    }
}

async function onMicClick() {
    if (voice.recording) {
        await stopRecordingAndTranscribe();
    } else {
        await startRecording();
    }
}

// ---------- Init ----------
async function init() {
    await loadMenu();
    const st = await api('/api/state');
    applyState({
        state: st.state,
        session_id: st.session_id,
        table_no: st.table_no,
        order: st.order,
    });

    if (state.current.state === 'STATE_GREETING') {
        appendChat('shelly',
            "Hi! I'm Shelly. Tell me your table number (for example, \"Table 5\") to get started.");
    }

    $('chat-toggle').addEventListener('click', toggleChat);
    $('chat-close').addEventListener('click', closeChat);
    $('chat-form').addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage(chatInput().value);
    });
    $('confirm-button').addEventListener('click', openConfirmModal);
    $('confirm-yes').addEventListener('click', doConfirm);
    $('confirm-no').addEventListener('click', closeConfirmModal);

    $('order-lines').addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const line = btn.closest('.order-line');
        if (!line) return;
        cartUpdate(line.dataset.itemName, btn.dataset.action);
    });

    // Voice support check
    const supported = await voice.init();
    const mic = $('mic-button');
    if (!supported) {
        mic.disabled = true;
        mic.title = 'Microphone not supported in this browser';
    } else {
        mic.disabled = false;
        mic.addEventListener('click', onMicClick);
    }
}

document.addEventListener('DOMContentLoaded', init);