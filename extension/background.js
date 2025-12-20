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

    const payload = {
      highlight: info.selectionText,
      source_url: tab.url || "unknown",
      timestamp: Date.now()
    };

    // 2. Buffer to storage (Async)
    chrome.storage.local.set({ pendingHarvest: payload });

    // 3. Try sending message directly (Backup)
    // We delay slightly to allow panel to initialize if it wasn't open
    setTimeout(() => {
      chrome.runtime.sendMessage({
        type: "HARVEST_TRIGGER",
        payload: payload
      }).catch(() => { });
    }, 500);
  }
});
