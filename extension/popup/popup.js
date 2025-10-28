/**
 * TabGraph Popup UI Script
 */

const BACKEND_URL = 'http://localhost:8000';

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

    // Update UI
    updateStats(data.clusters, importantTabs || []);
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
 */
function updateStats(clusters, importantTabs) {
  const totalTabs = clusters.reduce((sum, cluster) => sum + cluster.tab_count, 0);

  document.getElementById('groups-count').textContent = clusters.length;
  document.getElementById('tabs-count').textContent = totalTabs;
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

    groupItem.innerHTML = `
      <div class="group-name">${escapeHtml(cluster.name)}</div>
      <div class="group-meta">${cluster.tab_count} tabs</div>
    `;

    groupItem.addEventListener('click', () => {
      // TODO: Show group details or highlight tabs in browser
      console.log('Clicked group:', cluster);
    });

    listElement.appendChild(groupItem);
  });
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
