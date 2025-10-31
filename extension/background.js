/**
 * TabGraph Background Service Worker
 *
 * This service worker:
 * 1. Monitors all open tabs every 5 minutes
 * 2. Sends tab data to backend for clustering
 * 3. Creates/updates Chrome Tab Groups based on clusters
 * 4. Handles keyboard shortcuts
 */

// Import configuration
import { CONFIG } from './config.js';

// Configuration
const BACKEND_URL = CONFIG.BACKEND_URL;
const MONITOR_INTERVAL = CONFIG.MONITOR_INTERVAL_MINUTES * 60 * 1000; // Convert minutes to milliseconds
const EMBEDDINGS_CACHE_KEY = 'embeddingsCache'; // Storage key for embedding cache

// State
let monitorIntervalId = null;
let embeddingsCache = new Map(); // Cache: "url:title" -> embedding

// ============================================================================
// Initialization
// ============================================================================

/**
 * Initialize the extension on install/startup.
 */
chrome.runtime.onInstalled.addListener(async () => {
  console.log('TabGraph extension installed');

  // Load embeddings cache from storage
  const { embeddingsCache: cachedEmbeddings } = await chrome.storage.local.get([
    EMBEDDINGS_CACHE_KEY
  ]);

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
    // Get all tabs from normal windows only
    const tabs = await chrome.tabs.query({ windowType: 'normal' });

    // Filter out chrome:// and extension pages
    const validTabs = tabs.filter(tab =>
      tab.url &&
      !tab.url.startsWith('chrome://') &&
      !tab.url.startsWith('chrome-extension://')
    );

    // Convert to API format
    const tabsData = validTabs.map(tab => {
      // Handle groupId safely - it might be undefined in older Chrome versions
      let groupId = null;
      try {
        if (tab.groupId !== undefined && tab.groupId !== chrome.tabGroups.TAB_GROUP_ID_NONE) {
          groupId = tab.groupId;
        }
      } catch (e) {
        // groupId not supported or chrome.tabGroups not available
        console.warn('Tab groups not supported:', e);
      }

      return {
        id: tab.id,
        url: tab.url,
        title: tab.title || 'Untitled',
        favicon_url: tab.favIconUrl || null,
        window_id: tab.windowId,
        group_id: groupId,
      };
    });

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
    console.log('Sending tabs to backend:', `${BACKEND_URL}/api/tabs/ingest`);
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
      const errorText = await response.text();
      throw new Error(`Backend returned ${response.status}: ${response.statusText}. Body: ${errorText}`);
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
    console.error('Error details:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
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
    console.log(`[TAB GROUP] Processing cluster: ${cluster.name}`);
    const tabIds = cluster.tabs.map(tab => tab.id);
    console.log(`[TAB GROUP] - Cluster has ${tabIds.length} tabs from backend`);

    // Filter to only tabs that still exist in normal windows
    const existingTabs = await chrome.tabs.query({ windowType: 'normal' });
    const existingTabIds = new Set(existingTabs.map(t => t.id));
    const validTabs = existingTabs.filter(t => tabIds.includes(t.id));
    console.log(`[TAB GROUP] - ${validTabs.length} tabs still exist in browser`);

    if (validTabs.length === 0) {
      console.log(`[TAB GROUP] ❌ No valid tabs for cluster: ${cluster.name}`);
      return;
    }

    // Don't create tab groups for single tabs (min cluster size = 2)
    if (validTabs.length < 2) {
      console.log(`[TAB GROUP] ⏭️  Skipping single-tab cluster: ${cluster.name} (${validTabs.length} tab)`);
      return;
    }

    // Group tabs by window (can't group tabs across different windows)
    const tabsByWindow = new Map();
    validTabs.forEach(tab => {
      if (!tabsByWindow.has(tab.windowId)) {
        tabsByWindow.set(tab.windowId, []);
      }
      tabsByWindow.get(tab.windowId).push(tab);
    });

    console.log(`[TAB GROUP] - Tabs span ${tabsByWindow.size} window(s)`);

    // Process each window separately
    for (const [windowId, windowTabs] of tabsByWindow.entries()) {
      // Skip if only 1 tab in this window
      if (windowTabs.length < 2) {
        console.log(`[TAB GROUP] ⏭️  Skipping window ${windowId} - only ${windowTabs.length} tab`);
        continue;
      }

      const windowTabIds = windowTabs.map(t => t.id);
      console.log(`[TAB GROUP] - Processing ${windowTabIds.length} tabs in window ${windowId}`);

      // Check if ALL tabs in this window are already in the SAME group
      const tabsInGroup = windowTabs.filter(t =>
        t.groupId !== chrome.tabGroups.TAB_GROUP_ID_NONE
      );

      let groupId;

      // Check if all tabs share the same group ID
      const groupIds = new Set(tabsInGroup.map(t => t.groupId));

      if (tabsInGroup.length === windowTabIds.length && groupIds.size === 1) {
        // All tabs already in the same group - just update properties
        groupId = tabsInGroup[0].groupId;
        console.log(`[TAB GROUP] ♻️  Window ${windowId}: Cluster "${cluster.name}" already has group ${groupId}, updating properties`);
      } else if (tabsInGroup.length > 0 && groupIds.size === 1) {
        // Some tabs in a group, add the rest
        groupId = tabsInGroup[0].groupId;

        const tabsToAdd = windowTabIds.filter(id =>
          !tabsInGroup.find(t => t.id === id)
        );

        if (tabsToAdd.length > 0) {
          console.log(`[TAB GROUP] ➕ Window ${windowId}: Adding ${tabsToAdd.length} tabs to existing group ${groupId}`);
          await chrome.tabs.group({ groupId, tabIds: tabsToAdd });
        }
      } else {
        // Tabs are split across multiple groups or ungrouped - create new unified group
        console.log(`[TAB GROUP] 🆕 Window ${windowId}: Creating new group for cluster "${cluster.name}" with ${windowTabIds.length} tabs`);
        groupId = await chrome.tabs.group({ tabIds: windowTabIds });
        console.log(`[TAB GROUP] ✅ Window ${windowId}: Created group ${groupId}`);
      }

      // Update group properties
      console.log(`[TAB GROUP] 🎨 Window ${windowId}: Updating group ${groupId} properties: title="${cluster.name}", color="${cluster.color}"`);
      await chrome.tabGroups.update(groupId, {
        title: cluster.name,
        color: cluster.color,
        collapsed: false,
      });

      console.log(`[TAB GROUP] ✅ Window ${windowId}: Successfully updated group "${cluster.name}" with ${windowTabIds.length} tabs`);
    }

  } catch (error) {
    console.error(`Error creating/updating tab group for cluster "${cluster.name}":`, error);
  }
}

// ============================================================================
// Message Handling
// ============================================================================

/**
 * Listen for messages from content scripts and popup.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
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
