/**
 * TabGraph Knowledge Graph Visualization
 *
 * Uses Cytoscape.js to render the knowledge graph with:
 * - Clusters (tab groups) as large nodes
 * - Tabs as medium nodes
 * - Entities as small nodes (optional)
 * - Edges showing relationships
 */

// Configuration
const BACKEND_URL = CONFIG.BACKEND_URL;

// Cytoscape instance
let cy = null;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  // Set up event listeners
  document.getElementById('refresh-button').addEventListener('click', loadGraph);
  document.getElementById('fit-button').addEventListener('click', fitGraph);
  document.getElementById('close-button').addEventListener('click', closeWindow);
  document.getElementById('close-info').addEventListener('click', closeInfoPanel);

  // Filter change listeners
  document.getElementById('show-singletons').addEventListener('change', loadGraph);
  document.getElementById('time-range').addEventListener('change', loadGraph);
  document.getElementById('min-cluster-size').addEventListener('change', loadGraph);

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
  cy = cytoscape({
    container: document.getElementById('cy'),

    style: [
      // Cluster nodes (large circles)
      {
        selector: 'node[type="cluster"]',
        style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'width': '80',
          'height': '80',
          'font-size': '14px',
          'text-valign': 'center',
          'text-halign': 'center',
          'color': '#fff',
          'text-outline-width': 2,
          'text-outline-color': 'data(color)',
          'border-width': 3,
          'border-color': '#fff',
        }
      },

      // Tab nodes (medium circles)
      {
        selector: 'node[type="tab"]',
        style: {
          'background-color': '#4A90E2',
          'label': 'data(label)',
          'width': '50',
          'height': '50',
          'font-size': '10px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 5,
          'color': '#333',
        }
      },

      // Entity nodes (small circles)
      {
        selector: 'node[type="entity"]',
        style: {
          'background-color': '#9C27B0',
          'label': 'data(label)',
          'width': '30',
          'height': '30',
          'font-size': '8px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 3,
          'color': '#666',
        }
      },

      // Edges
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#ccc',
          'target-arrow-color': '#ccc',
          'curve-style': 'bezier',
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

  // Background click handler (close info panel)
  cy.on('tap', (event) => {
    if (event.target === cy) {
      closeInfoPanel();
    }
  });
}

// ============================================================================
// Data Loading
// ============================================================================

/**
 * Load graph data from backend and render.
 */
async function loadGraph() {
  try {
    // Get filter values
    const includeSingletons = document.getElementById('show-singletons').checked;
    const timeRange = document.getElementById('time-range').value;
    const minClusterSize = document.getElementById('min-cluster-size').value;

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

    // Update stats
    updateStats(data.metadata);

    // Clear existing graph
    cy.elements().remove();

    // Add nodes and edges
    cy.add(data.nodes);
    cy.add(data.edges);

    // Run layout
    cy.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      nestingFactor: 1.2,
      gravity: 1,
      numIter: 1000,
    }).run();

    // Fit to view
    setTimeout(() => fitGraph(), 600);

  } catch (error) {
    console.error('Error loading graph:', error);
    showError('Unable to load graph. Is the backend running?');
  }
}

/**
 * Update statistics display.
 */
function updateStats(metadata) {
  document.getElementById('cluster-count').textContent = metadata.cluster_count || 0;
  document.getElementById('tab-count').textContent = metadata.tab_count || 0;

  // Count unique entities from nodes
  const entityCount = cy ? cy.nodes('[type="entity"]').length : 0;
  document.getElementById('entity-count').textContent = entityCount;
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
