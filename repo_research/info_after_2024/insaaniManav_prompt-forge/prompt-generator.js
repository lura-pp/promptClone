// Prompt Generator State
const PromptGeneratorState = {
    conversation: [],
    isConversationActive: false,
    currentConversationId: null,
    systemPrompt: `You are a professional prompt engineer. Optimize prompts for AI systems through iterative refinement.

Process:
1. Analyze the user's prompt objective and requirements
2. Generate two sections:
   a. Revised prompt: Clear, optimized version
   b. Questions: Specific clarifications needed for further improvement
3. Continue refinement until the prompt meets professional standards

Focus on clarity, specificity, and effectiveness.`
};

// Generate unique conversation ID
function generateConversationId() {
    return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Save conversation to database
async function saveConversation() {
    if (!PromptGeneratorState.currentConversationId || PromptGeneratorState.conversation.length === 0) {
        return;
    }

    try {
        // Generate title from first user message
        const firstUserMessage = PromptGeneratorState.conversation.find(msg => msg.role === 'user');
        const title = firstUserMessage ? 
            firstUserMessage.content.substring(0, 50) + (firstUserMessage.content.length > 50 ? '...' : '') :
            'New Conversation';

        const response = await fetch(`${AppState.API_BASE}/conversations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: PromptGeneratorState.currentConversationId,
                title: title,
                messages: PromptGeneratorState.conversation.map(msg => ({
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.timestamp
                }))
            })
        });

        if (!response.ok) {
            console.error('Failed to save conversation:', response.status);
        }
    } catch (error) {
        console.error('Error saving conversation:', error);
    }
}

// Load conversation from database
async function loadConversation(conversationId) {
    try {
        const response = await fetch(`${AppState.API_BASE}/conversations/${conversationId}`);
        const data = await response.json();

        if (data.success && data.data) {
            PromptGeneratorState.conversation = data.data.messages || [];
            PromptGeneratorState.currentConversationId = conversationId;
            PromptGeneratorState.isConversationActive = true;
            
            // Show input area and render conversation
            document.getElementById('conversation-input-area').style.display = 'block';
            renderConversation();
            
            return true;
        }
    } catch (error) {
        console.error('Error loading conversation:', error);
    }
    return false;
}

// Load last conversation on page load
async function loadLastConversation() {
    const savedConversationId = localStorage.getItem('currentConversationId');
    if (savedConversationId) {
        const loaded = await loadConversation(savedConversationId);
        if (loaded) {
            return;
        }
    }
    
    // If no saved conversation or failed to load, show welcome screen
    clearConversation();
}



// Initialize conversation
function startNewConversation() {
    PromptGeneratorState.conversation = [];
    PromptGeneratorState.isConversationActive = true;
    PromptGeneratorState.currentConversationId = generateConversationId();
    
    // Save current conversation ID to localStorage
    localStorage.setItem('currentConversationId', PromptGeneratorState.currentConversationId);
    
    // Show input area and hide welcome
    document.getElementById('conversation-input-area').style.display = 'block';
    
    // Add initial AI message
    const initialMessage = {
        role: 'assistant',
        content: "**Prompt Engineering Session**\n\nDefine your prompt objective and target use case to begin optimization.",
        timestamp: new Date()
    };
    
    PromptGeneratorState.conversation.push(initialMessage);
    renderConversation();
    
    // Save initial conversation
    saveConversation();
    
    // Focus on input
    document.getElementById('conversation-input').focus();
}

// Clear conversation
function clearConversation() {
    PromptGeneratorState.conversation = [];
    PromptGeneratorState.isConversationActive = false;
    PromptGeneratorState.currentConversationId = null;
    
    // Clear localStorage
    localStorage.removeItem('currentConversationId');
    
    // Hide input area and show welcome
    document.getElementById('conversation-input-area').style.display = 'none';
    
    // Show welcome screen
    const conversationArea = document.getElementById('conversation-area');
    conversationArea.innerHTML = `
        <div class="conversation-welcome">
            <button class="action-btn" onclick="startNewConversation()">Generate a new prompt</button>
        </div>
    `;
}

// Send message
async function sendMessage() {
    const input = document.getElementById('conversation-input');
    const sendBtn = document.getElementById('send-btn');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to conversation
    const userMessage = {
        role: 'user',
        content: message,
        timestamp: new Date()
    };
    
    PromptGeneratorState.conversation.push(userMessage);
    
    // Clear input and disable send button
    input.value = '';
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span>Thinking...';
    
    // Render conversation
    renderConversation();
    
    // Save conversation after adding user message
    saveConversation();
    
    try {
        // Prepare messages for API
        const messages = [
            { role: 'system', content: PromptGeneratorState.systemPrompt },
            ...PromptGeneratorState.conversation.map(msg => ({
                role: msg.role,
                content: msg.content
            }))
        ];
        
        // Call API
        const response = await fetch(`${AppState.API_BASE}/prompt-engineer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: messages,
                model: 'o3',
                temperature: 0.7
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Add AI response to conversation
            const aiMessage = {
                role: 'assistant',
                content: data.data,
                timestamp: new Date()
            };
            
            PromptGeneratorState.conversation.push(aiMessage);
            renderConversation();
            
            // Save conversation to database
            saveConversation();
        } else {
            // Handle error
            showErrorMessage(data.error || 'Failed to get response from AI');
        }
    } catch (error) {
        showErrorMessage('Network error: ' + error.message);
    } finally {
        // Re-enable send button
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<span>Send</span>';
        input.focus();
    }
}

// Render conversation
function renderConversation() {
    const conversationArea = document.getElementById('conversation-area');
    
    if (PromptGeneratorState.conversation.length === 0) {
        clearConversation();
        return;
    }
    
    let html = '';
    
    PromptGeneratorState.conversation.forEach((message, index) => {
        if (message.role === 'user') {
            html += `
                <div class="conversation-message">
                    <div class="message-user">${escapeHtml(message.content)}</div>
                </div>
            `;
        } else {
            // Parse AI message for revised prompt and questions
            const parsedMessage = parseAIMessage(message.content);
            html += `
                <div class="conversation-message">
                    <div class="message-ai">
                        ${parsedMessage.html}
                    </div>
                </div>
            `;
        }
    });
    
    conversationArea.innerHTML = html;
    
    // Scroll to bottom
    conversationArea.scrollTop = conversationArea.scrollHeight;
}

// Parse AI message to extract revised prompt and questions
function parseAIMessage(content) {
    let html = '';
    let revisedPrompt = '';
    let questions = '';
    
    // Try to extract revised prompt section
    const revisedPromptMatch = content.match(/(?:^|\n)\s*(?:a\.|a\)|\*\*a\.\*\*|\*\*Revised prompt:?\*\*|Revised prompt:?)\s*([\s\S]*?)(?=\n\s*(?:b\.|b\)|\*\*b\.\*\*|\*\*Questions:?\*\*|Questions:?)|$)/i);
    if (revisedPromptMatch) {
        revisedPrompt = revisedPromptMatch[1].trim();
    }
    
    // Try to extract questions section
    const questionsMatch = content.match(/(?:^|\n)\s*(?:b\.|b\)|\*\*b\.\*\*|\*\*Questions:?\*\*|Questions:?)\s*([\s\S]*?)$/i);
    if (questionsMatch) {
        questions = questionsMatch[1].trim();
    }
    
    // If we found structured content, format it nicely
    if (revisedPrompt || questions) {
        // Add any content before the structured sections
        const beforeMatch = content.match(/^([\s\S]*?)(?=\n\s*(?:a\.|a\)|\*\*a\.\*\*|\*\*Revised prompt:?\*\*|Revised prompt:?))/i);
        if (beforeMatch && beforeMatch[1].trim()) {
            html += `<div>${markdownToHtml(beforeMatch[1].trim())}</div>`;
        }
        
        // Add revised prompt section
        if (revisedPrompt) {
            const promptId = 'prompt-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            html += `
                <div class="revised-prompt" id="${promptId}">
                    <button class="copy-prompt-btn" onclick="copyRevisedPrompt('${promptId}')">Copy</button>
                    ${escapeHtml(revisedPrompt)}
                </div>
            `;
        }
        
        // Add questions section
        if (questions) {
            html += `
                <div class="questions">
                    <h5>Questions for refinement:</h5>
                    ${markdownToHtml(questions)}
                </div>
            `;
        }
    } else {
        // No structured format found, just render as markdown
        html = markdownToHtml(content);
    }
    
    return { html, revisedPrompt, questions };
}

// Copy revised prompt to main editor
function copyRevisedPrompt(promptId) {
    const promptElement = document.getElementById(promptId);
    if (promptElement) {
        const promptText = promptElement.textContent.replace('Copy', '').trim();
        const mainPromptTextarea = document.getElementById('main-prompt');
        if (mainPromptTextarea) {
            mainPromptTextarea.value = promptText;
            // Trigger token count update
            if (typeof tokenCounter !== 'undefined') {
                tokenCounter.updateCount(promptText);
            }
            // Update line numbers
            if (typeof updateLineNumbers === 'function') {
                updateLineNumbers();
            }
            // Show success feedback
            const btn = promptElement.querySelector('.copy-prompt-btn');
            if (btn) {
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                btn.style.background = '#4caf50';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '#007acc';
                }, 2000);
            }
        }
    }
}

// Show error message in conversation
function showErrorMessage(error) {
    const errorMessage = {
        role: 'assistant',
        content: `⚠️ **Error**: ${error}\n\nRetry or refresh if the issue persists.`,
        timestamp: new Date()
    };
    
    PromptGeneratorState.conversation.push(errorMessage);
    renderConversation();
}

// This is now handled in the new combined DOMContentLoaded listener above

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Toggle prompt generator collapse state
function togglePromptGenerator() {
    const panel = document.getElementById('prompt-generator-panel');
    const icon = document.getElementById('collapse-icon');
    
    if (panel.classList.contains('collapsed')) {
        // Expand
        panel.classList.remove('collapsed');
        icon.textContent = '▼';
        // Save state
        localStorage.setItem('promptGeneratorCollapsed', 'false');
    } else {
        // Collapse
        panel.classList.add('collapsed');
        icon.textContent = '▶';
        // Save state
        localStorage.setItem('promptGeneratorCollapsed', 'true');
    }
}

// Initialize collapse state from localStorage
function initializeCollapseState() {
    const isCollapsed = localStorage.getItem('promptGeneratorCollapsed') === 'true';
    const panel = document.getElementById('prompt-generator-panel');
    const icon = document.getElementById('collapse-icon');
    
    if (isCollapsed) {
        panel.classList.add('collapsed');
        icon.textContent = '▶';
    } else {
        panel.classList.remove('collapsed');
        icon.textContent = '▼';
    }
}

// Initialize collapse state when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeCollapseState();
    
    const conversationInput = document.getElementById('conversation-input');
    if (conversationInput) {
        conversationInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Load last conversation if available
    loadLastConversation();
});

// Conversation History Functions
async function toggleConversationHistory() {
    console.log('toggleConversationHistory called'); // Debug log
    const historyPanel = document.getElementById('conversation-history-panel');
    const conversationArea = document.getElementById('conversation-area');
    
    console.log('historyPanel:', historyPanel); // Debug log
    console.log('conversationArea:', conversationArea); // Debug log
    
    if (historyPanel.style.display === 'none' || historyPanel.style.display === '') {
        // Show history panel
        historyPanel.style.display = 'block';
        conversationArea.style.display = 'none';
        await loadConversationHistory();
    } else {
        // Hide history panel
        hideConversationHistory();
    }
}

function hideConversationHistory() {
    const historyPanel = document.getElementById('conversation-history-panel');
    const conversationArea = document.getElementById('conversation-area');
    
    historyPanel.style.display = 'none';
    conversationArea.style.display = 'block';
}

async function loadConversationHistory() {
    console.log('loadConversationHistory called'); // Debug log
    const historyList = document.getElementById('history-list');
    historyList.innerHTML = '<div class="loading">Loading conversations...</div>';
    
    try {
        console.log('Fetching conversations from:', `${AppState.API_BASE}/conversations`); // Debug log
        const response = await fetch(`${AppState.API_BASE}/conversations`);
        const data = await response.json();
        
        console.log('Conversation data received:', data); // Debug log
        
        if (data.success) {
            if (data.data && data.data.length > 0) {
                renderConversationHistory(data.data);
            } else {
                historyList.innerHTML = '<div class="no-conversations">No conversations found. Start a new conversation to see it here.</div>';
            }
        } else {
            historyList.innerHTML = '<div class="loading">Error loading conversations</div>';
        }
    } catch (error) {
        console.error('Error loading conversation history:', error);
        historyList.innerHTML = '<div class="loading">Error loading conversations</div>';
    }
}

function renderConversationHistory(conversations) {
    const historyList = document.getElementById('history-list');
    
    let html = '';
    conversations.forEach(conversation => {
        const isActive = conversation.id === PromptGeneratorState.currentConversationId;
        const date = new Date(conversation.updated_at).toLocaleDateString();
        const time = new Date(conversation.updated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        html += `
            <div class="history-conversation-item ${isActive ? 'active' : ''}" onclick="loadHistoryConversation('${conversation.id}')">
                <div class="conversation-title">${escapeHtml(conversation.title)}</div>
                <div class="conversation-meta">
                    <span class="conversation-date">${date} ${time}</span>
                    <div class="conversation-actions">
                        <button class="delete-conversation-btn" onclick="event.stopPropagation(); deleteHistoryConversation('${conversation.id}')">Delete</button>
                    </div>
                </div>
            </div>
        `;
    });
    
    historyList.innerHTML = html;
}

async function loadHistoryConversation(conversationId) {
    try {
        const success = await loadConversation(conversationId);
        if (success) {
            // Update localStorage with new current conversation
            localStorage.setItem('currentConversationId', conversationId);
            
            // Hide history panel and show conversation
            hideConversationHistory();
            
            // Refresh history to update active state
            await loadConversationHistory();
        } else {
            showErrorMessage('Failed to load conversation');
        }
    } catch (error) {
        console.error('Error loading conversation:', error);
        showErrorMessage('Error loading conversation');
    }
}

async function deleteHistoryConversation(conversationId) {
    if (!confirm('Are you sure you want to delete this conversation?')) {
        return;
    }
    
    try {
        const response = await fetch(`${AppState.API_BASE}/conversations/${conversationId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // If we're deleting the current conversation, clear it
            if (conversationId === PromptGeneratorState.currentConversationId) {
                clearConversation();
            }
            
            // Reload conversation history
            await loadConversationHistory();
        } else {
            showErrorMessage('Failed to delete conversation');
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        showErrorMessage('Error deleting conversation');
    }
}

// Make functions available globally for onclick handlers (at the end after all functions are defined)
console.log('Assigning toggleConversationHistory to window:', typeof toggleConversationHistory);
window.toggleConversationHistory = toggleConversationHistory;
window.loadConversationHistory = loadConversationHistory;
window.hideConversationHistory = hideConversationHistory;
window.loadHistoryConversation = loadHistoryConversation;
window.deleteHistoryConversation = deleteHistoryConversation;
console.log('window.toggleConversationHistory assigned:', typeof window.toggleConversationHistory);

// Test function to verify JavaScript is working
function testHistoryButton() {
    alert('History button is working! JavaScript is loaded correctly.');
    toggleConversationHistory();
} 