// background.js

// Create Context Menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "weave-this",
    title: "Weave This",
    contexts: ["selection"]
  });

  // Open side panel on action click
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

// Handle Context Menu Click
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "weave-this" && info.selectionText) {

    // 1. Open side panel IMMEDIATELY (needs user gesture)
    if (tab.windowId >= 0) {
      chrome.sidePanel.open({ windowId: tab.windowId }).catch(e => console.error("Panel open failed:", e));
    }

    // NEW LOGIC: Ask content script for context
    if (tab.id) {
      chrome.tabs.sendMessage(tab.id, { type: "GET_SELECTION", search_text: info.selectionText }, (response) => {
        // Handle context response or fallback
        // Note: If content script is not loaded (e.g. strict page), response will be undefined.

        const payload = {
          highlight: (response && response.highlight) || info.selectionText,
          context: (response && response.context) || "Context unavailable (Script Error)",
          source_url: (response && response.source_url) || tab.url || "unknown",
          timestamp: Date.now()
        };

        saveAndTrigger(payload);
      });
    } else {
      // Fallback for weird edge cases
      const payload = {
        highlight: info.selectionText,
        context: "Context unavailable (No Tab)",
        source_url: tab.url || "unknown",
        timestamp: Date.now()
      };
      saveAndTrigger(payload);
    }
  }
});

function saveAndTrigger(payload) {
  // 2. Buffer to storage (Async)
  chrome.storage.local.set({ pendingHarvest: payload });

  // 3. Try sending message directly (Backup)
  setTimeout(() => {
    chrome.runtime.sendMessage({
      type: "HARVEST_TRIGGER",
      payload: payload
    }).catch(() => { });
  }, 500);
}

