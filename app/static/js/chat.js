// Chat interface JavaScript
let sessionId = null;

function initChat() {
    // Load conversation history if session exists
    loadConversationHistory();
    
    // Set up form submission
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        // Display user message
        appendMessage('user', message);
        messageInput.value = '';
        
        // Show loading indicator
        showLoading(true);
        
        try {
            // Send message to API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Update session ID
                sessionId = data.session_id;
                
                // Display assistant response
                appendMessage('assistant', data.response);
            } else {
                appendMessage('assistant', `Error: ${data.detail || 'Failed to get response'}`);
            }
        } catch (error) {
            appendMessage('assistant', `Error: ${error.message}`);
        } finally {
            showLoading(false);
        }
    });
}

function appendMessage(role, content) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showLoading(show) {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (show) {
        loadingIndicator.style.display = 'block';
    } else {
        loadingIndicator.style.display = 'none';
    }
}

async function loadConversationHistory() {
    // Load conversation history from API
    // Note: Agno manages conversation history internally via session_id
    // We can load session list, but individual messages are managed by Agno
    try {
        const response = await fetch('/api/chat/sessions');
        const data = await response.json();
        
        if (data.sessions && data.sessions.length > 0) {
            // Use the most recent session if available
            const mostRecentSession = data.sessions[0];
            if (mostRecentSession && mostRecentSession.session_id) {
                sessionId = mostRecentSession.session_id;
                // Note: Individual messages are loaded automatically by Agno
                // when we send a message with the same session_id
                console.log('Loaded session:', sessionId);
            }
        }
    } catch (error) {
        console.error('Failed to load conversation history:', error);
        // Don't fail if we can't load history - start a new session
    }
}
