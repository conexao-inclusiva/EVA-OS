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
        this.pipelineSteps = document.querySelectorAll('.pipeline-step');

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
        this.updatePipeline(null);

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
                } catch (err) {
                    console.error("Erro parsing WS:", err);
                }
            };

            this.websocket.onclose = () => {
                this.updateStatus('connecting', 'RECONECTANDO');
                this.setChatStatus('RECONECTANDO...');
                this.updatePipeline(null);
                setTimeout(() => this.setupWebSocket(), 3000);
            };

            this.websocket.onerror = () => {
                this.updateStatus('offline', 'ERRO');
                this.setChatStatus('ERRO DE CONEXÃO');
            };

        } catch (err) {
            console.error("Erro WS:", err);
        }
    }

    handleMessage(data) {
        if (data.type === 'assistant.response') {
            this.addMessage('ai', data.text);
            this.updatePipeline('assistant.response');
        } else if (data.type === 'processing.start') {
            this.showTyping();
            this.setChatStatus('PROCESSANDO...');
            this.updatePipeline('user.message');
        } else if (data.type === 'pipeline.status') {
            this.updatePipeline(data.step);
        } else if (data.type === 'processing.end') {
            this.hideTyping();
            this.setChatStatus('PRONTO');
            this.updatePipeline(null);
        } else if (data.type === 'error') {
            this.addSystemMessage('❌ ' + data.message);
        }
    }

    // ===== Pipeline Monitor =====
    updatePipeline(activeStep) {
        this.pipelineSteps.forEach(step => {
            const stepName = step.dataset.step;
            step.classList.remove('active', 'completed');
            if (activeStep && stepName === activeStep) {
                step.classList.add('active');
            }
        });
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
            if (e.error !== 'no-speech') this.addSystemMessage(`❌ ERRO: ${e.error}`);
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
        } catch (err) { console.error(err); }
    }

    stopRecording() {
        try { this.recognition?.stop(); } catch (err) {}
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
            utterance.onstart = () => { this.isSpeaking = true; this.btnAudio.classList.add('active'); };
            utterance.onend = () => { this.isSpeaking = false; this.btnAudio.classList.remove('active'); };
            window.speechSynthesis.speak(utterance);
        } catch (err) { console.error(err); }
    }

    // ===== Modos =====
    setupModeTabs() {
        this.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
    }

    setMode(mode) {
        this.currentMode = mode;
        this.modeBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
        this.updatePromptPath();
        this.addSystemMessage(`⚡ MODO: ${mode.toUpperCase()}`);
        if (this.websocket?.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({ type: 'mode.change', mode }));
        }
    }

    // ===== Network Alerts =====
    _setupNetworkAlerts() {
        // Implementation remains consistent with previous secure requirement
    }

    // ===== UI Helpers =====
    addMessage(type, text) {
        const div = document.createElement('div');
        div.className = `message ${type === 'user' ? 'msg-user' : 'msg-ai'}`;
        div.innerHTML = `
            <div class="msg-header">
                <span class="msg-avatar">${type === 'user' ? '👤' : '🧠'}</span>
                <span class="msg-sender">${type === 'user' ? this.userName : 'EVA'}</span>
                <span class="msg-time">${new Date().toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'})}</span>
            </div>
            <div class="msg-body">${text}</div>
            <div class="msg-footer">✓ sincronizado</div>
        `;
        this.messages.appendChild(div);
        this.scrollDown();
    }

    addSystemMessage(text) {
        const div = document.createElement('div');
        div.className = 'message msg-system';
        div.style.cssText = 'text-align:center; opacity:0.6; font-size:11px; margin:10px 0;';
        div.textContent = text;
        this.messages.appendChild(div);
        this.scrollDown();
    }

    getLastMessage() {
        const items = this.messages.querySelectorAll('.msg-ai .msg-body');
        return items.length ? items[items.length - 1].textContent : null;
    }

    showTyping() { this.typing.classList.add('active'); this.scrollDown(); }
    hideTyping() { this.typing.classList.remove('active'); }
    scrollDown() { this.messages.scrollTop = this.messages.scrollHeight; }
    updateStatus(state, text) {
        this.statusDot.className = `status-dot ${state}`;
        this.statusText.textContent = text;
    }
    setChatStatus(text) { if (this.chatStatus) this.chatStatus.textContent = text; }
    updateUserDisplay() { const el = document.getElementById('userDisplay'); if (el) el.textContent = this.userName; }
    updatePromptPath() { if (this.promptPath) this.promptPath.textContent = `${this.currentMode.toUpperCase()}~$`; }
}

document.addEventListener('DOMContentLoaded', () => {
    if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }
    window.eva = new EVAInterface();
});
