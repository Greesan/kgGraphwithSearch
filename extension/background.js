/**
 * TabGraph Background Service Worker
 *
 * This service worker:
 * 1. Monitors all open tabs every 5 minutes
 * 2. Sends tab data to backend for clustering
 * 3. Creates/updates Chrome Tab Groups based on clusters
 * 4. Handles keyboard shortcuts
 */

// Configuration
const BACKEND_URL = 'http://localhost:8000';
const MONITOR_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds
const IMPORTANT_TABS_KEY = 'importantTabs'; // Storage key for important tabs
const EMBEDDINGS_CACHE_KEY = 'embeddingsCache'; // Storage key for embedding cache

// State
let monitorIntervalId = null;
let importantTabs = new Set();
let embeddingsCache = new Map(); // Cache: "url:title" -> embedding

// ============================================================================
// Initialization
// ============================================================================

/**
 * Initialize the extension on install/startup.
 */
chrome.runtime.onInstalled.addListener(async () => {
  console.log('TabGraph extension installed');

  // Load important tabs from storage
  const { importantTabs: saved, embeddingsCache: cachedEmbeddings } = await chrome.storage.local.get([
    IMPORTANT_TABS_KEY,
    EMBEDDINGS_CACHE_KEY
  ]);

  if (saved) {
    importantTabs = new Set(saved);
  }

  // Load embeddings cache
  if (cachedEmbeddings) {
    embeddingsCache = new Map(Object.entries(cachedEmbeddings));
    console.log(`Loaded ${embeddingsCache.size} cached embeddings`);
  }

  // Start monitoring
  startMonitoring();

  // Run initial sync
  await collectAndSendTabs();
});

/**
 * Start monitoring on startup if not already running.
 */
chrome.runtime.onStartup.addListener(() => {
  console.log('TabGraph extension started');
  startMonitoring();
});

// ============================================================================
// Tab Monitoring
// ============================================================================

/**
 * Start the periodic tab monitoring.
 */
function startMonitoring() {
  if (monitorIntervalId) {
    clearInterval(monitorIntervalId);
  }

  monitorIntervalId = setInterval(async () => {
    await collectAndSendTabs();
  }, MONITOR_INTERVAL);

  console.log(`Tab monitoring started (interval: ${MONITOR_INTERVAL}ms)`);
}

/**
 * Collect all open tabs and send to backend for clustering.
 *
 * This function runs asynchronously and does not block the UI.
 * Tab groups will appear when clustering completes.
 */
async function collectAndSendTabs() {
  try {
    // Get all tabs
    const tabs = await chrome.tabs.query({});

    // Filter out chrome:// and extension pages
    const validTabs = tabs.filter(tab =>
      tab.url &&
      !tab.url.startsWith('chrome://') &&
      !tab.url.startsWith('chrome-extension://')
    );

    // Convert to API format
    const tabsData = validTabs.map(tab => ({
      id: tab.id,
      url: tab.url,
      title: tab.title || 'Untitled',
      favicon_url: tab.favIconUrl || null,
      important: importantTabs.has(tab.id),
      window_id: tab.windowId,
      group_id: tab.groupId !== chrome.tabGroups.TAB_GROUP_ID_NONE ? tab.groupId : null,
    }));

    if (tabsData.length === 0) {
      console.log('No valid tabs to process');
      return;
    }

    console.log(`Collected ${tabsData.length} tabs, sending to backend...`);

    // Track which tabs have cache hits
    let cacheHits = 0;
    let cacheMisses = 0;

    tabsData.forEach(tab => {
      const cacheKey = `${tab.url}:${tab.title}`;
      if (embeddingsCache.has(cacheKey)) {
        cacheHits++;
      } else {
        cacheMisses++;
      }
    });

    console.log(`Cache stats: ${cacheHits} hits, ${cacheMisses} misses`);

    // Send to backend (backend will use batch embedding for new tabs)
    const response = await fetch(`${BACKEND_URL}/api/tabs/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tabs: tabsData,
        timestamp: new Date().toISOString(),
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('Tabs ingested:', result);

    // Cache embeddings for future use (simulated - backend would need to return them)
    // For now, just mark that we've seen these tabs
    tabsData.forEach(tab => {
      const cacheKey = `${tab.url}:${tab.title}`;
      if (!embeddingsCache.has(cacheKey)) {
        embeddingsCache.set(cacheKey, true); // Placeholder - would store actual embedding
      }
    });

    // Save updated cache to storage
    await saveEmbeddingsCache();

    // Get clusters and update tab groups (runs in background)
    await updateTabGroups();

  } catch (error) {
    console.error('Error collecting and sending tabs:', error);
  }
}

/**
 * Save embeddings cache to chrome.storage.
 */
async function saveEmbeddingsCache() {
  try {
    // Convert Map to object for storage
    const cacheObj = Object.fromEntries(embeddingsCache);
    await chrome.storage.local.set({ [EMBEDDINGS_CACHE_KEY]: cacheObj });
    console.log(`Saved ${embeddingsCache.size} embeddings to cache`);
  } catch (error) {
    console.error('Error saving embeddings cache:', error);
  }
}

/**
 * Fetch clusters from backend and update Chrome Tab Groups.
 */
async function updateTabGroups() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/tabs/clusters`);

    if (!response.ok) {
      throw new Error(`Failed to fetch clusters: ${response.status}`);
    }

    const { clusters } = await response.json();
    console.log(`Received ${clusters.length} clusters from backend`);

    // Create or update tab groups
    for (const cluster of clusters) {
      await createOrUpdateTabGroup(cluster);
    }

  } catch (error) {
    console.error('Error updating tab groups:', error);
  }
}

/**
 * Create or update a Chrome Tab Group based on cluster data.
 *
 * @param {Object} cluster - Cluster data from backend
 */
async function createOrUpdateTabGroup(cluster) {
  try {
    const tabIds = cluster.tabs.map(tab => tab.id);

    // Filter to only tabs that still exist
    const existingTabs = await chrome.tabs.query({});
    const existingTabIds = new Set(existingTabs.map(t => t.id));
    const validTabIds = tabIds.filter(id => existingTabIds.has(id));

    if (validTabIds.length === 0) {
      console.log(`No valid tabs for cluster: ${cluster.name}`);
      return;
    }

    // Check if tabs are already in a group
    const tabsInGroup = existingTabs.filter(t =>
      validTabIds.includes(t.id) &&
      t.groupId !== chrome.tabGroups.TAB_GROUP_ID_NONE
    );

    let groupId;

    if (tabsInGroup.length > 0) {
      // Use existing group
      groupId = tabsInGroup[0].groupId;

      // Add remaining tabs to the group
      const tabsToAdd = validTabIds.filter(id =>
        !tabsInGroup.find(t => t.id === id)
      );

      if (tabsToAdd.length > 0) {
        await chrome.tabs.group({ groupId, tabIds: tabsToAdd });
      }
    } else {
      // Create new group
      groupId = await chrome.tabs.group({ tabIds: validTabIds });
    }

    // Update group properties
    await chrome.tabGroups.update(groupId, {
      title: cluster.name,
      color: cluster.color,
      collapsed: false,
    });

    console.log(`Updated group "${cluster.name}" with ${validTabIds.length} tabs`);

  } catch (error) {
    console.error(`Error creating/updating tab group for cluster "${cluster.name}":`, error);
  }
}

// ============================================================================
// Keyboard Shortcuts
// ============================================================================

/**
 * Handle keyboard shortcut commands.
 */
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'mark-important') {
    await toggleImportantTab();
  }
});

/**
 * Toggle the "important" flag for the currently active tab.
 */
async function toggleImportantTab() {
  try {
    // Get active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab) {
      console.error('No active tab found');
      return;
    }

    // Toggle important status
    if (importantTabs.has(tab.id)) {
      importantTabs.delete(tab.id);
      console.log(`Tab ${tab.id} marked as NOT important`);

      // TODO: Visual indicator - remove highlight
    } else {
      importantTabs.add(tab.id);
      console.log(`Tab ${tab.id} marked as IMPORTANT`);

      // TODO: Visual indicator - add highlight

      // Extract content from the page
      await extractTabContent(tab.id);
    }

    // Save to storage
    await chrome.storage.local.set({
      [IMPORTANT_TABS_KEY]: Array.from(importantTabs)
    });

    // Send updated tab data to backend
    await collectAndSendTabs();

  } catch (error) {
    console.error('Error toggling important tab:', error);
  }
}

/**
 * Extract content from a tab using content script.
 *
 * @param {number} tabId - ID of the tab to extract content from
 */
async function extractTabContent(tabId) {
  try {
    // Send message to content script
    const response = await chrome.tabs.sendMessage(tabId, {
      action: 'extract-content'
    });

    console.log('Content extracted:', response);
  } catch (error) {
    console.error('Error extracting tab content:', error);
  }
}

// ============================================================================
// Message Handling
// ============================================================================

/**
 * Listen for messages from content scripts and popup.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'get-important-tabs') {
    sendResponse({ importantTabs: Array.from(importantTabs) });
    return true;
  }

  if (request.action === 'sync-now') {
    collectAndSendTabs().then(() => {
      sendResponse({ success: true });
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true; // Will respond asynchronously
  }
});

console.log('TabGraph background service worker loaded');
