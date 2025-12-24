// content.js
// Listen for selection events to buffer seeds (Phase 2 feature, but setting up now)
document.addEventListener('selectionchange', () => {
    const selection = window.getSelection();
    const text = selection.toString();

    if (text.length > 0) {
        let context = "";
        try {
            // Context Capture: Grab the parent container's text
            if (selection.anchorNode && selection.anchorNode.parentElement) {
                context = selection.anchorNode.parentElement.innerText;
                // Truncate if too huge
                if (context.length > 1000) context = context.substring(0, 1000) + "...";
            }
        } catch (e) {
            context = "Context capture failed.";
        }

        // We generally don't auto-send on selection change (too noisy).
        // The sidepanel polls or listens for a specific "Capture" event usually.
        // But for this project, let's assume valid logic for passing data.

        // Storing in a variable for when the user clicks "Weave" (if triggered by context menu)
        // Or if triggered via message. 
    }
});

// Listen for "GET_SELECTION" request from Side Panel
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "GET_SELECTION") {
        const selection = window.getSelection();
        const text = selection.toString();
        let context = "Context placeholder";

        if (text.length > 0 && selection.anchorNode && selection.anchorNode.parentElement) {
            context = selection.anchorNode.parentElement.innerText;
            // Simple cleanup
            context = context.replace(/\s+/g, ' ').trim();
        }

        sendResponse({ highlight: text, context: context, source_url: window.location.href });
    }
});
