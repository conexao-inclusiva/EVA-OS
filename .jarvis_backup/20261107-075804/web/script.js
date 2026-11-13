// ============================================================
// EVA // IA COGNITIVA — AURA STYLE
// ============================================================

class EVAInterface {
    constructor() {
        // DOM Elements
        this.messages = document.getElementById('chatMessages');
        this.input = document.getElementById('messageInput');
        this.btnSend = document.getElementById('btnSend');
        this.btnVoice = document.getElementById('btnVoice');
        this.btnAudio = document.getElementById('btnAudio');
        this.statusDot = document.getElementById('statusDot');
        this.statusText = document.getElementById('statusText');
        this.voiceIndicator = document.getElementById('voiceIndicator');
        this.typing = document.getElementById('typingIndicator');
        this.chatStatus = document.getElementById('chatStatus');
        this.promptPath = document.getElementById('promptPath');

        // Modos
        this.currentMode = 'normal';
        this.modeBtns = document.querySelectorAll('.mode-btn');

        // Estado
        this.isRecording = false;
        this.isSpeaking = false;
        this.websocket = null;
        this.recognition = null;

        // Config
        this.wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
        this.userName = 'ALBERTO';

        this.init();
    }

    init() {
        this.setupWebSocket();
        this.setupEventListeners();
        this.setupSpeechRecognition();
        this.setupModeTabs();
        this._setupNetworkAlerts();
        this.updateStatus('connecting', 'INICIALIZANDO');
        this.setChatStatus('INICIALIZANDO');
        this.updateUserDisplay();
        this.updatePromptPath();

        // Atualiza hora da mensagem de boas-vindas
        const timeEl = document.getElementById('welcomeTime');
        if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('pt-BR');
    }

    // ===== WebSocket =====
    setupWebSocket() {
        try {
            this.websocket = new WebSocket(this.wsUrl);

            this.websocket.onopen = () => {
                this.updateStatus('online', 'ONLINE');
                this.setChatStatus('CONECTADO');
                this.addSystemMessage('🟢 SISTEMA CONECTADO');
            };

            this.websocket.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.handleMessage(data);
                } catch (_) {}
            };

            this.websocket.onclose = () => {
                this.updateStatus('connecting', 'RECONECTANDO');
                this.setChatStatus('RECONECTANDO...');
                setTimeout(() => this.setupWebSocket(), 3000);
            };

            this.websocket.onerror = () => {
                this.updateStatus('offline', 'ERRO');
                this.setChatStatus('ERRO DE CONEXÃO');
            };

        } catch (_) {}
    }

    handleMessage(data) {
        if (data.type === 'assistant.response') {
            this.addMessage('ai', data.text);
        } else if (data.type === 'processing.start') {
            this.showTyping();
            this.setChatStatus('PROCESSANDO...');
        } else if (data.type === 'processing.end') {
            this.hideTyping();
            this.setChatStatus('PRONTO');
        } else if (data.type === 'error') {
            this.addSystemMessage('❌ ' + data.message);
        }
    }

    // ===== Event Listeners =====
    setupEventListeners() {
        this.btnSend.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.btnVoice.addEventListener('click', () => this.toggleRecording());

        this.btnAudio.addEventListener('click', () => {
            const last = this.getLastMessage();
            if (last) this.speak(last);
        });

        // Auto-focus
        this.input.focus();
    }

    // ===== Envio =====
    sendMessage() {
        const text = this.input.value.trim();
        if (!text) return;

        this.addMessage('user', text);
        this.input.value = '';
        this.setChatStatus('ENVIANDO...');

        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'user.message',
                text: text,
                user: this.userName,
                mode: this.currentMode
            }));
        } else {
            this.addSystemMessage('❌ SEM CONEXÃO COM O SERVIDOR');
            this.setChatStatus('OFFLINE');
        }
    }

    // ===== Voz (STT) =====
    setupSpeechRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            this.btnVoice.style.opacity = '0.3';
            this.btnVoice.title = 'STT indisponível';
            return;
        }

        this.recognition = new SR();
        this.recognition.lang = 'pt-BR';
        this.recognition.continuous = false;
        this.recognition.interimResults = true;

        this.recognition.onresult = (e) => {
            let final = '';
            let interim = '';

            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript;
                if (e.results[i].isFinal) final += t;
                else interim += t;
            }

            if (final) {
                this.input.value = final;
                this.sendMessage();
                this.stopRecording();
            } else if (interim) {
                this.input.value = interim;
            }
        };

        this.recognition.onerror = (e) => {
            if (e.error !== 'no-speech') {
                this.addSystemMessage(`❌ ERRO: ${e.error}`);
            }
            this.stopRecording();
        };

        this.recognition.onend = () => this.stopRecording();
    }

    toggleRecording() {
        if (this.isRecording) this.stopRecording();
        else this.startRecording();
    }

    startRecording() {
        if (!this.recognition) return;
        try {
            this.recognition.start();
            this.isRecording = true;
            this.btnVoice.classList.add('active');
            this.voiceIndicator.classList.add('active');
            this.input.placeholder = '🎤 OUVINDO...';
            this.setChatStatus('OUVINDO...');
        } catch (_) {}
    }

    stopRecording() {
        try { this.recognition?.stop(); } catch (_) {}
        this.isRecording = false;
        this.btnVoice.classList.remove('active');
        this.voiceIndicator.classList.remove('active');
        this.input.placeholder = 'Insira seu comando ou mensagem...';
        this.setChatStatus('PRONTO');
    }

    // ===== Voz (TTS) =====
    speak(text) {
        if (this.isSpeaking) window.speechSynthesis.cancel();

        try {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'pt-BR';
            utterance.rate = 0.85;
            utterance.pitch = 1.1;

            const voices = window.speechSynthesis.getVoices();
            const ptVoice = voices.find(v => v.lang.startsWith('pt') && v.name.includes('Feminino'));
            if (ptVoice) utterance.voice = ptVoice;

            utterance.onstart = () => { this.isSpeaking = true; this.btnAudio.style.color = '#00f3ff'; };
            utterance.onend = () => { this.isSpeaking = false; this.btnAudio.style.color = ''; };
            utterance.onerror = () => { this.isSpeaking = false; this.btnAudio.style.color = ''; };

            window.speechSynthesis.speak(utterance);
        } catch (_) {}
    }

    // ===== Modos =====
    setupModeTabs() {
        this.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                this.setMode(mode);
            });
        });
    }

    setMode(mode) {
        this.currentMode = mode;

        this.modeBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        const container = document.getElementById('chatArea');
        container.classList.remove('mode-nicolas', 'mode-expert', 'mode-terminal');
        if (mode === 'nicolas') {
            container.classList.add('mode-nicolas');
            this.addSystemMessage('🧸 MODO NICOLAS ATIVADO');
        } else if (mode === 'expert') {
            container.classList.add('mode-expert');
            this.addSystemMessage('🧠 MODO EXPERT ATIVADO');
        } else if (mode === 'terminal') {
            container.classList.add('mode-terminal');
            this.addSystemMessage('⌨️ MODO TERMINAL ATIVADO');
        } else if (mode === 'family') {
            this.addSystemMessage('🏠 MODO FAMÍLIA ATIVADO');
        } else {
            this.addSystemMessage('💬 MODO CONVERSA');
        }

        this.updatePromptPath();

        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({ type: 'mode.change', mode }));
        }
    }

    _setupNetworkAlerts() {
        if (this._networkAlertUI) return;
        const make = (tag, text) => {
            const node = document.createElement(tag);
            if (text !== undefined) node.textContent = text;
            return node;
        };
        const panel = make('details');
        panel.id = 'evaNetworkAlerts';
        panel.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:1000;width:360px;max-width:calc(100vw - 32px);max-height:75vh;overflow:auto;background:#101827;color:#e5edf8;border:1px solid #52657d;border-radius:12px;padding:12px;font:14px/1.5 sans-serif;box-shadow:0 8px 28px #0008;';
        const summary = make('summary', 'Alertas de rede');
        summary.style.cssText = 'cursor:pointer;font-weight:bold;';
        const description = make('p', 'Acesso de leitura. Verifica conectividade; imagens e gravacoes nao sao verificadas.');
        const label = make('label', 'Chave de acesso');
        label.htmlFor = 'evaNetworkAlertKey';
        const input = make('input');
        input.id = 'evaNetworkAlertKey';
        input.type = 'password';
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.maxLength = 128;
        input.style.cssText = 'display:block;box-sizing:border-box;width:100%;margin:6px 0 10px;padding:8px;background:#182438;color:#fff;border:1px solid #71839b;border-radius:6px;';
        const form = make('form');
        form.autocomplete = 'off';
        const connect = make('button', 'Conectar');
        connect.type = 'submit';
        const disconnect = make('button', 'Sair e limpar');
        disconnect.type = 'button';
        for (const button of [connect, disconnect]) {
            button.style.cssText = 'padding:7px 10px;margin:0 8px 6px 0;border-radius:6px;cursor:pointer;';
        }
        const status = make('p');
        status.setAttribute('role', 'status');
        const notice = make('p', 'Ultimos 100 eventos desta sessao do servidor. Historico nao persistente.');
        notice.style.cssText = 'font-size:12px;color:#bec9d9;';
        const list = make('ol');
        list.setAttribute('aria-live', 'polite');
        list.style.cssText = 'padding-left:22px;max-height:280px;overflow:auto;';
        form.append(label, input, connect, disconnect);
        panel.append(summary, description, form, status, notice, list);
        document.body.appendChild(panel);
        this._networkAlertUI = {panel, input, connect, disconnect, status, notice, list};
        this._networkAlertSeen = new Set();
        this._networkAlertGeneration = 0;
        this._stopNetworkAlerts();
        form.addEventListener('submit', event => {
            event.preventDefault();
            this._startNetworkAlerts(input.value);
        });
        disconnect.addEventListener('click', () => this._stopNetworkAlerts());
        window.addEventListener('pagehide', () => this._stopNetworkAlerts());
    }

    _stopNetworkAlerts(message = 'Desconectado.') {
        this._networkAlertGeneration += 1;
        clearTimeout(this._networkAlertTimer);
        this._networkAlertTimer = null;
        if (this._networkAlertAbort) this._networkAlertAbort.abort();
        this._networkAlertAbort = null;
        this._networkAlertKey = '';
        this._networkAlertCursor = 0;
        this._networkAlertSeen.clear();
        const ui = this._networkAlertUI;
        ui.input.value = '';
        ui.input.disabled = false;
        ui.connect.disabled = false;
        ui.disconnect.disabled = true;
        ui.list.replaceChildren();
        ui.status.textContent = message;
        ui.notice.textContent = 'Ultimos 100 eventos desta sessao do servidor. Historico nao persistente.';
    }

    _startNetworkAlerts(key) {
        this._stopNetworkAlerts();
        const ui = this._networkAlertUI;
        const location = window.location;
        const local = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
        if (!(location.protocol === 'https:' || (location.protocol === 'http:' && local))) {
            ui.status.textContent = 'Use HTTPS ou abra a EVA neste computador por localhost.';
            return;
        }
        if (typeof key !== 'string' || !/^[A-Za-z0-9_-]{43,128}$/.test(key)) {
            ui.status.textContent = 'Chave invalida. Informe a chave de leitura fornecida no computador da EVA.';
            return;
        }
        this._networkAlertKey = key;
        ui.input.value = '';
        ui.input.disabled = true;
        ui.connect.disabled = true;
        ui.disconnect.disabled = false;
        ui.status.textContent = 'Validando acesso...';
        return this._pollNetworkAlerts(this._networkAlertGeneration);
    }

    async _pollNetworkAlerts(generation) {
        if (generation !== this._networkAlertGeneration || !this._networkAlertKey) return;
        const controller = new AbortController();
        this._networkAlertAbort = controller;
        const deadline = setTimeout(() => controller.abort(), 8000);
        try {
            const response = await fetch(
                '/security/network-alerts?after=' + this._networkAlertCursor,
                {
                    method: 'GET',
                    headers: {Authorization: 'Bearer ' + this._networkAlertKey},
                    cache: 'no-store',
                    credentials: 'omit',
                    redirect: 'error',
                    referrerPolicy: 'no-referrer',
                    signal: controller.signal,
                }
            );
            if (generation !== this._networkAlertGeneration) return;
            if ([400, 401, 403, 503].includes(response.status)) {
                const messages = {
                    400: 'Consulta rejeitada. Conecte novamente.',
                    401: 'Acesso negado. Confira a chave de leitura.',
                    403: 'Conexao rejeitada. Use HTTPS ou localhost no computador da EVA.',
                    503: 'Canal indisponivel. A chave precisa estar configurada no servidor.',
                };
                this._stopNetworkAlerts(messages[response.status]);
                return;
            }
            if (!response.ok) throw new Error('request_failed');
            const body = await response.json();
            if (generation !== this._networkAlertGeneration) return;
            this._renderNetworkAlerts(body);
            this._networkAlertUI.status.textContent = 'Canal conectado. Aguardando novos eventos.';
        } catch (_) {
            if (generation !== this._networkAlertGeneration) return;
            this._networkAlertUI.status.textContent = 'Conexao interrompida. Nova tentativa em 5 segundos.';
        } finally {
            clearTimeout(deadline);
            if (this._networkAlertAbort === controller) this._networkAlertAbort = null;
            if (generation === this._networkAlertGeneration && this._networkAlertKey) {
                this._networkAlertTimer = setTimeout(
                    () => this._pollNetworkAlerts(generation), 5000
                );
            }
        }
    }

    _renderNetworkAlerts(body) {
        if (!body || body.scope !== 'connectivity_only'
                || !Number.isSafeInteger(body.cursor) || body.cursor < 0
                || typeof body.gap !== 'boolean'
                || !Array.isArray(body.events) || body.events.length > 100) {
            throw new Error('invalid_alert_response');
        }
        for (const item of body.events) {
            const states = {
                'security.network.alert': 'unavailable',
                'security.network.recovered': 'available',
            };
            if (!item || !states[item.type] || item.scope !== 'connectivity_only'
                    || !Number.isSafeInteger(item.sequence) || item.sequence < 1
                    || item.sequence > body.cursor
                    || typeof item.notification_id !== 'string'
                    || !/^[A-Za-z0-9_-]{1,128}$/.test(item.notification_id)
                    || !item.target || typeof item.target.id !== 'string'
                    || !/^[A-Za-z0-9_-]{1,64}$/.test(item.target.id)
                    || item.target.state !== states[item.type]
                    || typeof item.checked_at !== 'string' || item.checked_at.length > 64
                    || typeof item.message !== 'string' || item.message.length > 512) {
                throw new Error('invalid_alert_event');
            }
        }
        const ui = this._networkAlertUI;
        if (body.cursor < this._networkAlertCursor) {
            ui.list.replaceChildren();
            this._networkAlertSeen.clear();
        }
        if (body.gap) {
            ui.notice.textContent = 'Parte do historico nao esta disponivel ou o servidor foi reiniciado.';
        }
        for (const item of body.events) {
            if (this._networkAlertSeen.has(item.notification_id)) continue;
            this._networkAlertSeen.add(item.notification_id);
            while (this._networkAlertSeen.size > 300) {
                this._networkAlertSeen.delete(this._networkAlertSeen.values().next().value);
            }
            const row = document.createElement('li');
            row.style.cssText = 'white-space:pre-wrap;padding:8px 0;border-bottom:1px solid #354258;';
            const recovered = item.type === 'security.network.recovered';
            const time = new Date(item.checked_at);
            const timeLabel = Number.isNaN(time.getTime()) ? item.checked_at : time.toLocaleString('pt-BR');
            row.textContent = (recovered ? 'RECUPERADO: ' : 'ALERTA: ')
                + item.target.id + '\n' + item.message + '\n' + timeLabel;
            ui.list.prepend(row);
            while (ui.list.children.length > 100) {
                ui.list.removeChild(ui.list.lastElementChild);
            }
        }
        this._networkAlertCursor = body.cursor;
    }

    // ===== UI Helpers =====
    addMessage(type, text) {
        const div = document.createElement('div');
        div.className = `message ${type === 'user' ? 'msg-user' : 'msg-ai'}`;

        const header = document.createElement('div');
        header.className = 'msg-header';

        const avatar = document.createElement('span');
        avatar.className = 'msg-avatar';
        avatar.textContent = type === 'user' ? '👤' : '🧠';

        const sender = document.createElement('span');
        sender.className = 'msg-sender';
        sender.textContent = type === 'user' ? this.userName : 'EVA';

        const time = document.createElement('span');
        time.className = 'msg-time';
        time.textContent = new Date().toLocaleTimeString('pt-BR');

        header.appendChild(avatar);
        header.appendChild(sender);
        header.appendChild(time);

        const body = document.createElement('div');
        body.className = 'msg-body';
        body.textContent = String(text ?? '');
        body.style.whiteSpace = 'pre-wrap';

        const footer = document.createElement('div');
        footer.className = 'msg-footer';
        footer.innerHTML = `<span class="msg-status">✓ sincronizado</span>`;

        div.appendChild(header);
        div.appendChild(body);
        div.appendChild(footer);
        this.messages.appendChild(div);
        this.scrollDown();
    }

    addSystemMessage(text) {
        const div = document.createElement('div');
        div.className = 'message msg-system';
        div.style.cssText = 'align-self:center; max-width:90%; padding:8px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); text-align:center; font-size:12px; color:#8899bb; letter-spacing:1px;';

        const body = document.createElement('div');
        body.className = 'msg-body';
        body.textContent = text;

        div.appendChild(body);
        this.messages.appendChild(div);
        this.scrollDown();
    }

    getLastMessage() {
        const items = this.messages.querySelectorAll('.msg-ai .msg-body');
        return items.length ? items[items.length - 1].textContent : null;
    }

    showTyping() {
        this.typing.classList.add('active');
        this.scrollDown();
    }

    hideTyping() {
        this.typing.classList.remove('active');
    }

    scrollDown() {
        setTimeout(() => {
            this.messages.scrollTop = this.messages.scrollHeight;
        }, 50);
    }

    updateStatus(state, text) {
        this.statusDot.className = 'status-dot';
        if (state === 'online') this.statusDot.classList.add('online');
        else if (state === 'connecting') this.statusDot.classList.add('connecting');
        this.statusText.textContent = text;
    }

    setChatStatus(text) {
        if (this.chatStatus) this.chatStatus.textContent = text;
    }

    updateUserDisplay() {
        const el = document.getElementById('userDisplay');
        if (el) el.textContent = this.userName;
    }

    updatePromptPath() {
        if (!this.promptPath) return;
        const modeMap = {
            'normal': 'EVA~$',
            'nicolas': 'NICOLAS~$',
            'family': 'FAMILIA~$',
            'expert': 'EXPERT~$',
            'terminal': 'TERMINAL~$'
        };
        this.promptPath.textContent = modeMap[this.currentMode] || 'EVA~$';
    }
}

// ===== Inicialização =====
document.addEventListener('DOMContentLoaded', () => {
    if (window.speechSynthesis) {
        window.speechSynthesis.getVoices();
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }

    window.eva = new EVAInterface();
});

console.log('🧠 EVA // IA COGNITIVA — AURA STYLE carregada!');
console.log('✦ Sistema operacional. Aguardando comandos, Criador.');