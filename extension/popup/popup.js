/**
 * TabGraph Popup UI Script
 */

import { CONFIG } from '../config.js';

const BACKEND_URL = CONFIG.BACKEND_URL;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  // Set up event listeners
  document.getElementById('sync-button').addEventListener('click', handleSyncClick);
  document.getElementById('view-graph-button').addEventListener('click', handleViewGraphClick);

  // Load initial data
  await loadDashboardData();
});

// ============================================================================
// Event Handlers
// ============================================================================

/**
 * Handle sync button click.
 *
 * This triggers a sync in the background and returns immediately.
 * The dashboard will update when clustering completes.
 */
async function handleSyncClick() {
  const button = document.getElementById('sync-button');
  button.disabled = true;
  button.style.opacity = '0.6';

  try {
    // Send message to background script to sync now (non-blocking)
    chrome.runtime.sendMessage({ action: 'sync-now' });

    // Show immediate feedback
    showInfo('Syncing tabs in background...');

    // Poll for updates every 500ms for up to 10 seconds
    let attempts = 0;
    const maxAttempts = 20;

    const pollInterval = setInterval(async () => {
      attempts++;

      // Reload dashboard data
      await loadDashboardData();

      // Stop polling after max attempts or if we have clusters
      if (attempts >= maxAttempts) {
        clearInterval(pollInterval);
        button.disabled = false;
        button.style.opacity = '1';
      }
    }, 500);

    // Re-enable button after 2 seconds regardless
    setTimeout(() => {
      button.disabled = false;
      button.style.opacity = '1';
    }, 2000);

  } catch (error) {
    console.error('Error syncing:', error);
    showError('Failed to sync tabs');
    button.disabled = false;
    button.style.opacity = '1';
  }
}

/**
 * Handle view graph button click.
 */
function handleViewGraphClick() {
  // TODO: Open full graph visualization page
  chrome.tabs.create({ url: chrome.runtime.getURL('graph/graph.html') });
}

// ============================================================================
// Data Loading
// ============================================================================

/**
 * Load dashboard data from backend and update UI.
 */
async function loadDashboardData() {
  try {
    // Fetch clusters from backend
    const response = await fetch(`${BACKEND_URL}/api/tabs/clusters`);

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();

    // Get important tabs count from background script
    const { importantTabs } = await chrome.runtime.sendMessage({
      action: 'get-important-tabs'
    });

    // Get all current tabs to calculate ungrouped count
    const allTabs = await chrome.tabs.query({});
    const validTabs = allTabs.filter(tab =>
      tab.url &&
      !tab.url.startsWith('chrome://') &&
      !tab.url.startsWith('chrome-extension://')
    );

    // Update UI
    updateStats(data.clusters, importantTabs || [], validTabs);
    updateGroupsList(data.clusters);

  } catch (error) {
    console.error('Error loading dashboard data:', error);
    showError('Unable to connect to backend. Is the server running?');
  }
}

/**
 * Update statistics display.
 *
 * @param {Array} clusters - Clusters from backend
 * @param {Array} importantTabs - List of important tab IDs
 * @param {Array} allTabs - All current browser tabs
 */
function updateStats(clusters, importantTabs, allTabs) {
  const groupedTabs = clusters.reduce((sum, cluster) => sum + cluster.tab_count, 0);
  const totalTabs = allTabs.length;
  const ungroupedTabs = totalTabs - groupedTabs;

  document.getElementById('groups-count').textContent = clusters.length;
  document.getElementById('tabs-count').textContent = groupedTabs;
  document.getElementById('tabs-free-count').textContent = Math.max(0, ungroupedTabs);
  document.getElementById('important-count').textContent = importantTabs.length;
}

/**
 * Update the groups list display.
 *
 * @param {Array} clusters - Clusters from backend
 */
function updateGroupsList(clusters) {
  const listElement = document.getElementById('groups-list');

  if (clusters.length === 0) {
    listElement.innerHTML = '<p class="loading">No tab groups yet. Open some tabs and click sync!</p>';
    return;
  }

  // Clear loading message
  listElement.innerHTML = '';

  // Create group items
  clusters.forEach(cluster => {
    const groupItem = document.createElement('div');
    groupItem.className = 'group-item';
    groupItem.style.borderLeftColor = getColorHex(cluster.color);

    const headerDiv = document.createElement('div');
    headerDiv.style.display = 'flex';
    headerDiv.style.alignItems = 'center';
    headerDiv.style.gap = '8px';

    headerDiv.innerHTML = `
      <div style="flex: 1;">
        <div class="group-name">${escapeHtml(cluster.name)}</div>
        <div class="group-meta">${cluster.tab_count} tabs</div>
      </div>
      <span class="expand-icon">▶</span>
    `;

    groupItem.appendChild(headerDiv);

    // Add click handler to toggle tree view and activate group
    headerDiv.addEventListener('click', async (e) => {
      e.stopPropagation();
      await toggleGroupExpansion(groupItem, cluster);
    });

    listElement.appendChild(groupItem);
  });
}

/**
 * Toggle expansion of a group item to show/hide tabs tree.
 *
 * @param {HTMLElement} groupItem - The group item DOM element
 * @param {Object} cluster - The cluster data
 */
async function toggleGroupExpansion(groupItem, cluster) {
  const isExpanded = groupItem.classList.contains('expanded');

  if (isExpanded) {
    // Collapse the group
    groupItem.classList.remove('expanded');
    const treeView = groupItem.querySelector('.tabs-tree');
    if (treeView) {
      treeView.remove();
    }
  } else {
    // Expand the group
    groupItem.classList.add('expanded');

    // Activate the tab group in Chrome
    await activateTabGroup(cluster);

    // Create and append the tree view
    const treeView = await createTabsTreeView(cluster);
    groupItem.appendChild(treeView);
  }
}

/**
 * Activate a tab group in Chrome (bring it to focus).
 *
 * @param {Object} cluster - The cluster data with tabs
 */
async function activateTabGroup(cluster) {
  try {
    if (cluster.tabs && cluster.tabs.length > 0) {
      // Get the first tab ID from the cluster
      const firstTabId = cluster.tabs[0].id;

      // Query to check if tab still exists
      const tabs = await chrome.tabs.query({});
      const tabExists = tabs.find(t => t.id === firstTabId);

      if (tabExists) {
        // Activate the first tab in the group (which will show the group)
        await chrome.tabs.update(firstTabId, { active: true });
        // Focus the window containing the tab
        await chrome.windows.update(tabExists.windowId, { focused: true });
      }
    }
  } catch (error) {
    console.error('Error activating tab group:', error);
  }
}

/**
 * Create a tree view of tabs for a cluster.
 *
 * @param {Object} cluster - The cluster data
 * @returns {HTMLElement} The tree view element
 */
async function createTabsTreeView(cluster) {
  const treeView = document.createElement('div');
  treeView.className = 'tabs-tree';

  // Get current tabs to verify they still exist
  const currentTabs = await chrome.tabs.query({});
  const currentTabIds = new Set(currentTabs.map(t => t.id));

  // Filter to only existing tabs
  const validTabs = cluster.tabs.filter(tab => currentTabIds.has(tab.id));

  if (validTabs.length === 0) {
    treeView.innerHTML = '<p class="loading" style="font-size: 11px; padding: 8px;">No tabs found in this group</p>';
    return treeView;
  }

  // Create a tab item for each tab
  validTabs.forEach(tab => {
    const tabItem = document.createElement('div');
    tabItem.className = 'tab-item';

    // Create favicon
    const favicon = document.createElement('img');
    favicon.className = 'tab-favicon';
    if (tab.favicon_url) {
      favicon.src = tab.favicon_url;
      favicon.onerror = () => {
        favicon.style.display = 'none';
        const placeholder = document.createElement('div');
        placeholder.className = 'tab-favicon default';
        tabItem.insertBefore(placeholder, tabItem.firstChild);
      };
    } else {
      favicon.className = 'tab-favicon default';
    }

    // Create title
    const title = document.createElement('div');
    title.className = 'tab-title';
    title.textContent = tab.title || 'Untitled';
    title.title = tab.title || 'Untitled';

    // Create URL display
    const urlDiv = document.createElement('div');
    urlDiv.className = 'tab-url';
    try {
      const url = new URL(tab.url);
      urlDiv.textContent = url.hostname;
      urlDiv.title = tab.url;
    } catch {
      urlDiv.textContent = tab.url;
      urlDiv.title = tab.url;
    }

    // Append elements
    tabItem.appendChild(favicon);
    tabItem.appendChild(title);
    tabItem.appendChild(urlDiv);

    // Add click handler to activate the tab
    tabItem.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await chrome.tabs.update(tab.id, { active: true });
        const tabInfo = currentTabs.find(t => t.id === tab.id);
        if (tabInfo) {
          await chrome.windows.update(tabInfo.windowId, { focused: true });
        }
      } catch (error) {
        console.error('Error activating tab:', error);
      }
    });

    treeView.appendChild(tabItem);
  });

  return treeView;
}

/**
 * Show error message.
 *
 * @param {string} message - Error message to display
 */
function showError(message) {
  const listElement = document.getElementById('groups-list');
  listElement.innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
}

/**
 * Show info message.
 *
 * @param {string} message - Info message to display
 */
function showInfo(message) {
  const listElement = document.getElementById('groups-list');
  listElement.innerHTML = `<p class="loading">${escapeHtml(message)}</p>`;
}

// ============================================================================
// Utilities
// ============================================================================

/**
 * Convert color name to hex code.
 *
 * @param {string} colorName - Chrome Tab Group color name
 * @returns {string} Hex color code
 */
function getColorHex(colorName) {
  const colors = {
    grey: '#5F6368',
    blue: '#4A90E2',
    red: '#D93025',
    yellow: '#F9AB00',
    green: '#1E8E3E',
    pink: '#E91E63',
    purple: '#9C27B0',
    cyan: '#00ACC1',
    orange: '#FF6F00',
  };
  return colors[colorName] || '#4A90E2';
}

/**
 * Escape HTML to prevent XSS.
 *
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
