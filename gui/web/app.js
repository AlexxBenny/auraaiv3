/**
 * AURA Modern GUI - Application JavaScript
 * Advanced Neural Network Interface with Voice Animation
 */

class AuraApp {
    constructor() {
        // DOM Elements
        this.elements = {
            chatContainer: document.getElementById('chat-container'),
            chatMessages: document.getElementById('chat-messages'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            voiceToggle: document.getElementById('voice-toggle'),
            voiceOrb: document.getElementById('voice-orb'),
            voiceOrbContainer: document.getElementById('voice-orb-container'),
            orbLabel: document.getElementById('orb-label'),
            settingsBtn: document.getElementById('settings-btn'),
            settingsModal: document.getElementById('settings-modal'),
            closeSettings: document.getElementById('close-settings'),
            clearBtn: document.getElementById('clear-btn'),
            voiceStatusDot: document.getElementById('voice-status-dot'),
            voiceStatusText: document.getElementById('voice-status-text'),
        };

        // State
        this.state = {
            isListening: false,
            isProcessing: false,
            isSpeaking: false,
            voiceEnabled: true,
            commandCount: 0,
            sessionStart: new Date(),
            backendConnected: false,
            backendReady: false,  // True only after backend sends 'ready' signal
        };

        // WebSocket connection
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;

        // Speech Recognition & Synthesis
        this.speechRecognition = null;
        this.speechSynthesis = window.speechSynthesis;

        // Initialize
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initSpeechRecognition();
        this.connectWebSocket();
        this.showWelcomeMessage();
        this.updateVoiceStatus();
    }

    connectWebSocket() {
        // Get WebSocket URL based on current location
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('Connected to AURA backend');
                this.state.backendConnected = true;
                this.reconnectAttempts = 0;
                this.addSystemMessage('Neural network backend connected.');
            };

            this.websocket.onclose = () => {
                console.log('Disconnected from AURA backend');
                this.state.backendConnected = false;
                this.scheduleReconnect();
            };

            this.websocket.onerror = (error) => {
                console.warn('WebSocket error:', error);
                // Will use demo mode as fallback
            };

            this.websocket.onmessage = (event) => {
                this.handleBackendMessage(JSON.parse(event.data));
            };
        } catch (error) {
            console.warn('Failed to connect to backend, using demo mode:', error);
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connectWebSocket(), delay);
        }
    }

    handleBackendMessage(data) {
        // Handle server responses
        console.log('Backend response:', data);

        // Handle ready signal from server
        if (data.type === 'ready') {
            this.state.backendReady = true;
            this.addSystemMessage('Backend fully initialized. Ready for commands.');
            this.enableInput();
            return;
        }

        // Handle streaming progress messages
        if (data.type === 'progress') {
            this.updateProgressBubble(data.message);
            return;
        }

        if (this.pendingResolve) {
            this.pendingResolve(data);
            this.pendingResolve = null;
        }
    }

    updateProgressBubble(text) {
        // Update the current "thinking" bubble with progress text
        const bubbles = this.elements.chatMessages.querySelectorAll('.neural .message-bubble');
        if (bubbles.length > 0) {
            const lastBubble = bubbles[bubbles.length - 1];
            lastBubble.textContent = text;
        }
    }

    enableInput() {
        // Enable input after backend is ready
        this.elements.messageInput.disabled = false;
        this.elements.messageInput.placeholder = 'Type your command...';
        this.elements.sendBtn.disabled = false;
    }

    disableInput() {
        // Disable input while waiting for backend
        this.elements.messageInput.disabled = true;
        this.elements.messageInput.placeholder = 'Waiting for backend...';
        this.elements.sendBtn.disabled = true;
    }

    addSystemMessage(text) {
        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        console.log(`[${timestamp}] System: ${text}`);
    }

    setupEventListeners() {
        // Send message
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

        // Enter key handling
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.messageInput.style.height = 'auto';
            this.elements.messageInput.style.height =
                Math.min(this.elements.messageInput.scrollHeight, 150) + 'px';
        });

        // Voice orb click
        this.elements.voiceOrb.addEventListener('click', () => this.toggleVoiceInput());

        // Voice toggle button
        this.elements.voiceToggle.addEventListener('click', () => this.toggleVoiceInput());

        // Settings modal
        this.elements.settingsBtn.addEventListener('click', () => this.openSettings());
        this.elements.closeSettings.addEventListener('click', () => this.closeSettings());
        this.elements.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.elements.settingsModal) {
                this.closeSettings();
            }
        });

        // Clear chat
        this.elements.clearBtn.addEventListener('click', () => this.clearChat());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'l') {
                e.preventDefault();
                this.clearChat();
            }
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.openSettings();
            }
            if (e.key === 'Escape') {
                this.closeSettings();
                if (this.state.isListening) {
                    this.stopListening();
                }
            }
        });
    }

    initSpeechRecognition() {
        // Check for browser support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('Speech recognition not supported');
            this.state.voiceEnabled = false;
            this.updateVoiceStatus(false);
            return;
        }

        this.speechRecognition = new SpeechRecognition();
        this.speechRecognition.continuous = false;
        this.speechRecognition.interimResults = true;
        this.speechRecognition.lang = 'en-US';

        this.speechRecognition.onstart = () => {
            this.state.isListening = true;
            this.elements.voiceOrb.classList.add('listening');
            this.elements.voiceToggle.classList.add('active');
            this.elements.orbLabel.textContent = 'Listening...';
            this.updateVoiceStatus(true, 'LISTENING');
        };

        this.speechRecognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0])
                .map(result => result.transcript)
                .join('');

            // Update input field with interim results
            this.elements.messageInput.value = transcript;

            // If final result, send the message
            if (event.results[0].isFinal) {
                this.stopListening();
                setTimeout(() => this.sendMessage(), 300);
            }
        };

        this.speechRecognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.stopListening();
            if (event.error === 'no-speech') {
                this.addMessage('aura', 'No speech detected. Please try again.', 'error');
            }
        };

        this.speechRecognition.onend = () => {
            this.stopListening();
        };

        this.updateVoiceStatus(true);
    }

    updateVoiceStatus(enabled = this.state.voiceEnabled, status = 'VOICE READY') {
        const dot = this.elements.voiceStatusDot;
        const text = this.elements.voiceStatusText;

        if (enabled) {
            dot.classList.add('pulse');
            dot.style.background = status === 'LISTENING' ?
                'var(--color-warning)' : 'var(--color-success)';
            text.textContent = status;
        } else {
            dot.classList.remove('pulse');
            dot.style.background = 'var(--color-error)';
            text.textContent = 'VOICE OFFLINE';
        }
    }

    toggleVoiceInput() {
        if (!this.state.voiceEnabled || !this.speechRecognition) {
            this.addMessage('aura', 'Voice recognition is not available in your browser.', 'error');
            return;
        }

        if (this.state.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    startListening() {
        if (!this.speechRecognition || this.state.isListening) return;

        try {
            this.speechRecognition.start();
        } catch (error) {
            console.error('Failed to start speech recognition:', error);
        }
    }

    stopListening() {
        if (!this.speechRecognition) return;

        try {
            this.speechRecognition.stop();
        } catch (error) {
            // Ignore errors when stopping
        }

        this.state.isListening = false;
        this.elements.voiceOrb.classList.remove('listening');
        this.elements.voiceToggle.classList.remove('active');
        this.elements.orbLabel.textContent = 'Click to speak';
        this.updateVoiceStatus(true, 'VOICE READY');
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || this.state.isProcessing) return;

        // Clear input
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';

        // Add user message
        this.addMessage('user', message);
        this.state.commandCount++;

        // Check for exit commands
        if (['exit', 'quit', 'goodbye', 'stop'].some(cmd => message.toLowerCase().includes(cmd))) {
            this.addMessage('aura', this.getGoodbyeMessage());
            return;
        }

        // Process with AURA
        await this.processWithAura(message);
    }

    async processWithAura(message) {
        this.state.isProcessing = true;
        this.elements.voiceOrb.classList.add('processing');
        this.elements.sendBtn.disabled = true;

        // Show thinking message
        this.addMessage('aura', this.getThinkingMessage(), 'neural');

        try {
            let response;

            // Use WebSocket if connected, otherwise fallback to demo
            if (this.state.backendConnected && this.websocket?.readyState === WebSocket.OPEN) {
                response = await this.sendToBackend(message);
            } else {
                response = await this.simulateAuraResponse(message);
            }

            // Remove thinking message
            this.removeLastMessage();

            // Show code if present
            if (response.code) {
                this.addMessage('aura', 'Neural code generation:', 'neural');
                this.addMessage('aura', '```python\n' + response.code + '\n```', 'code');
            }

            // Add response
            this.addMessage('aura', response.message || response.output, response.type);

            // Speak response if voice is enabled
            if (response.type === 'success') {
                this.speak(this.getSuccessMessage());
            }

        } catch (error) {
            console.error('AURA processing error:', error);
            this.removeLastMessage();
            this.addMessage('aura', `Error processing request: ${error.message}`, 'error');
        } finally {
            this.state.isProcessing = false;
            this.elements.voiceOrb.classList.remove('processing');
            this.elements.sendBtn.disabled = false;
        }
    }

    async sendToBackend(message) {
        return new Promise((resolve, reject) => {
            // Increased timeout to 60s to handle slow LLM calls
            const timeout = setTimeout(() => {
                reject(new Error('Backend response timed out'));
            }, 60000);

            this.pendingResolve = (data) => {
                clearTimeout(timeout);
                if (data.type === 'error') {
                    resolve({ message: data.message, type: 'error' });
                } else {
                    resolve(data);
                }
            };

            this.websocket.send(JSON.stringify({
                type: 'command',
                content: message
            }));
        });
    }

    async simulateAuraResponse(message) {
        // Simulate processing delay
        await new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 1000));

        const lowerMessage = message.toLowerCase();

        // Demo responses based on command type
        if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
            return {
                message: "Hello! I'm AURA, your Advanced Neural Network Interface. How may I assist you today?",
                type: 'success'
            };
        }

        if (lowerMessage.includes('status') || lowerMessage.includes('how are you')) {
            return {
                message: "All neural networks are operational. System diagnostics show optimal performance. Ready to process your commands.",
                type: 'success'
            };
        }

        if (lowerMessage.includes('time')) {
            const now = new Date();
            return {
                message: `The current time is ${now.toLocaleTimeString()} on ${now.toLocaleDateString()}.`,
                type: 'success'
            };
        }

        if (lowerMessage.includes('capabilities') || lowerMessage.includes('what can you do')) {
            return {
                message: `I can assist you with a wide range of tasks:\n\n• **System Automation** - Control Windows settings, open applications\n• **File Operations** - Manage files and folders\n• **Voice Commands** - Speak naturally to give commands\n• **Self-Learning** - I improve and learn new capabilities\n• **Code Execution** - Run Python code safely\n• **And much more...**\n\nJust tell me what you need!`,
                type: 'success'
            };
        }

        // Default response
        return {
            message: `Processing command: "${message}"\n\nNeural networks analyzing request. This would connect to the Python backend for actual execution.\n\n*Note: This is a demo interface. Connect to the Python backend for full functionality.*`,
            type: 'neural'
        };
    }

    addMessage(sender, content, type = 'normal') {
        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender} ${type}`;

        // Parse markdown-like syntax
        const formattedContent = this.formatMessage(content);

        messageDiv.innerHTML = `
            <div class="message-avatar">${sender === 'user' ? 'YOU' : 'AI'}</div>
            <div class="message-content">
                <div class="message-bubble">${formattedContent}</div>
                <div class="message-time">[${timestamp}]</div>
            </div>
        `;

        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(content) {
        // Bold text
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Code blocks
        content = content.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>');

        // Inline code
        content = content.replace(/`(.*?)`/g, '<code>$1</code>');

        // Bullet points
        content = content.replace(/^• (.*)$/gm, '<li>$1</li>');
        content = content.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

        // Line breaks
        content = content.replace(/\n/g, '<br>');

        return content;
    }

    removeLastMessage() {
        const messages = this.elements.chatMessages.children;
        if (messages.length > 0) {
            messages[messages.length - 1].remove();
        }
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    speak(text) {
        if (!this.speechSynthesis || !this.state.voiceEnabled) return;

        // Cancel any ongoing speech
        this.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1;
        utterance.pitch = 1.1;
        utterance.volume = 0.9;

        // Try to find a female voice
        const voices = this.speechSynthesis.getVoices();
        const femaleVoice = voices.find(voice =>
            voice.name.toLowerCase().includes('female') ||
            voice.name.toLowerCase().includes('zira') ||
            voice.name.toLowerCase().includes('samantha') ||
            voice.name.toLowerCase().includes('karen')
        );

        if (femaleVoice) {
            utterance.voice = femaleVoice;
        }

        utterance.onstart = () => {
            this.state.isSpeaking = true;
            this.elements.voiceOrb.classList.add('speaking');
        };

        utterance.onend = () => {
            this.state.isSpeaking = false;
            this.elements.voiceOrb.classList.remove('speaking');
        };

        this.speechSynthesis.speak(utterance);
    }

    showWelcomeMessage() {
        const greeting = this.getGreeting();
        const welcomeMessage = `${greeting}\n\nNeural networks initialized. I am AURA, your Advanced Neural Network Interface.\n\nI can assist you with:\n• System automation and control\n• File operations and data management\n• Voice command processing\n• Self-learning capabilities\n\nClick the orb or use the microphone button to speak, or type your command below.`;

        this.addMessage('aura', welcomeMessage);
        this.speak(greeting);
    }

    clearChat() {
        this.elements.chatMessages.innerHTML = '';
        this.showWelcomeMessage();
    }

    openSettings() {
        this.elements.settingsModal.classList.add('active');

        // Update session info
        const duration = this.getSessionDuration();
        // Update dynamic content in modal if needed
    }

    closeSettings() {
        this.elements.settingsModal.classList.remove('active');
    }

    getSessionDuration() {
        const now = new Date();
        const diff = now - this.state.sessionStart;
        const hours = Math.floor(diff / 3600000);
        const minutes = Math.floor((diff % 3600000) / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    // AURA Personality Messages
    getGreeting() {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning! AURA neural systems online and ready to assist.";
        if (hour < 17) return "Good afternoon! AURA systems operational and at your service.";
        return "Good evening! AURA neural networks activated for your assistance.";
    }

    getThinkingMessage() {
        const messages = [
            "Processing neural pathways...",
            "Analyzing request through neural networks...",
            "Computing optimal solution...",
            "Neural processing in progress...",
            "Engaging cognitive algorithms..."
        ];
        return messages[Math.floor(Math.random() * messages.length)];
    }

    getSuccessMessage() {
        const messages = [
            "Task completed successfully.",
            "Operation executed as requested.",
            "Neural processing complete.",
            "Command successfully processed.",
        ];
        return messages[Math.floor(Math.random() * messages.length)];
    }

    getGoodbyeMessage() {
        return "Goodbye! AURA neural networks entering standby mode. It was a pleasure assisting you today.";
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.auraApp = new AuraApp();
});

// Load voices when available (for speech synthesis)
window.speechSynthesis.onvoiceschanged = () => {
    // Voices are now available
};
