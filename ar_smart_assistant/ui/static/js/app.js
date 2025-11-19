// AR-SmartAssistant Debug UI JavaScript

class DebugUI {
    constructor() {
        this.isRecording = false;
        this.currentSessionId = null;
        this.audioSource = 'microphone';
        this.metricsInterval = null;
        this.transcriptInterval = null;

        this.init();
    }

    init() {
        // Get DOM elements
        this.statusIndicator = document.getElementById('status-indicator');
        this.sessionIdDisplay = document.getElementById('session-id');
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.audioSourceSelect = document.getElementById('audio-source-select');
        this.deviceInfo = document.getElementById('device-info');
        this.transcriptStream = document.getElementById('transcript-stream');
        this.sessionsList = document.getElementById('sessions-list');
        this.memoryReviewPanel = document.getElementById('memory-review-panel');

        // Bind event listeners
        this.startBtn.addEventListener('click', () => this.startSession());
        this.stopBtn.addEventListener('click', () => this.stopSession());
        this.audioSourceSelect.addEventListener('change', (e) => {
            this.audioSource = e.target.value;
            this.updateDeviceInfo();
        });

        document.getElementById('refresh-sessions-btn').addEventListener('click', () => {
            this.loadSessions();
        });

        // Initial load
        this.updateStatus();
        this.loadSessions();
        this.updateDeviceInfo();
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            this.isRecording = data.is_recording;
            this.currentSessionId = data.current_session_id;

            if (this.isRecording) {
                this.statusIndicator.textContent = 'Recording';
                this.statusIndicator.className = 'status-indicator status-recording';
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.audioSourceSelect.disabled = true;

                // Start polling for transcripts and metrics
                this.startLiveUpdates();
            } else {
                this.statusIndicator.textContent = 'Idle';
                this.statusIndicator.className = 'status-indicator status-idle';
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.audioSourceSelect.disabled = false;

                // Stop polling
                this.stopLiveUpdates();
            }

            if (this.currentSessionId) {
                this.sessionIdDisplay.textContent = `Session ID: ${this.currentSessionId}`;
            }

        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    async startSession() {
        try {
            const response = await fetch('/api/session/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    audio_source: this.audioSource
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.showMessage('Session started!', 'success');
                this.updateStatus();
                this.clearTranscripts();
            } else {
                this.showMessage(`Error: ${data.error}`, 'error');
            }

        } catch (error) {
            this.showMessage(`Failed to start session: ${error.message}`, 'error');
        }
    }

    async stopSession() {
        try {
            const response = await fetch('/api/session/stop', {
                method: 'POST'
            });

            const data = await response.json();

            if (response.ok) {
                this.showMessage('Session stopped!', 'success');
                this.updateStatus();
                this.loadSessions();
            } else {
                this.showMessage(`Error: ${data.error}`, 'error');
            }

        } catch (error) {
            this.showMessage(`Failed to stop session: ${error.message}`, 'error');
        }
    }

    startLiveUpdates() {
        // Poll for metrics every second
        this.metricsInterval = setInterval(() => this.updateMetrics(), 1000);

        // Poll for transcripts every 500ms
        this.transcriptInterval = setInterval(() => this.updateTranscripts(), 500);
    }

    stopLiveUpdates() {
        if (this.metricsInterval) {
            clearInterval(this.metricsInterval);
            this.metricsInterval = null;
        }

        if (this.transcriptInterval) {
            clearInterval(this.transcriptInterval);
            this.transcriptInterval = null;
        }
    }

    async updateMetrics() {
        try {
            const response = await fetch('/api/metrics/live');
            const data = await response.json();

            if (data.metrics) {
                document.getElementById('metric-asr').textContent =
                    (data.metrics.asr_confidence || '--');
                document.getElementById('metric-speaker').textContent =
                    (data.metrics.speaker_confidence || '--');
                document.getElementById('metric-queue').textContent =
                    (data.metrics.queue_depth || '--');
                document.getElementById('metric-llm').textContent =
                    (data.metrics.llm_latency_ms || '--');
            }

        } catch (error) {
            console.error('Error updating metrics:', error);
        }
    }

    async updateTranscripts() {
        try {
            const response = await fetch('/api/transcripts/live');
            const data = await response.json();

            if (data.transcripts && data.transcripts.length > 0) {
                this.displayTranscripts(data.transcripts);
            }

        } catch (error) {
            console.error('Error updating transcripts:', error);
        }
    }

    displayTranscripts(transcripts) {
        // Clear empty message if present
        if (this.transcriptStream.querySelector('.empty-message')) {
            this.transcriptStream.innerHTML = '';
        }

        // Add new transcripts
        transcripts.forEach(transcript => {
            const existing = document.querySelector(`[data-transcript-id="${transcript.id}"]`);
            if (!existing) {
                const line = this.createTranscriptLine(transcript);
                this.transcriptStream.appendChild(line);
            }
        });

        // Auto-scroll to bottom
        this.transcriptStream.scrollTop = this.transcriptStream.scrollHeight;

        // Keep only last 100 lines
        const lines = this.transcriptStream.querySelectorAll('.transcript-line');
        if (lines.length > 100) {
            for (let i = 0; i < lines.length - 100; i++) {
                lines[i].remove();
            }
        }
    }

    createTranscriptLine(transcript) {
        const div = document.createElement('div');
        div.className = `transcript-line intent-${transcript.predicted_intent || 'ignore'}`;
        div.setAttribute('data-transcript-id', transcript.id || Math.random());

        const timestamp = new Date(transcript.timestamp).toLocaleTimeString();

        div.innerHTML = `
            <span class="transcript-timestamp">${timestamp}</span>
            <span class="transcript-speaker">${transcript.speaker_id || 'unknown'}:</span>
            <span class="transcript-text">${transcript.transcript || ''}</span>
        `;

        return div;
    }

    clearTranscripts() {
        this.transcriptStream.innerHTML = '<p class="empty-message">Recording in progress...</p>';
    }

    async loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            const data = await response.json();

            if (data.sessions) {
                this.displaySessions(data.sessions);
            }

        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    displaySessions(sessions) {
        if (sessions.length === 0) {
            this.sessionsList.innerHTML = '<p class="empty-message">No sessions yet</p>';
            return;
        }

        this.sessionsList.innerHTML = '';

        sessions.forEach(session => {
            const item = this.createSessionItem(session);
            this.sessionsList.appendChild(item);
        });
    }

    createSessionItem(session) {
        const div = document.createElement('div');
        div.className = 'session-item';
        div.addEventListener('click', () => this.loadSessionMemories(session.id));

        const startTime = new Date(session.start_time).toLocaleString();
        const statusClass = session.status.replace('_', '-');

        div.innerHTML = `
            <div class="session-item-header">
                <span class="session-id">Session ${session.id}</span>
                <span class="session-status ${statusClass}">${session.status}</span>
            </div>
            <div class="session-time">${startTime}</div>
        `;

        return div;
    }

    async loadSessionMemories(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}/memories`);
            const data = await response.json();

            if (data.memories) {
                this.displayMemories(sessionId, data.memories);
            }

        } catch (error) {
            console.error('Error loading memories:', error);
        }
    }

    displayMemories(sessionId, memories) {
        const panel = this.memoryReviewPanel;
        panel.classList.remove('hidden');

        document.getElementById('review-session-id').textContent = sessionId;

        const container = document.getElementById('memories-list');

        if (memories.length === 0) {
            container.innerHTML = '<p class="empty-message">No memories for this session</p>';
            return;
        }

        container.innerHTML = '';

        memories.forEach(memory => {
            const item = this.createMemoryItem(memory);
            container.appendChild(item);
        });

        // Scroll to review panel
        panel.scrollIntoView({ behavior: 'smooth' });
    }

    createMemoryItem(memory) {
        const div = document.createElement('div');
        div.className = 'memory-item';

        const tags = memory.topic_tags || [];
        const tagsHtml = tags.map(tag => `<span class="tag">${tag}</span>`).join('');

        const confidence = Math.round((memory.confidence_llm || 0) * 100);

        div.innerHTML = `
            <div class="memory-header">
                <strong>Memory #${memory.id}</strong>
                <span class="session-status ${memory.approval_status}">${memory.approval_status}</span>
            </div>
            <div class="memory-text">${memory.text}</div>
            <div class="memory-meta">
                <span>Intent: ${memory.predicted_intent || 'unknown'}</span>
                <span>Importance: ${memory.importance || 'N/A'}</span>
                <span>Confidence: ${confidence}%</span>
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: ${confidence}%"></div>
            </div>
            <div class="memory-tags">${tagsHtml}</div>
            <div class="memory-actions">
                <button class="btn btn-approve" data-memory-id="${memory.id}">Approve</button>
                <button class="btn btn-reject" data-memory-id="${memory.id}">Reject</button>
            </div>
        `;

        // Add event listeners for approve/reject buttons
        div.querySelector('.btn-approve').addEventListener('click', () => {
            this.approveMemory(memory.id);
        });

        div.querySelector('.btn-reject').addEventListener('click', () => {
            this.rejectMemory(memory.id);
        });

        return div;
    }

    async approveMemory(memoryId) {
        try {
            const response = await fetch(`/api/memories/${memoryId}/approve`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showMessage('Memory approved!', 'success');
                // Reload current session memories
                const sessionId = document.getElementById('review-session-id').textContent;
                this.loadSessionMemories(sessionId);
            }

        } catch (error) {
            this.showMessage(`Error approving memory: ${error.message}`, 'error');
        }
    }

    async rejectMemory(memoryId) {
        const reason = prompt('Why are you rejecting this memory?');

        if (reason === null) return; // User cancelled

        try {
            const response = await fetch(`/api/memories/${memoryId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ reason })
            });

            if (response.ok) {
                this.showMessage('Memory rejected!', 'success');
                // Reload current session memories
                const sessionId = document.getElementById('review-session-id').textContent;
                this.loadSessionMemories(sessionId);
            }

        } catch (error) {
            this.showMessage(`Error rejecting memory: ${error.message}`, 'error');
        }
    }

    async updateDeviceInfo() {
        if (this.audioSource === 'microphone') {
            try {
                const response = await fetch('/api/devices/audio');
                const data = await response.json();

                if (data.devices && data.devices.length > 0) {
                    const deviceList = data.devices
                        .map(d => `${d.name} (${d.sample_rate}Hz)`)
                        .join(', ');
                    this.deviceInfo.textContent = `Available devices: ${deviceList}`;
                } else {
                    this.deviceInfo.textContent = 'No audio input devices found!';
                }

            } catch (error) {
                this.deviceInfo.textContent = 'Error loading audio devices';
            }

        } else {
            this.deviceInfo.textContent = 'Waiting for WebSocket connection from Glass/Phone...';
        }
    }

    showMessage(message, type = 'info') {
        // Simple alert for now - could be enhanced with toast notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    }
}

// Initialize the UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const ui = new DebugUI();

    // Status check every 2 seconds
    setInterval(() => ui.updateStatus(), 2000);
});
