// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    const chatButton = document.getElementById('chatButton');
    const chatPopup = document.getElementById('chatPopup');
    const closeButton = document.getElementById('closeButton');
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');

    // API Configuration
    const API_URL = '/chat';

    // Event Listeners
    chatButton.addEventListener('click', toggleChat);
    closeButton.addEventListener('click', toggleChat);
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    // Toggle chat popup visibility
    function toggleChat() {
        if (chatPopup.classList.contains('hidden')) {
            // Show chat popup
            chatPopup.classList.remove('hidden');
            setTimeout(() => {
                userInput.focus();
            }, 100);
        } else {
            // Hide chat popup
            chatPopup.classList.add('hidden');
        }
    }

    // Send message function
    async function sendMessage() {
        const userMessage = userInput.value.trim();

        if (userMessage === '') {
            return; // Don't send empty messages
        }

        // Display user message
        addMessageToChatbox(userMessage, 'user');
        userInput.value = ''; // Clear input field

        // Show thinking indicator
        const thinkingElement = addThinkingIndicator();

        try {
            // Send message to API
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: userMessage }),
            });

            // Remove thinking indicator
            if (chatbox.contains(thinkingElement)) {
                chatbox.removeChild(thinkingElement);
            }

            if (!response.ok) {
                // Handle HTTP errors
                const errorData = await response.json().catch(() => ({ 
                    error: `HTTP error! Status: ${response.status}` 
                }));
                console.error('API Error:', errorData);
                addMessageToChatbox(`Error: ${errorData.error || response.statusText}`, 'error');
                return;
            }

            // Parse and handle response
            const data = await response.json();

            if (data && data.reply) {
                addMessageToChatbox(data.reply, 'bot');
            } else {
                addMessageToChatbox('Received an empty or invalid response.', 'error');
            }

        } catch (error) {
            // Remove thinking indicator on error
            if (chatbox.contains(thinkingElement)) {
                chatbox.removeChild(thinkingElement);
            }
            
            console.error('Fetch Error:', error);
            addMessageToChatbox(`Connection error. Please try again later.`, 'error');
        }
    }

    // Add thinking indicator
    function addThinkingIndicator() {
        const thinkingElement = document.createElement('div');
        thinkingElement.className = 'message bot-message bg-indigo-100 rounded-lg p-3 max-w-[75%] shadow-sm animate-fade-in rounded-tl-sm flex items-center space-x-1';
        
        // Create three animated dots
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = `h-1.5 w-1.5 bg-indigo-600 rounded-full animate-blink-${i+1}`;
            thinkingElement.appendChild(dot);
        }
        
        chatbox.appendChild(thinkingElement);
        
        // Scroll to bottom
        chatbox.scrollTop = chatbox.scrollHeight;
        
        return thinkingElement;
    }

    // Add message to chatbox
    function addMessageToChatbox(message, sender) {
        const messageElement = document.createElement('div');
        
        // Apply styles based on sender type
        if (sender === 'user') {
            messageElement.className = 'message user-message bg-indigo-600 text-white rounded-lg p-3 max-w-[75%] ml-auto shadow-sm animate-fade-in rounded-tr-sm';
        } else if (sender === 'bot') {
            messageElement.className = 'message bot-message bg-indigo-100 text-indigo-900 rounded-lg p-3 max-w-[75%] shadow-sm animate-fade-in rounded-tl-sm';
        } else {
            messageElement.className = 'message error-message bg-red-100 text-red-800 rounded-lg p-3 max-w-[75%] shadow-sm animate-fade-in rounded-tl-sm';
        }

        const textElement = document.createElement('p');
        textElement.className = 'text-sm';
        textElement.textContent = message;
        messageElement.appendChild(textElement);

        chatbox.appendChild(messageElement);

        // Scroll to bottom
        chatbox.scrollTop = chatbox.scrollHeight;

        return messageElement;
    }
});