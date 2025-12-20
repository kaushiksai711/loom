// sidepanel.js

const API_URL = "http://localhost:8000/api/v1";
let currentSessionId = null;
let lastProcessedTimestamp = 0;

document.addEventListener('DOMContentLoaded', () => {
    const createBtn = document.getElementById('create-session-btn');
    const statusDiv = document.getElementById('status');
    const seedList = document.getElementById('seed-list');

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
            console.log("Received direct message");
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

            if (!res.ok) throw new Error("API Error: " + res.status);

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
        console.log("Handling harvest:", payload);

        // Deduplication: Ignore if we already processed this timestamp
        if (payload.timestamp && payload.timestamp === lastProcessedTimestamp) {
            console.log("Duplicate harvest ignored");
            return;
        }
        lastProcessedTimestamp = payload.timestamp;

        if (!currentSessionId) {
            // Double check storage
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

            if (!res.ok) throw new Error("API Error: " + res.status);

            const data = await res.json();

            const li = document.createElement('li');
            li.textContent = payload.highlight.substring(0, 50) + "...";
            seedList.prepend(li);
            statusDiv.textContent = "Seed harvested!";

        } catch (e) {
            statusDiv.textContent = "Harvest failed: " + e.message;
            console.error(e);
        }
    }
});
