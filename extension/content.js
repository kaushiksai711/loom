// content.js
// Listen for selection events to buffer seeds (Phase 2 feature, but setting up now)
document.addEventListener('selectionchange', () => {
    const selection = window.getSelection().toString();
    if (selection.length > 0) {
        // Send to background/sidepanel if needed
        // chrome.runtime.sendMessage({ type: "SELECTION_UPDATE", text: selection });
    }
});
