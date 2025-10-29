/**
 * TabGraph Knowledge Graph Visualization
 *
 * Uses Cytoscape.js to render the knowledge graph with:
 * - Clusters (tab groups) as large nodes
 * - Tabs as medium nodes
 * - Entities as small nodes (optional)
 * - Edges showing relationships
 */

import { CONFIG } from '../config.js';

const BACKEND_URL = CONFIG.BACKEND_URL;

// Cytoscape instance
let cy = null;

// Current view mode: 'cluster' or 'entity'
let currentView = 'cluster';

// Store graph data for view switching
let graphData = null;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  // Set up event listeners with null checks
  const toggleViewBtn = document.getElementById('toggle-view-button');
  const refreshBtn = document.getElementById('refresh-button');
  const fitBtn = document.getElementById('fit-button');
  const closeBtn = document.getElementById('close-button');
  const closeInfoBtn = document.getElementById('close-info');
  const showSingletonsCheckbox = document.getElementById('show-singletons');
  const timeRangeSelect = document.getElementById('time-range');
  const minClusterSizeInput = document.getElementById('min-cluster-size');

  if (toggleViewBtn) toggleViewBtn.addEventListener('click', toggleView);
  if (refreshBtn) refreshBtn.addEventListener('click', loadGraph);
  if (fitBtn) fitBtn.addEventListener('click', fitGraph);
  if (closeBtn) closeBtn.addEventListener('click', closeWindow);
  if (closeInfoBtn) closeInfoBtn.addEventListener('click', closeInfoPanel);
  if (showSingletonsCheckbox) showSingletonsCheckbox.addEventListener('change', loadGraph);
  if (timeRangeSelect) timeRangeSelect.addEventListener('change', loadGraph);
  if (minClusterSizeInput) minClusterSizeInput.addEventListener('change', loadGraph);

  // Initialize Cytoscape
  initializeCytoscape();

  // Load initial graph data
  await loadGraph();
});

// ============================================================================
// Cytoscape Setup
// ============================================================================

/**
 * Initialize the Cytoscape graph instance.
 */
function initializeCytoscape() {
  // Check if Cytoscape library is loaded
  if (typeof cytoscape === 'undefined') {
    console.error('Cytoscape library not loaded!');
    showError('Failed to load graph library. Please refresh the page.');
    return;
  }

  const container = document.getElementById('cy');
  if (!container) {
    console.error('Graph container element not found!');
    return;
  }

  cy = cytoscape({
    container: container,

    style: [
      // Cluster nodes (large circles)
      {
        selector: 'node[type="cluster"]',
        style: {
          'shape': 'ellipse',
          'background-color': 'data(color)',
          'label': 'data(label)',
          'width': '70',
          'height': '70',
          'font-size': '18px',
          'font-weight': 'bold',
          'text-valign': 'center',
          'text-halign': 'center',
          'color': '#fff',
          'text-outline-width': 2,
          'text-outline-color': 'data(color)',
          'border-width': 4,
          'border-color': '#fff',
        }
      },

      // Tab nodes (medium circles) - default blue
      {
        selector: 'node[type="tab"]',
        style: {
          'shape': 'ellipse',
          'background-color': '#4A90E2',
          'label': 'data(label)',
          'width': '45',
          'height': '45',
          'font-size': '13px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 6,
          'color': '#333',
          'text-outline-width': 1,
          'text-outline-color': '#fff',
          'border-width': 2,
          'border-color': '#fff',
        }
      },

      // Tab nodes with color data (colored by cluster)
      {
        selector: 'node[type="tab"][color]',
        style: {
          'background-color': 'data(color)',
        }
      },

      // Entity nodes (small circles)
      {
        selector: 'node[type="entity"]',
        style: {
          'shape': 'ellipse',
          'background-color': '#9C27B0',
          'label': 'data(label)',
          'width': '28',
          'height': '28',
          'font-size': '12px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 4,
          'color': '#666',
          'text-outline-width': 1,
          'text-outline-color': '#fff',
        }
      },

      // Cluster->Tab edges (thick, gray)
      {
        selector: 'edge[type="contains"]',
        style: {
          'width': 3,
          'line-color': '#999',
          'curve-style': 'bezier',
        }
      },

      // Tab->Entity edges (thin, light gray)
      {
        selector: 'edge[type="references"]',
        style: {
          'width': 1,
          'line-color': '#ccc',
          'curve-style': 'bezier',
        }
      },

      // Entity->Entity edges (purple, with arrows and labels)
      {
        selector: 'edge[type="relationship"]',
        style: {
          'width': 2,
          'line-color': '#9C27B0',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': '#9C27B0',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '10px',
          'color': '#666',
          'text-background-color': '#fff',
          'text-background-opacity': 0.8,
          'text-background-padding': '2px',
        }
      },

      // Selected elements
      {
        selector: ':selected',
        style: {
          'border-width': 3,
          'border-color': '#FF6F00',
        }
      },

      // Hidden elements
      {
        selector: '.hidden',
        style: {
          'display': 'none'
        }
      },
    ],

    layout: {
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      nestingFactor: 1.2,
      gravity: 1,
      numIter: 1000,
      randomize: false,
    },
  });

  // Node click handler
  cy.on('tap', 'node', (event) => {
    const node = event.target;
    showNodeInfo(node);
  });

  // Double-click on tab nodes - open URL in new tab
  cy.on('dbltap', 'node[type="tab"]', (event) => {
    const node = event.target;
    const url = node.data('url');
    if (url) {
      chrome.tabs.create({ url: url, active: false });
    }
  });

  // Background click handler (close info panel)
  cy.on('tap', (event) => {
    if (event.target === cy) {
      closeInfoPanel();
    }
  });

  // Keyboard handlers
  document.addEventListener('keydown', (event) => {
    handleKeyDown(event);
  });
}

// ============================================================================
// Data Loading
// ============================================================================

/**
 * Load graph data from backend and render.
 */
async function loadGraph() {
  // Ensure Cytoscape is initialized
  if (!cy) {
    console.error('Cytoscape not initialized');
    showError('Graph not initialized. Please refresh the page.');
    return;
  }

  try {
    // Get filter values with null checks
    const showSingletonsEl = document.getElementById('show-singletons');
    const timeRangeEl = document.getElementById('time-range');
    const minClusterSizeEl = document.getElementById('min-cluster-size');

    const includeSingletons = showSingletonsEl ? showSingletonsEl.checked : false;
    const timeRange = timeRangeEl ? timeRangeEl.value : '';
    const minClusterSize = minClusterSizeEl ? minClusterSizeEl.value : '2';

    // Build query parameters
    const params = new URLSearchParams({
      include_singletons: includeSingletons,
      min_cluster_size: minClusterSize,
    });

    if (timeRange) {
      params.append('time_range_hours', timeRange);
    }

    // Fetch graph data
    const response = await fetch(`${BACKEND_URL}/api/graph/visualization?${params}`);

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();

    // Store graph data for view switching
    graphData = data;

    // Update stats
    updateStats(data.metadata);

    // Render the graph in current view mode
    renderGraph(currentView);

  } catch (error) {
    console.error('Error loading graph:', error);
    showError('Unable to load graph. Is the backend running?');
  }
}

/**
 * Toggle between cluster and entity views.
 */
function toggleView() {
  if (!graphData) return;

  // Toggle view mode
  currentView = currentView === 'cluster' ? 'entity' : 'cluster';

  // Update button label
  const viewLabel = document.getElementById('view-label');
  if (viewLabel) {
    viewLabel.textContent = currentView === 'cluster' ? 'Entity View' : 'Cluster View';
  }

  // Re-render graph
  renderGraph(currentView);
}

/**
 * Render the graph in the specified view mode.
 */
function renderGraph(view) {
  if (!graphData || !cy) return;

  // Clear existing graph
  cy.elements().remove();

  // Add all nodes and edges
  cy.add(graphData.nodes);
  cy.add(graphData.edges);

  if (view === 'cluster') {
    // Cluster View: Show all nodes, hide entity-entity relationships
    cy.elements().removeClass('hidden');
    cy.edges('[type="relationship"]').addClass('hidden');

    // Run hierarchical layout optimized for clusters
    cy.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 10000,
      idealEdgeLength: function(edge) {
        // Cluster-tab edges shorter, tab-entity edges longer
        if (edge.data('type') === 'contains') return 80;
        if (edge.data('type') === 'references') return 120;
        return 100;
      },
      edgeElasticity: function(edge) {
        // High elasticity for cluster-tab (keeps tabs near cluster)
        if (edge.data('type') === 'contains') return 200;
        return 100;
      },
      nestingFactor: 1.2,
      gravity: 0.8,
      numIter: 1500,
      randomize: false,
    }).run();

  } else {
    // Entity View: Hide clusters, show entity relationships, color tabs by cluster
    cy.nodes('[type="cluster"]').addClass('hidden');
    cy.edges('[type="contains"]').addClass('hidden');
    cy.edges('[type="relationship"]').removeClass('hidden');

    // Slightly enlarge tabs in entity view (since no clusters)
    cy.nodes('[type="tab"]').style({
      'width': '50',
      'height': '50',
    });

    // Run flat layout optimized for entity relationships
    cy.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      gravity: 0.3,
      numIter: 1500,
      randomize: false,
    }).run();
  }

  // Fit to view after layout
  setTimeout(() => fitGraph(), 600);
}

/**
 * Update statistics display.
 */
function updateStats(metadata) {
  const clusterCountEl = document.getElementById('cluster-count');
  const tabCountEl = document.getElementById('tab-count');
  const entityCountEl = document.getElementById('entity-count');

  if (clusterCountEl) clusterCountEl.textContent = metadata.cluster_count || 0;
  if (tabCountEl) tabCountEl.textContent = metadata.tab_count || 0;

  // Count unique entities from nodes
  const entityCount = cy ? cy.nodes('[type="entity"]').length : 0;
  if (entityCountEl) entityCountEl.textContent = entityCount;
}

/**
 * Show error message.
 */
function showError(message) {
  alert(message);
}

// ============================================================================
// Graph Controls
// ============================================================================

/**
 * Fit graph to view.
 */
function fitGraph() {
  if (cy) {
    cy.fit(null, 50);
  }
}

/**
 * Close the window.
 */
function closeWindow() {
  window.close();
}

// ============================================================================
// Info Panel
// ============================================================================

/**
 * Show information about a selected node.
 */
function showNodeInfo(node) {
  const data = node.data();
  const infoPanel = document.getElementById('info-panel');
  const infoTitle = document.getElementById('info-title');
  const infoContent = document.getElementById('info-content');

  // Set title
  infoTitle.textContent = data.label || 'Node Details';

  // Build content based on node type
  let html = '';

  if (data.type === 'cluster') {
    html = `
      <div class="info-section">
        <strong>Type:</strong> Tab Group
      </div>
      <div class="info-section">
        <strong>Tabs:</strong> ${data.tab_count || 0}
      </div>
      <div class="info-section">
        <strong>Shared Entities:</strong>
        <ul>
          ${(data.shared_entities || []).map(e => `<li>${escapeHtml(e)}</li>`).join('')}
        </ul>
      </div>
      <div class="info-section">
        <strong>Actions:</strong><br>
        <small style="color: #999;">• Press Delete/Backspace to close all tabs in this group</small>
      </div>
    `;
  } else if (data.type === 'tab') {
    html = `
      <div class="info-section">
        <strong>Type:</strong> Tab
      </div>
      <div class="info-section">
        <strong>URL:</strong><br>
        <a href="${escapeHtml(data.url)}" target="_blank">${escapeHtml(data.url)}</a>
      </div>
      <div class="info-section">
        <strong>Entities:</strong>
        <ul>
          ${(data.entities || []).map(e => `<li>${escapeHtml(e)}</li>`).join('')}
        </ul>
      </div>
      ${data.opened_at ? `
      <div class="info-section">
        <strong>Opened:</strong> ${new Date(data.opened_at).toLocaleString()}
      </div>
      ` : ''}
      <div class="info-section">
        <strong>Actions:</strong><br>
        <small style="color: #999;">
          • Double-click to open in new tab<br>
          • Press Delete/Backspace to close this tab
        </small>
      </div>
    `;
  } else if (data.type === 'entity') {
    html = `
      <div class="info-section">
        <strong>Type:</strong> Entity (Concept)
      </div>
      <div class="info-section">
        <strong>Description:</strong> ${escapeHtml(data.description || 'N/A')}
      </div>
    `;
  }

  infoContent.innerHTML = html;
  infoPanel.classList.remove('hidden');
}

/**
 * Close the info panel.
 */
function closeInfoPanel() {
  document.getElementById('info-panel').classList.add('hidden');
}

// ============================================================================
// Keyboard Handlers
// ============================================================================

/**
 * Handle keyboard events for graph interactions.
 */
function handleKeyDown(event) {
  // Delete/Backspace - close selected tab(s) or cluster
  if (event.key === 'Delete' || event.key === 'Backspace') {
    // Prevent default browser back navigation on Backspace
    event.preventDefault();

    const selected = cy.$(':selected');
    if (selected.length === 0) return;

    // Collect tabs to close
    const tabsToClose = [];

    selected.forEach(node => {
      if (node.data('type') === 'tab') {
        // Single tab selected
        const tabId = node.data('id').replace('tab_', '');
        tabsToClose.push(parseInt(tabId));
      } else if (node.data('type') === 'cluster') {
        // Cluster selected - get all tabs in the cluster
        const clusterId = node.data('id');
        // Find all tab nodes connected to this cluster
        const clusterTabs = cy.nodes('[type="tab"]').filter(tabNode => {
          return tabNode.data('cluster_id') === clusterId;
        });
        clusterTabs.forEach(tabNode => {
          const tabId = tabNode.data('id').replace('tab_', '');
          tabsToClose.push(parseInt(tabId));
        });
      }
    });

    if (tabsToClose.length > 0) {
      // Confirm deletion
      const message = tabsToClose.length === 1
        ? 'Close this tab?'
        : `Close ${tabsToClose.length} tabs?`;

      if (confirm(message)) {
        closeTabsById(tabsToClose);
      }
    }
  }
}

/**
 * Close tabs by their IDs.
 */
function closeTabsById(tabIds) {
  // Remove tabs via Chrome API
  chrome.tabs.remove(tabIds, () => {
    if (chrome.runtime.lastError) {
      console.error('Error closing tabs:', chrome.runtime.lastError);
      alert('Failed to close some tabs. They may have already been closed.');
    } else {
      // Reload graph to reflect changes
      setTimeout(() => loadGraph(), 500);
    }
  });
}

// ============================================================================
// Utilities
// ============================================================================

/**
 * Escape HTML to prevent XSS.
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
