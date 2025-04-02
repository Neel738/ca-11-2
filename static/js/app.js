document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const micButton = document.getElementById('mic-button');
    const micText = document.getElementById('mic-text');
    const statusText = document.getElementById('status-text');
    const statusIndicator = document.getElementById('status-indicator');
    const messagesContainer = document.getElementById('messages');
    const chatContainer = document.getElementById('chat-container');
    const processingOverlay = document.getElementById('processing-overlay');
    const debugPanel = document.getElementById('debug-panel');
    const debugToggle = document.getElementById('debug-toggle');
    const sessionId = document.getElementById('session-id').textContent;
    const statusBadge = document.getElementById('status-badge');
    
    // App state
    let isRecording = false;
    let isProcessing = false;
    let socket = null;
    let audioContext = null;
    let audioStream = null;
    let processorNode = null;
    let reconnectAttempts = 0;
    let debugVisible = false;
    let thinkingMessageElement = null;
    let currentTranscriptionMessage = null;
    let isThinking = false;
    let currentStatus = 'ready';
    
    // Initialize debug panel toggle
    debugToggle.addEventListener('click', () => {
        debugVisible = !debugVisible;
        debugPanel.style.display = debugVisible ? 'block' : 'none';
        debugToggle.textContent = debugVisible ? 'Hide Debug Info' : 'Show Debug Info';
    });
    
    // Initialize with debug panel hidden by default
    debugVisible = false;
    debugPanel.style.display = 'none';
    debugToggle.textContent = 'Show Debug Info';
    
    // Add debug info to panel
    function addDebugInfo(event, data) {
        const debugEntry = document.createElement('div');
        debugEntry.classList.add('debug-entry');
        
        const time = new Date().toLocaleTimeString();
        const debugTime = document.createElement('span');
        debugTime.classList.add('debug-time');
        debugTime.textContent = `[${time}] `;
        
        const debugEvent = document.createElement('span');
        debugEvent.classList.add('debug-event');
        debugEvent.textContent = event + ': ';
        
        debugEntry.appendChild(debugTime);
        debugEntry.appendChild(debugEvent);
        debugEntry.appendChild(document.createTextNode(JSON.stringify(data)));
        
        debugPanel.appendChild(debugEntry);
        debugPanel.scrollTop = debugPanel.scrollHeight;
    }
    
    // Show thinking message in chat
    function showThinkingMessage() {
        console.log('Showing thinking message');
        // If there's already a thinking message, don't add another one
        if (thinkingMessageElement) {
            console.log('Thinking message already exists, not creating another one');
            return;
        }
        
        thinkingMessageElement = document.createElement('div');
        thinkingMessageElement.classList.add('message', 'assistant-message', 'thinking-message');
        
        const thinkingText = document.createElement('div');
        thinkingText.classList.add('thinking-text');
        thinkingText.textContent = "THINKING... GENERATING RESPONSE...";
        thinkingText.style.fontWeight = "bold";
        thinkingText.style.color = "#0066cc";
        
        const thinkingDots = document.createElement('div');
        thinkingDots.classList.add('thinking-dots');
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            dot.classList.add('dot');
            dot.style.backgroundColor = "#0066cc";
            dot.style.width = "12px";
            dot.style.height = "12px";
            thinkingDots.appendChild(dot);
        }
        
        thinkingMessageElement.appendChild(thinkingText);
        thinkingMessageElement.appendChild(thinkingDots);
        
        messagesContainer.appendChild(thinkingMessageElement);
        scrollToBottom();
    }
    
    // Remove thinking message
    function removeThinkingMessage() {
        console.log('Removing thinking message');
        if (thinkingMessageElement && thinkingMessageElement.parentNode) {
            thinkingMessageElement.parentNode.removeChild(thinkingMessageElement);
            thinkingMessageElement = null;
        }
    }
    
    // Connect to WebSocket server
    function connectSocket() {
        // Get the current host
        const host = window.location.host;
        socket = io(`http://${host}`);
        
        socket.on('connect', () => {
            console.log('Connected to server');
            addDebugInfo('connect', { status: 'connected' });
            updateStatus('ready', 'Ready to listen');
            reconnectAttempts = 0;
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            addDebugInfo('disconnect', { status: 'disconnected' });
            updateStatus('error', 'Disconnected');
            stopRecording();
            
            // Try to reconnect
            if (reconnectAttempts < 5) {
                setTimeout(() => {
                    reconnectAttempts++;
                    console.log(`Attempting to reconnect (${reconnectAttempts}/5)...`);
                    socket.connect();
                }, 2000);
            }
        });
        
        socket.on('status', (data) => {
            console.log('Received status:', data);
            addDebugInfo('status', data);
            
            if (data.status === 'listening') {
                updateStatus('listening', 'Processing audio...');
                isProcessing = false;
                micButton.disabled = false;
                processingOverlay.classList.remove('active');
            } else if (data.status === 'processing') {
                updateStatus('processing', 'Processing response...');
                isProcessing = true;
                micButton.disabled = true;
                processingOverlay.classList.add('active');
            } else if (data.status === 'transcribing') {
                updateStatus('transcribing', 'Converting speech to text...');
                isProcessing = true;
                micButton.disabled = true;
                processingOverlay.classList.add('active');
            } else if (data.status === 'thinking') {
                console.log('Setting thinking status from status event');
                updateStatus('thinking', 'Generating response...');
                isProcessing = true;
                isThinking = true;
                micButton.disabled = true;
                processingOverlay.classList.add('active');
                
                // Force status badge update for thinking - with emphasized styling
                console.log('FORCE UPDATING STATUS BADGE TO THINKING');
                statusBadge.textContent = 'GENERATING RESPONSE';
                statusBadge.classList.remove('listening', 'transcribing', 'processing', 'error');
                statusBadge.classList.add('thinking');
            } else if (data.status === 'ready') {
                updateStatus('ready', 'Ready to listen');
                isProcessing = false;
                micButton.disabled = false;
                processingOverlay.classList.remove('active');
                
                // Force status badge update for ready state
                statusBadge.textContent = 'Ready';
                statusBadge.classList.remove('listening', 'transcribing', 'thinking', 'processing', 'error');
                
                // Re-enable microphone after processing if it was active before
                if (!isRecording && micButton.classList.contains('muted')) {
                    startRecording();
                }
            }
        });
        
        socket.on('transcription', (data) => {
            addDebugInfo('transcription', data);
            
            if (data.text && data.text.trim() !== '') {
                // Handle streaming transcription updates
                if (!data.final) {
                    // For non-final transcriptions, update existing message or create a new one
                    if (!currentTranscriptionMessage) {
                        currentTranscriptionMessage = document.createElement('div');
                        currentTranscriptionMessage.classList.add('message', 'user-message', 'pending');
                        currentTranscriptionMessage.textContent = data.text;
                        messagesContainer.appendChild(currentTranscriptionMessage);
                    } else {
                        currentTranscriptionMessage.textContent = data.text;
                    }
                } else {
                    // For final transcriptions, update the style
                    if (currentTranscriptionMessage) {
                        currentTranscriptionMessage.classList.remove('pending');
                        currentTranscriptionMessage.textContent = data.text;
                    } else {
                        addMessage(data.text, 'user-message');
                    }
                    currentTranscriptionMessage = null;
                }
                scrollToBottom();
            }
        });
        
        socket.on('thinking', (data) => {
            console.log('Received thinking event:', data);
            addDebugInfo('thinking', data);
            
            if (data.status === 'started') {
                console.log('Thinking started');
                updateStatus('thinking', 'Generating response...');
                // Force status badge update for thinking
                statusBadge.textContent = 'GENERATING RESPONSE';
                statusBadge.classList.remove('listening', 'transcribing', 'processing', 'error');
                statusBadge.classList.add('thinking');
                showThinkingMessage();
            } else if (data.status === 'ended') {
                console.log('Thinking ended');
                removeThinkingMessage();
                isThinking = false;
            }
        });
        
        socket.on('assistant_response', (data) => {
            addDebugInfo('assistant_response', data);
            
            // Remove the thinking message before adding the actual response
            removeThinkingMessage();
            
            if (data.text && data.text.trim() !== '') {
                addMessage(data.text, 'assistant-message');
                scrollToBottom();
            }
        });

        socket.on('tts_audio', (data) => {
            console.log('Received tts_audio event', data);
            // Create a Blob from the binary data (assuming WAV format)
            const blob = new Blob([data], { type: 'audio/wav' });
            const url = URL.createObjectURL(blob);
            const audioElement = new Audio(url);
            audioElement.play().catch(err => console.error("Audio playback error:", err));
        });
        
        socket.on('debug', (data) => {
            addDebugInfo(data.event, data);
        });
        
        socket.on('error', (data) => {
            console.error('Server error:', data.message);
            addDebugInfo('error', data);
            
            // Remove thinking message on error
            removeThinkingMessage();
            isThinking = false;
            
            updateStatus('error', 'Error: ' + data.message);
            isProcessing = false;
            micButton.disabled = false;
            processingOverlay.classList.remove('active');
            
            setTimeout(() => {
                updateStatus('ready', 'Ready to listen');
            }, 3000);
        });
    }
    
    // Update UI status
    function updateStatus(status, message) {
        console.log(`Status update: ${status} - ${message}`);
        
        // Update the status text
        statusText.textContent = message;
        
        // Update the current status
        currentStatus = status;
        
        // Update the prominent status badge
        updateStatusBadge(status);
        
        // Remove all status classes
        statusIndicator.parentElement.classList.remove('listening', 'processing', 'thinking', 'error');
        
        if (status !== 'ready') {
            statusIndicator.parentElement.classList.add(status);
            console.log(`Added class ${status} to status indicator`);
        }
    }
    
    // Update the prominent status badge
    function updateStatusBadge(status) {
        console.log(`Updating status badge to: ${status}`);
        
        // Remove all status classes
        statusBadge.classList.remove('listening', 'transcribing', 'thinking', 'processing', 'error');
        
        // Add the appropriate class
        if (status !== 'ready') {
            statusBadge.classList.add(status);
        }
        
        // Update the text
        let badgeText = 'Ready';
        
        switch (status) {
            case 'listening':
                badgeText = 'Processing Audio';
                break;
            case 'transcribing':
                badgeText = 'Transcribing';
                break;
            case 'thinking':
                badgeText = 'GENERATING RESPONSE';
                break;
            case 'processing':
                badgeText = 'Processing';
                break;
            case 'error':
                badgeText = 'Error';
                break;
        }
        
        statusBadge.textContent = badgeText;
    }
    
    // Add a message to the chat
    function addMessage(text, type) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', type);
        messageElement.textContent = text;
        messagesContainer.appendChild(messageElement);
        
        // Scroll to bottom
        scrollToBottom();
    }
    
    // Scroll chat to bottom
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Start recording audio
    async function startRecording() {
        if (isRecording || isProcessing) return;
        
        try {
            // Request microphone access
            audioStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // Create audio context
            audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            
            const source = audioContext.createMediaStreamSource(audioStream);
            
            // Create script processor node to process audio data
            processorNode = audioContext.createScriptProcessor(4096, 1, 1);
            
            processorNode.onaudioprocess = (e) => {
                if (!isRecording) return;
                
                // Convert audio data to Float32Array
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Skip sending if socket is not connected
                if (!socket || !socket.connected) {
                    return;
                }
                
                // Only send if there's actual audio data (not silence)
                const energy = Math.sqrt(inputData.reduce((acc, val) => acc + val * val, 0) / inputData.length);
                if (energy > 0.001) {
                    socket.emit('audio_data', inputData);
                }
            };
            
            // Connect nodes
            source.connect(processorNode);
            processorNode.connect(audioContext.destination);
            
            // Update UI
            isRecording = true;
            micButton.classList.add('muted');
            micText.textContent = 'Stop';
            updateStatus('listening', 'Processing audio...');
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            addDebugInfo('mic_error', { error: error.name, message: error.message });
            
            let errorMessage = 'Microphone access denied';
            
            if (error.name === 'NotAllowedError') {
                errorMessage = 'Microphone permission denied. Please allow microphone access in your browser settings.';
            } else if (error.name === 'NotFoundError') {
                errorMessage = 'No microphone found. Please connect a microphone and try again.';
            }
            
            updateStatus('error', errorMessage);
        }
    }
    
    // Stop recording audio
    function stopRecording() {
        if (!isRecording) return;
        
        // Stop all audio tracks
        if (audioStream) {
            audioStream.getTracks().forEach(track => track.stop());
        }
        
        // Disconnect processor node
        if (processorNode) {
            processorNode.disconnect();
            processorNode = null;
        }
        
        // Close audio context
        if (audioContext) {
            if (audioContext.state !== 'closed') {
                audioContext.close().catch(err => console.error('Error closing audio context:', err));
            }
        }
        
        // Update UI
        isRecording = false;
        micButton.classList.remove('muted');
        micText.textContent = 'Talk';
        if (!isProcessing) {
            updateStatus('ready', 'Ready to listen');
        }
    }
    
    // Toggle recording state
    function toggleRecording() {
        if (isProcessing) return; // Don't allow toggle while processing
        
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    // Event listeners
    micButton.addEventListener('click', toggleRecording);
    
    // Initialize socket connection
    connectSocket();
    
    // Initial scroll to bottom to show welcome message
    scrollToBottom();
    
    // Initial debug info
    addDebugInfo('init', { session_id: sessionId });
    
    // Handle page unload to clean up resources
    window.addEventListener('beforeunload', () => {
        stopRecording();
        if (socket) {
            socket.disconnect();
        }
    });
}); 