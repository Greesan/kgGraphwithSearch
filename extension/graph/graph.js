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

    // Enable multi-selection features
    boxSelectionEnabled: true,  // Shift/Ctrl+drag for box selection
    selectionType: 'additive',  // Ctrl+click toggles selection

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

      // Tab nodes (medium circles) - default bright blue
      {
        selector: 'node[type="tab"]',
        style: {
          'shape': 'ellipse',
          'background-color': '#5FA8F5',
          'label': 'data(label)',
          'width': '45',
          'height': '45',
          'font-size': '13px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 6,
          'color': '#ffffff',
          'text-outline-width': 2,
          'text-outline-color': '#1a1a1a',
          'border-width': 2,
          'border-color': '#3a3a3a',
        }
      },

      // Tab nodes with color data (colored by cluster)
      {
        selector: 'node[type="tab"][color]',
        style: {
          'background-color': 'data(color)',
        }
      },

      // Entity nodes (small circles) - bright purple, hidden by default
      {
        selector: 'node[type="entity"]',
        style: {
          'shape': 'ellipse',
          'background-color': '#B565E0',
          'label': 'data(label)',
          'width': '28',
          'height': '28',
          'font-size': '12px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 4,
          'color': '#ffffff',
          'text-outline-width': 2,
          'text-outline-color': '#1a1a1a',
          'display': 'none',  // Hidden by default in cluster view
        }
      },

      // Cluster->Tab edges (thick, lighter gray)
      {
        selector: 'edge[type="contains"]',
        style: {
          'width': 3,
          'line-color': '#5a5a5a',
          'curve-style': 'bezier',
        }
      },

      // Tab->Entity edges (thin, light gray)
      {
        selector: 'edge[type="references"]',
        style: {
          'width': 1,
          'line-color': '#4a4a4a',
          'curve-style': 'bezier',
        }
      },

      // Entity->Entity edges (bright purple, with arrows and labels)
      {
        selector: 'edge[type="relationship"]',
        style: {
          'width': 2,
          'line-color': '#B565E0',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': '#B565E0',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '10px',
          'color': '#ffffff',
          'text-background-color': '#2a2a2a',
          'text-background-opacity': 0.9,
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

      // Dimmed nodes (when selection is active in entity view)
      {
        selector: 'node.dimmed',
        style: {
          'opacity': 0.2,
        }
      },

      // Dimmed edges (when selection is active in entity view)
      {
        selector: 'edge.dimmed',
        style: {
          'opacity': 0.2,
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

    // When tab is selected, show its entities
    if (node.data('type') === 'tab') {
      showTabEntities(node);
    }

    // When cluster is selected (ctrl/cmd+click in additive mode), also select all its tabs
    if (node.data('type') === 'cluster' && node.selected()) {
      const clusterId = node.id();
      // Select all tabs connected to this cluster
      cy.nodes('[type="tab"]').filter(tabNode => {
        return tabNode.data('cluster_id') === clusterId;
      }).select();
    }
  });

  // Double-click on tab nodes - open URL in CURRENT tab
  cy.on('dbltap', 'node[type="tab"]', (event) => {
    const node = event.target;
    const url = node.data('url');
    if (url) {
      // Update current tab instead of creating new one
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs.update(tabs[0].id, { url: url });
        }
      });
    }
  });

  // Double-click on cluster nodes - collapse/expand cluster
  cy.on('dbltap', 'node[type="cluster"]', (event) => {
    const clusterNode = event.target;
    toggleClusterCollapse(clusterNode);
  });

  // Background click handler (close info panel and reset entity visibility)
  cy.on('tap', (event) => {
    if (event.target === cy) {
      closeInfoPanel();

      if (currentView === 'cluster') {
        // Cluster view: Hide all entities when clicking background
        cy.nodes('[type="entity"]').style('display', 'none');
        cy.edges('[type="references"]').style('display', 'none');
      } else {
        // Entity view: Remove dimming from all nodes and edges
        cy.nodes().removeClass('dimmed');
        cy.edges().removeClass('dimmed');
      }
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
 * Custom concentric circle layout for clusters.
 * Positions: Cluster center → Tabs in inner ring → Entities in outer ring
 */
function applyConcentricLayout() {
  if (!cy) return;

  // Get all clusters
  const clusters = cy.nodes('[type="cluster"]');

  // Track positioned entities to handle shared entities
  const positionedEntities = new Set();

  // Spacing between clusters
  const clusterSpacing = 600;
  const clustersPerRow = Math.ceil(Math.sqrt(clusters.length));

  clusters.forEach((clusterNode, clusterIndex) => {
    const clusterId = clusterNode.id();

    // Position cluster in grid
    const row = Math.floor(clusterIndex / clustersPerRow);
    const col = clusterIndex % clustersPerRow;
    const clusterX = col * clusterSpacing;
    const clusterY = row * clusterSpacing;

    // Position cluster at center
    clusterNode.position({ x: clusterX, y: clusterY });

    // Get tabs connected to this cluster
    const tabs = cy.edges(`[source="${clusterId}"][type="contains"]`)
      .map(edge => cy.getElementById(edge.data('target')));

    // Position tabs in inner circle around cluster
    const tabRadius = 150;
    const tabAngleStep = (2 * Math.PI) / Math.max(tabs.length, 1);

    tabs.forEach((tabNode, tabIndex) => {
      const angle = tabIndex * tabAngleStep;
      const tabX = clusterX + tabRadius * Math.cos(angle);
      const tabY = clusterY + tabRadius * Math.sin(angle);
      tabNode.position({ x: tabX, y: tabY });

      // Get entities connected to this tab
      const entities = cy.edges(`[source="${tabNode.id()}"][type="references"]`)
        .map(edge => cy.getElementById(edge.data('target')));

      // Position entities in outer circle around their tab
      const entityRadius = 80;
      const entityAngleStep = (2 * Math.PI) / Math.max(entities.length, 1);

      entities.forEach((entityNode, entityIndex) => {
        const entityId = entityNode.id();

        // Only position if not already positioned by another tab
        if (!positionedEntities.has(entityId)) {
          const entityAngle = angle + (entityIndex * entityAngleStep);
          const entityX = tabX + entityRadius * Math.cos(entityAngle);
          const entityY = tabY + entityRadius * Math.sin(entityAngle);
          entityNode.position({ x: entityX, y: entityY });
          positionedEntities.add(entityId);
        }
      });
    });
  });

  // Handle orphaned nodes (not connected to clusters)
  const orphanTabs = cy.nodes('[type="tab"]').filter(node =>
    cy.edges(`[target="${node.id()}"][type="contains"]`).length === 0
  );

  if (orphanTabs.length > 0) {
    const orphanY = Math.ceil(clusters.length / clustersPerRow) * clusterSpacing;
    orphanTabs.forEach((node, index) => {
      node.position({ x: index * 200, y: orphanY });
    });
  }
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

    // Hide single-tab clusters (they add no value - just show the tab with entities)
    cy.nodes('[type="cluster"]').forEach(clusterNode => {
      const clusterId = clusterNode.id();
      const tabCount = cy.edges(`[source="${clusterId}"][type="contains"]`).length;

      if (tabCount <= 1) {
        // Hide the cluster node and its edge
        clusterNode.addClass('hidden');
        cy.edges(`[source="${clusterId}"][type="contains"]`).addClass('hidden');
      }
    });

    // Apply custom concentric circle layout
    applyConcentricLayout();

  } else {
    // Entity View: Hide clusters, show entity relationships, color tabs by cluster
    cy.nodes('[type="cluster"]').addClass('hidden');
    cy.edges('[type="contains"]').addClass('hidden');
    cy.edges('[type="relationship"]').removeClass('hidden');

    // Show all entities in entity view
    cy.nodes('[type="entity"]').style('display', 'element');
    cy.edges('[type="references"]').style('display', 'element');

    // Slightly enlarge tabs in entity view (since no clusters)
    cy.nodes('[type="tab"]').style({
      'width': '50',
      'height': '50',
    });

    // Add tap handler for entity view to dim unconnected nodes
    cy.on('tap', 'node', (event) => {
      const selectedNode = event.target;

      // Get all connected nodes (neighbors)
      const connectedNodes = selectedNode.neighborhood().nodes();
      const connectedNodeIds = new Set([selectedNode.id(), ...connectedNodes.map(n => n.id())]);

      // Dim all nodes except selected and connected ones
      cy.nodes().forEach(node => {
        if (connectedNodeIds.has(node.id())) {
          node.removeClass('dimmed');
        } else {
          node.addClass('dimmed');
        }
      });

      // Dim edges not connected to selected node
      cy.edges().forEach(edge => {
        if (edge.source().id() === selectedNode.id() || edge.target().id() === selectedNode.id()) {
          edge.removeClass('dimmed');
        } else {
          edge.addClass('dimmed');
        }
      });
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
  setTimeout(() => {
    fitGraph();
    updateLegend();
  }, 600);
}

/**
 * Update statistics display.
 */
function updateStats(metadata) {
  const clusterCountEl = document.getElementById('cluster-count');
  const tabCountEl = document.getElementById('tab-count');
  const entityCountEl = document.getElementById('entity-count');

  // Count visible clusters (excluding hidden single-tab clusters)
  const visibleClusters = cy ? cy.nodes('[type="cluster"]').not('.hidden') : [];
  const visibleClusterCount = visibleClusters.length;

  // Count visible tabs (only tabs in visible clusters)
  const visibleTabs = cy ? cy.nodes('[type="tab"]').not('.hidden') : [];
  const visibleTabCount = visibleTabs.length;

  if (clusterCountEl) clusterCountEl.textContent = visibleClusterCount;
  if (tabCountEl) tabCountEl.textContent = visibleTabCount;

  // Count unique entities from nodes
  const entityCount = cy ? cy.nodes('[type="entity"]').length : 0;
  if (entityCountEl) entityCountEl.textContent = entityCount;
}

/**
 * Update legend to show cluster colors and names dynamically.
 */
function updateLegend() {
  if (!cy) return;

  const legendContainer = document.querySelector('.legend');
  if (!legendContainer) return;

  // Get all cluster nodes
  const clusterNodes = cy.nodes('[type="cluster"]');

  // Build legend HTML
  let legendHTML = '<h4>Legend</h4>';

  // Add cluster items if any exist
  if (clusterNodes.length > 0) {
    clusterNodes.forEach(node => {
      const color = node.data('color');
      const label = node.data('label');
      const tabCount = node.data('tab_count') || 0;

      legendHTML += `
        <div class="legend-item">
          <div class="legend-icon" style="background: ${escapeHtml(color)}; width: 35px; height: 35px; border: 3px solid #3a3a3a; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);"></div>
          <span>${escapeHtml(label)} (${tabCount} tabs)</span>
        </div>
      `;
    });
  }

  // Add generic node type items
  legendHTML += `
    <div class="legend-item">
      <div class="legend-icon entity"></div>
      <span>Entity (concept)</span>
    </div>
  `;

  legendContainer.innerHTML = legendHTML;
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
    // Build summary and topic HTML if available
    const summaryHTML = data.summary
      ? `<div class="info-section tab-summary">${escapeHtml(data.summary)}</div>`
      : '';

    const topicHTML = data.topic
      ? `<div class="info-section"><span class="topic-badge">${escapeHtml(data.topic)}</span></div>`
      : '';

    html = `
      <div class="info-section">
        <strong>Type:</strong> Tab
      </div>
      ${summaryHTML}
      ${topicHTML}
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
  // First, remove the nodes from the visualization immediately
  const nodesToRemove = [];
  tabIds.forEach(tabId => {
    const nodeId = `tab_${tabId}`;
    const node = cy.$(`#${nodeId}`);
    if (node.length > 0) {
      nodesToRemove.push(node);
    }
  });

  // Remove nodes and their connected edges
  nodesToRemove.forEach(node => {
    node.remove();
  });

  // Update stats and legend after removal
  if (graphData && graphData.metadata) {
    graphData.metadata.tab_count = (graphData.metadata.tab_count || 0) - nodesToRemove.length;
    updateStats(graphData.metadata);
  }
  updateLegend();

  // Remove tabs via Chrome API
  chrome.tabs.remove(tabIds, () => {
    if (chrome.runtime.lastError) {
      console.error('Error closing tabs:', chrome.runtime.lastError);
      alert('Failed to close some tabs. They may have already been closed.');
      // Reload graph to sync state
      setTimeout(() => loadGraph(), 500);
    } else {
      console.log(`Successfully closed ${tabIds.length} tab(s)`);

      // Notify background script to trigger a re-sync
      // This will update the backend clusters and ensure popup stats are accurate
      chrome.runtime.sendMessage({ action: 'sync-now' }, (response) => {
        if (chrome.runtime.lastError) {
          console.warn('Could not notify background script:', chrome.runtime.lastError);
        } else {
          console.log('Backend sync triggered after tab deletion');
        }
      });
    }
  });
}

// ============================================================================
// Entity Visibility & Cluster Collapse
// ============================================================================

/**
 * Show only entities connected to the selected tab.
 */
function showTabEntities(tabNode) {
  if (!cy) return;

  const tabId = tabNode.id();

  // Get entities connected to this tab
  const connectedEntities = cy.edges(`[source="${tabId}"][type="references"]`)
    .map(edge => cy.getElementById(edge.data('target')));

  const connectedEntityIds = new Set(connectedEntities.map(e => e.id()));

  // Show only connected entities (hide all others)
  cy.nodes('[type="entity"]').forEach(entityNode => {
    if (connectedEntityIds.has(entityNode.id())) {
      entityNode.style('display', 'element');  // Show connected entities
      entityNode.connectedEdges().style('display', 'element');  // Show their edges
    } else {
      entityNode.style('display', 'none');  // Hide unconnected entities
      entityNode.connectedEdges().style('display', 'none');  // Hide their edges
    }
  });
}

/**
 * Toggle cluster collapse state (hide/show tabs and entities).
 */
function toggleClusterCollapse(clusterNode) {
  if (!cy) return;

  const clusterId = clusterNode.id();
  const isCollapsed = clusterNode.hasClass('collapsed');

  // Get Chrome tab group ID from first tab in this cluster
  let chromeGroupId = null;
  const firstEdge = cy.edges(`[source="${clusterId}"][type="contains"]`).first();
  if (firstEdge.length > 0) {
    const firstTab = cy.getElementById(firstEdge.data('target'));
    chromeGroupId = firstTab.data('group_id');
  }

  if (isCollapsed) {
    // Expand: Show tabs and their entities
    clusterNode.removeClass('collapsed');

    // Show tabs
    cy.edges(`[source="${clusterId}"][type="contains"]`).forEach(edge => {
      const tabNode = cy.getElementById(edge.data('target'));
      tabNode.removeClass('hidden');
      edge.removeClass('hidden');

      // Show entities connected to this tab (but keep them hidden by default - user must click tab)
      // Don't automatically show entities on expand
    });

    // Expand Chrome tab group
    if (chromeGroupId) {
      chrome.tabGroups.update(chromeGroupId, { collapsed: false }, () => {
        if (chrome.runtime.lastError) {
          console.error('Error expanding Chrome tab group:', chrome.runtime.lastError);
        } else {
          console.log(`Expanded Chrome tab group ${chromeGroupId}`);
        }
      });
    }
  } else {
    // Collapse: Hide tabs and their entities
    clusterNode.addClass('collapsed');

    // Hide tabs
    cy.edges(`[source="${clusterId}"][type="contains"]`).forEach(edge => {
      const tabNode = cy.getElementById(edge.data('target'));
      tabNode.addClass('hidden');
      edge.addClass('hidden');

      // Hide entities connected to this tab (use style display, not class)
      cy.edges(`[source="${tabNode.id()}"][type="references"]`).forEach(entityEdge => {
        const entityNode = cy.getElementById(entityEdge.data('target'));
        entityNode.style('display', 'none');
        entityEdge.style('display', 'none');
      });
    });

    // Collapse Chrome tab group
    if (chromeGroupId) {
      chrome.tabGroups.update(chromeGroupId, { collapsed: true }, () => {
        if (chrome.runtime.lastError) {
          console.error('Error collapsing Chrome tab group:', chrome.runtime.lastError);
        } else {
          console.log(`Collapsed Chrome tab group ${chromeGroupId}`);
        }
      });
    }
  }
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
