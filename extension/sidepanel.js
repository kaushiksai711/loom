// sidepanel.js

const API_URL = "http://localhost:8000/api/v1";
let currentSessionId = null;
let lastProcessedTimestamp = 0;

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const createBtn = document.getElementById('create-session-btn');
    const statusDiv = document.getElementById('status');
    const seedList = document.getElementById('seed-list');

    // Tabs
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // Chat
    const chatInput = document.getElementById('chat-input');
    const sendChatBtn = document.getElementById('send-chat-btn');
    const chatMessages = document.getElementById('chat-messages');

    // --- Tab Logic ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    // --- Logic Restoration (Session & Harvest) ---

    // Restore session ID from storage
    chrome.storage.local.get(['currentSessionId'], (result) => {
        if (result.currentSessionId) {
            currentSessionId = result.currentSessionId;
            document.getElementById('session-info').textContent = "Session Active";
        }
    });

    // 1. Check for pending harvest on load
    chrome.storage.local.get(['pendingHarvest'], (result) => {
        if (result.pendingHarvest) {
            console.log("Found pending harvest on load");
            handleHarvest(result.pendingHarvest);
            chrome.storage.local.remove('pendingHarvest');
        }
    });

    // 2. Listen for storage changes
    chrome.storage.onChanged.addListener((changes, area) => {
        if (area === 'local' && changes.pendingHarvest && changes.pendingHarvest.newValue) {
            console.log("Storage changed: pendingHarvest");
            handleHarvest(changes.pendingHarvest.newValue);
            chrome.storage.local.remove('pendingHarvest');
        }
    });

    // 3. Listen for direct messages (Backup)
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === "HARVEST_TRIGGER") {
            handleHarvest(message.payload);
        }
    });

    createBtn.addEventListener('click', async () => {
        try {
            statusDiv.textContent = "Creating session...";
            const res = await fetch(`${API_URL}/session/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: "New Session " + new Date().toLocaleTimeString(),
                    goal: "Learning"
                })
            });

            if (!res.ok) {
                const text = await res.text();
                console.error("FULL API ERROR:", text);
                throw new Error("API Error: " + res.status + " | " + text.substring(0, 200));
            }

            const data = await res.json();
            currentSessionId = data._key;
            document.getElementById('session-info').textContent = data.title;
            statusDiv.textContent = "Session created!";

            chrome.storage.local.set({ currentSessionId });

        } catch (e) {
            statusDiv.textContent = "Error: " + e.message;
            console.error(e);
        }
    });

    async function handleHarvest(payload) {
        // Deduplication
        if (payload.timestamp && payload.timestamp === lastProcessedTimestamp) {
            return;
        }
        lastProcessedTimestamp = payload.timestamp;

        if (!currentSessionId) {
            const stored = await chrome.storage.local.get(['currentSessionId']);
            if (stored.currentSessionId) {
                currentSessionId = stored.currentSessionId;
            } else {
                statusDiv.textContent = "Please create a session first!";
                return;
            }
        }

        try {
            statusDiv.textContent = "Weaving...";
            const res = await fetch(`${API_URL}/harvest/initiate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    highlight: payload.highlight,
                    context: "Context placeholder",
                    source_url: payload.source_url,
                    session_id: currentSessionId
                })
            });

            if (!res.ok) {
                const text = await res.text();
                throw new Error("API Error: " + res.status + " " + text);
            }

            const data = await res.json();

            const li = document.createElement('li');
            li.textContent = payload.highlight.substring(0, 50) + "...";
            seedList.prepend(li);
            statusDiv.textContent = "Seed captured!";

        } catch (e) {
            statusDiv.textContent = "Harvest failed: " + e.message;
            console.error(e);
        }
    }

    // --- Chat Logic ---
    sendChatBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        if (!currentSessionId) {
            appendMessage("System", "Please start a session first.");
            return;
        }

        // Add User Message
        appendMessage("You", text);
        chatInput.value = "";

        try {
            const res = await fetch(`${API_URL}/session/chat/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: currentSessionId
                })
            });

            if (!res.ok) throw new Error("API Error");

            const data = await res.json();
            appendMessage("AI", data.response);

        } catch (e) {
            appendMessage("System", "Error: " + e.message);
        }
    }

    function appendMessage(sender, text) {
        const div = document.createElement('div');
        div.className = `message ${sender.toLowerCase() === 'you' ? 'user' : (sender.toLowerCase() === 'system' ? 'system' : 'ai')}`;
        div.textContent = text;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
