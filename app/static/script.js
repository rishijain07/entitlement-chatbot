// app/static/script.js

// Get DOM elements
const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// --- Configuration ---
// URL of your running Flask backend API
// Since the frontend is now served by Flask, we can use a relative path
const API_URL = '/chat'; // Changed from absolute URL

// --- Event Listeners ---

// Send message when button is clicked
sendButton.addEventListener('click', sendMessage);

// Send message when Enter key is pressed in the input field
userInput.addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
});

// --- Functions ---

/**
 * Sends the user's message to the backend and displays the response.
 */
async function sendMessage() {
    const userMessage = userInput.value.trim();

    if (userMessage === '') {
        return; // Don't send empty messages
    }

    // Display user message immediately
    addMessageToChatbox(userMessage, 'user');
    userInput.value = ''; // Clear input field

    // Add a temporary thinking indicator for the bot (optional)
    const thinkingMessage = addMessageToChatbox('...', 'bot');

    try {
        // Send message to Flask backend using the relative URL
        const response = await fetch(API_URL, { // Uses relative '/chat'
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: userMessage }),
        });

        // Remove the thinking indicator
        if (chatbox.contains(thinkingMessage)) { // Check if it still exists
             chatbox.removeChild(thinkingMessage);
        }


        if (!response.ok) {
            // Handle HTTP errors (like 500 Internal Server Error)
            const errorData = await response.json().catch(() => ({ error: `HTTP error! Status: ${response.status}` }));
            console.error('API Error Response:', errorData);
            addMessageToChatbox(`Error: ${errorData.error || response.statusText}`, 'error');
            return;
        }

        // Parse JSON response
        const data = await response.json();

        if (data && data.reply) {
            // Display bot's reply
            addMessageToChatbox(data.reply, 'bot');
        } else {
            addMessageToChatbox('Received an empty or invalid response from the server.', 'error');
        }

    } catch (error) {
         // Remove the thinking indicator even if there's an error
        if (chatbox.contains(thinkingMessage)) {
            chatbox.removeChild(thinkingMessage);
        }
        // Handle network errors or issues parsing JSON
        console.error('Fetch Error:', error);
        addMessageToChatbox(`Network error or failed to connect to the server. (${error.message})`, 'error');
    }
}

/**
 * Adds a message div to the chatbox element.
 * @param {string} message - The text content of the message.
 * @param {string} sender - 'user', 'bot', or 'error'. Determines the CSS class.
 * @returns {HTMLElement} The created message element.
 */
function addMessageToChatbox(message, sender) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`); // e.g., 'user-message', 'bot-message'

    const textElement = document.createElement('p');
    textElement.textContent = message; // Use textContent to prevent XSS issues
    messageElement.appendChild(textElement);

    chatbox.appendChild(messageElement);

    // Scroll to the bottom of the chatbox
    chatbox.scrollTop = chatbox.scrollHeight;

    return messageElement; // Return the element in case we need to remove it (like the thinking indicator)
}