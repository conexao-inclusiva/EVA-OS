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
        this.wsUrl = 'ws://localhost:8000/ws';
        this.userName = 'ALBERTO';

        this.init();
    }

    init() {
        this.setupWebSocket();
        this.setupEventListeners();
        this.setupSpeechRecognition();
        this.setupModeTabs();
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
        body.innerHTML = text.replace(/\n/g, '<br />');

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