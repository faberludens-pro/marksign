// Open side panel when toolbar icon is clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});

// Reset panel content when the user switches tabs
chrome.tabs.onActivated.addListener(() => {
  chrome.runtime.sendMessage({ type: 'TAB_SWITCHED' }).catch(() => {
    // Panel may not be open — ignore
  });
});
