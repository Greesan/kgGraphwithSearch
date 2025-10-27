# Product Requirements Document: TabGraph

**AI-Powered Tab Manager with Temporal Knowledge Graph**

---

## Executive Summary

TabGraph is a Chromium browser extension that automatically organizes tabs into semantic groups using AI-powered clustering, builds a personal temporal knowledge graph of browsing behavior, and proactively recommends related content using You.com's APIs. It combines Chrome's native Tab Groups API with knowledge graph technology to solve tab overload for researchers, learners, and knowledge workers.

**Tech Stack:** Python (FastAPI) + Chromium Extension + You.com APIs + OpenAI + SQLite/Neo4j

---

## Problem Statement

**Current Pain Points:**
1. Researchers/learners open 50+ tabs and lose track of context
2. Manual tab organization is tedious and time-consuming
3. Users miss important related content while researching
4. No way to track research evolution over time
5. Existing tab managers don't understand semantic relationships

**Who This Affects:**
- Researchers conducting literature reviews
- Students learning complex topics
- Developers researching technical solutions
- Knowledge workers synthesizing information across multiple sources

---

## Solution Overview

TabGraph combines three core technologies:
1. **Chrome Tab Groups API** - Native browser tab organization
2. **Temporal Knowledge Graph** - Track entities, relationships, and evolution over time
3. **You.com APIs** - Real-time web search, news, and AI-powered content analysis

**Key Innovation:** Unlike traditional tab managers, TabGraph understands the *semantic relationships* between tabs and builds a personal knowledge graph that grows with the user's research.

---

## Core Features

### 1. Automatic Tab Grouping

**Functionality:**
- Monitors all open tabs continuously (every 5 minutes)
- Analyzes tab content and extracts entities
- Clusters tabs by topic using entity similarity
- Creates/updates Chrome Tab Groups automatically
- Assigns group names based on dominant topics

**User Control:**
- **Settings Toggle:**
  - **Respect Mode:** Keep existing user-created groups, only add new groups for uncategorized tabs
  - **Reorganize Mode:** AI reorganizes all tabs based on current clustering analysis

**Technical Details:**
- Uses Chrome Tab Groups API (`chrome.tabs.group()`, `chrome.tabGroups.update()`)
- Clustering algorithm: Hierarchical or DBSCAN based on entity similarity matrix
- Group names generated from top 2-3 entities in cluster
- Group colors assigned consistently per topic

---

### 2. Two-Tier Analysis System

**Tier 1: Metadata Analysis (All Tabs)**
- **Input:** URL + Page Title
- **Processing:** Fast entity extraction from URL patterns and title keywords
- **Cost:** Free, instant
- **Use Case:** Lightweight tracking for all tabs

**Tier 2: Deep Analysis (Important Tabs Only)**
- **Input:** Full page content (first 10k characters)
- **Processing:**
  1. You.com Express API - LLM-powered entity/concept extraction
  2. OpenAI GPT-4o-mini - Structure into Entity/Triplet models
  3. Store in temporal knowledge graph with timestamp
- **Cost:** API calls (You.com + OpenAI)
- **Use Case:** Detailed understanding of key research materials

**Marking Tabs as Important:**
- **Keyboard Shortcut:** `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`)
- **Visual Indicator:** Important tabs shown in gold/orange in graph visualization
- **Automatic Trigger:** Content extraction + deep analysis pipeline

---

### 3. Interactive Knowledge Graph Visualization

**Technology:** Cytoscape.js for graph rendering

**Visual Elements:**

**Nodes (Tabs):**
- Regular tabs: Light blue circles (size: 15px)
- Important tabs: Gold/orange circles (size: 20px)
- Node label: Tab title (truncated)
- Hover: Full title + snippet

**Edges (Relationships):**
- Drawn between tabs with shared entities
- Edge thickness: Proportional to number of shared entities
- Edge label: Shared entity names

**Clusters (Tab Groups):**
- Background color boxes around grouped tabs
- Cluster label: Group name (e.g., "Graph Databases")
- Visual distinction from Chrome Tab Groups colors

**Interactions:**

| Action | Result |
|--------|--------|
| **Double-click node** | Switch to that tab (bring to front) |
| **Right-click node** | Context menu: Close tab, Mark/unmark important, Move to group |
| **Right-click cluster** | Context menu: Close entire group, Rename group, Show recommendations |
| **Click cluster** | Show all tabs in group + recommendations panel |
| **Drag node between clusters** | Move tab to different group |
| **Hover node** | Show tooltip with tab preview/snippet |
| **Hover edge** | Show shared entities between tabs |
| **Click "+" on cluster** | Open recommendations panel for that topic |

---

### 4. Content Recommendations

**Recommendation Sources:**

**You.com Search API:**
- Query based on cluster topics
- Find high-quality related content user hasn't seen
- Filter for novelty (not already in knowledge graph)

**You.com News API:**
- Breaking news on entities in user's knowledge graph
- Time-stamped for temporal tracking
- Relevance filtering based on user's research focus

**Recommendation Display:**
- Shown in extension popup (top 3)
- Full list in graph visualization (click cluster)
- Each recommendation includes:
  - Title
  - URL
  - Snippet
  - Reason: "You're reading about X but haven't seen Y"
  - Relevance score

**Opening Recommendations:**
- Click to open in new tab
- **Automatically added to relevant tab group**
- Button: "Open in [Group Name]"
- Opens in background by default

---

### 5. Tab Management from Graph

**Close Operations:**
- Close individual tab (right-click node)
- Close entire group (right-click cluster)
- Confirm dialog for group closures

**Move Operations:**
- Drag-and-drop nodes between clusters
- Right-click → "Move to..." menu
- Updates Chrome Tab Groups immediately

**Open Operations:**
- Open recommendation in specific group
- Create new tab in group from graph UI
- All new tabs tracked in knowledge graph

**Context Menu (Right-Click Node):**
```
- Switch to Tab
- Mark as Important (or Unmark)
- Move to Group >
  - [Group 1]
  - [Group 2]
  - New Group...
- Close Tab
```

**Context Menu (Right-Click Cluster):**
```
- Show Recommendations
- Rename Group
- Change Color
- Close Entire Group
- Collapse Group
```

---

### 6. Temporal Knowledge Graph

**Data Model:**

**Entities:**
- Name, Type (Person, Organization, Concept, Product, etc.)
- Description
- Created timestamp
- Last seen timestamp

**Triplets (Relationships):**
- Subject Entity → Predicate → Object Entity
- Temporal validity (start_time, end_time, is_current)
- Confidence score (0.0-1.0)
- Source (URL where relationship was found)
- Created timestamp

**Sessions:**
- Group of tabs analyzed together
- Timestamp
- Entities discovered
- Relationships formed

**Temporal Tracking:**

**Knowledge Graph Growth:**
- New entities discovered per session
- New relationships formed
- Graph size over time (entities + relationships)

**Topic Evolution:**
- Track dominant topics per day/week
- Show research focus shifts (e.g., "Python basics" → "FastAPI" → "Async programming")
- Visualize topic timeline

**Fresh Content Alerts:**
- Daily check: Query You.com News API for entities in graph
- Alert user to breaking news on their research topics
- Badge notification with count

**Temporal Queries (Advanced):**
- "What was I researching last week?"
- "When did I first learn about Neo4j?"
- "Show how my understanding of knowledge graphs evolved"

---

### 7. Extension UI Components

**Popup UI (Click Extension Icon):**
```
┌─────────────────────────────────────┐
│  TabGraph                     [⚙️]  │
├─────────────────────────────────────┤
│  📊 Current Session                 │
│  • 3 tab groups, 15 tabs            │
│  • 12 entities, 18 relationships    │
│  • 2 important tabs                 │
├─────────────────────────────────────┤
│  📁 Tab Groups                      │
│  ┌──────────────────────────────┐   │
│  │ 🟦 Graph Databases      [5]  │   │
│  │ 🟨 AI/LLM Research      [4]  │   │
│  │ 🟩 JavaScript Tools     [3]  │   │
│  └──────────────────────────────┘   │
├─────────────────────────────────────┤
│  💡 Recommendations (3 new)         │
│  • "Neo4j Temporal Functions"       │
│    → Open in Graph Databases        │
│  • "GraphRAG with LangChain"        │
│    → Open in AI/LLM Research        │
│  • "New D3.js Release"              │
│    → Open in JavaScript Tools       │
├─────────────────────────────────────┤
│  [View Full Graph]  [Clear History] │
└─────────────────────────────────────┘
```

**Settings Page:**
```
┌─────────────────────────────────────┐
│  TabGraph Settings                  │
├─────────────────────────────────────┤
│  Tab Grouping Mode                  │
│  ○ Respect Mode                     │
│     Keep existing groups            │
│  ● Reorganize Mode                  │
│     AI reorganizes all tabs         │
├─────────────────────────────────────┤
│  Analysis Frequency                 │
│  Every: [5] minutes                 │
├─────────────────────────────────────┤
│  Privacy                            │
│  ☑ Exclude banking sites            │
│  ☑ Exclude social media             │
│  Excluded domains:                  │
│  • bank.com                         │
│  • facebook.com                     │
│  [+ Add Domain]                     │
├─────────────────────────────────────┤
│  API Configuration                  │
│  Backend URL: [localhost:8000]      │
│  Status: ✅ Connected               │
├─────────────────────────────────────┤
│  [Save Settings]                    │
└─────────────────────────────────────┘
```

**Graph Visualization Page (Full View):**
```
┌────────────────────────────────────────────────┐
│  TabGraph - Knowledge Graph          [≡] [×]  │
├────────────────────────────────────────────────┤
│  [🔄 Refresh] [⚙️] [🔍 Search]  Mode: [Respect]│
├────────────────────────────────────────────────┤
│                                                │
│        [Interactive Cytoscape Graph]           │
│                                                │
│   🟦 Graph Databases Cluster                   │
│       ● Neo4j docs (important - gold)          │
│       ● GraphRAG paper (important)             │
│       ● Cypher tutorial                        │
│       ● Neo4j pricing                          │
│       ● APOC procedures                        │
│                                                │
│   🟨 AI/LLM Research Cluster                   │
│       ● OpenAI Cookbook                        │
│       ● LangChain docs                         │
│       ● RAG tutorial                           │
│       ● Vector databases                       │
│                                                │
│   🟩 JavaScript Tools Cluster                  │
│       ● React docs                             │
│       ● D3.js examples                         │
│       ● Cytoscape.js API                       │
│                                                │
├────────────────────────────────────────────────┤
│  Recommendations for "Graph Databases":        │
│  • Neo4j Temporal Functions Guide              │
│  • Advanced Cypher Patterns                    │
│  • Graph Algorithms Library                    │
│  [Open in Group]                               │
└────────────────────────────────────────────────┘
```

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────┐
│  Browser (Comet/Chromium)                       │
│  ┌───────────────────────────────────────────┐  │
│  │  TabGraph Extension                       │  │
│  │  • Tab monitoring (background.js)         │  │
│  │  • Content extraction (content.js)        │  │
│  │  • UI (popup, graph, settings)            │  │
│  │  • Tab Groups API integration             │  │
│  └───────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ HTTP/WebSocket
                   │ localhost:8000
                   ▼
┌─────────────────────────────────────────────────┐
│  Python Backend (FastAPI)                       │
│  ┌───────────────────────────────────────────┐  │
│  │  API Server                               │  │
│  │  • /api/tabs/ingest                       │  │
│  │  • /api/tabs/clusters                     │  │
│  │  • /api/recommendations                   │  │
│  │  • /api/insights                          │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │  Agents                                   │  │
│  │  • Tab Analyzer                           │  │
│  │  • Tab Clusterer                          │  │
│  │  • Recommendation Engine                  │  │
│  │  • Temporal Tracker                       │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │  Knowledge Graph (SQLite/Neo4j)           │  │
│  │  • Entities                               │  │
│  │  • Triplets (relationships)               │  │
│  │  • Sessions                               │  │
│  └───────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ API Calls
                   ▼
┌─────────────────────────────────────────────────┐
│  External APIs                                  │
│  • You.com Express API (entity extraction)      │
│  • You.com Search API (recommendations)         │
│  • You.com News API (breaking news)             │
│  • OpenAI GPT-4o-mini (structuring)             │
└─────────────────────────────────────────────────┘
```

### Data Flow

**1. Tab Ingestion:**
```
Browser Tab → Extension (background.js)
  → Collect metadata (URL, title)
  → If important: content.js extracts full content
  → POST /api/tabs/ingest
  → Backend: Tab Analyzer
     → Regular: Extract entities from metadata
     → Important: You.com Express API + OpenAI
  → Store in Knowledge Graph with timestamp
```

**2. Clustering:**
```
Backend: Tab Clusterer
  → Query all tabs from current session
  → Calculate entity similarity matrix
  → Run clustering algorithm (DBSCAN/Hierarchical)
  → Generate cluster names from dominant entities
  → Return clusters to extension
Extension: Tab Groups API
  → Create/update Chrome Tab Groups
  → Apply settings (Respect vs Reorganize mode)
```

**3. Recommendations:**
```
Backend: Recommendation Engine
  → Analyze knowledge graph entities
  → For each cluster:
     → Query You.com Search API (related content)
     → Query You.com News API (breaking news)
  → Filter for novelty (not already in graph)
  → Rank by relevance
  → Return to extension
Extension: Display in popup + graph view
```

**4. Graph Visualization:**
```
Extension: Graph page
  → Fetch /api/tabs/clusters
  → Fetch /api/insights (temporal data)
  → Render with Cytoscape.js
     → Nodes: Tabs (color-coded by importance)
     → Edges: Shared entities
     → Clusters: Visual grouping
  → Handle interactions (click, right-click, drag)
```

---

## API Specifications

### Backend API Endpoints

#### POST /api/tabs/ingest
Receive tab data from extension for analysis.

**Request:**
```json
{
  "tabs": [
    {
      "id": 12345,
      "url": "https://neo4j.com/docs",
      "title": "Neo4j Documentation",
      "important": true,
      "content": "Full page content here...",
      "favicon": "https://neo4j.com/favicon.ico"
    }
  ],
  "timestamp": "2025-10-27T14:30:00Z"
}
```

**Response:**
```json
{
  "status": "success",
  "processed": 1,
  "entities_extracted": 5,
  "session_id": "session_abc123"
}
```

#### GET /api/tabs/clusters
Get current tab clusters for display/grouping.

**Response:**
```json
{
  "clusters": [
    {
      "id": "cluster_1",
      "name": "Graph Databases",
      "color": "#4A90E2",
      "tabs": [
        {
          "id": 12345,
          "title": "Neo4j Documentation",
          "url": "https://neo4j.com/docs",
          "important": true,
          "entities": ["Neo4j", "Cypher", "Graph Database"]
        }
      ],
      "shared_entities": ["Graph Database", "Neo4j", "Cypher"],
      "tab_count": 5
    }
  ],
  "relationships": [
    {
      "from": 12345,
      "to": 12346,
      "shared_entities": ["Neo4j", "Graph Database"],
      "strength": 0.85
    }
  ],
  "timestamp": "2025-10-27T14:35:00Z"
}
```

#### GET /api/recommendations
Get content recommendations based on current knowledge graph.

**Query Parameters:**
- `cluster_id` (optional): Get recommendations for specific cluster
- `limit` (optional): Max recommendations (default: 10)

**Response:**
```json
{
  "recommendations": [
    {
      "title": "Neo4j Temporal Functions Guide",
      "url": "https://neo4j.com/docs/temporal",
      "snippet": "Learn how to query temporal data in Neo4j...",
      "reason": "You're reading Neo4j docs but haven't seen the temporal functions",
      "relevance_score": 0.92,
      "source": "you_search",
      "cluster_id": "cluster_1",
      "is_news": false
    },
    {
      "title": "Neo4j Releases Version 5.15 with Temporal Improvements",
      "url": "https://neo4j.com/blog/release-5.15",
      "snippet": "Breaking: Neo4j announces major temporal query enhancements...",
      "reason": "Breaking news on 'Neo4j' from your research topics",
      "relevance_score": 0.88,
      "source": "you_news",
      "cluster_id": "cluster_1",
      "is_news": true,
      "published_at": "2025-10-26T10:00:00Z"
    }
  ],
  "total": 8
}
```

#### GET /api/insights
Get temporal insights about knowledge graph evolution.

**Response:**
```json
{
  "stats": {
    "total_entities": 42,
    "total_relationships": 67,
    "total_sessions": 8,
    "important_tabs": 5
  },
  "growth": {
    "entities_this_week": 15,
    "relationships_this_week": 23,
    "new_topics": ["Temporal Databases", "Cypher Query Language"]
  },
  "topic_evolution": [
    {
      "date": "2025-10-20",
      "dominant_topics": ["React", "JavaScript", "Frontend"]
    },
    {
      "date": "2025-10-25",
      "dominant_topics": ["Neo4j", "Graph Database", "Backend"]
    }
  ],
  "alerts": [
    {
      "type": "breaking_news",
      "entity": "Neo4j",
      "message": "3 news articles published on Neo4j in last 24 hours",
      "count": 3
    }
  ]
}
```

#### POST /api/tabs/mark-important
Mark a tab as important for deep analysis.

**Request:**
```json
{
  "tab_id": 12345,
  "important": true
}
```

**Response:**
```json
{
  "status": "success",
  "tab_id": 12345,
  "analysis_queued": true
}
```

---

### You.com API Integration

#### Express API
**Endpoint:** `https://api.ydc-index.io/express`
**Purpose:** LLM-powered entity extraction from page content

**Request:**
```json
{
  "query": "Extract key entities, concepts, and relationships from this text: [page content]",
  "num_web_results": 0
}
```

**Response:** LLM-generated structured response with entities and relationships

#### Search API
**Endpoint:** `https://api.ydc-index.io/search`
**Purpose:** Find related content for recommendations

**Request:**
```json
{
  "query": "temporal knowledge graphs research",
  "num_web_results": 10,
  "safesearch": "moderate",
  "country": "US"
}
```

**Response:** Search results with titles, URLs, snippets

#### News API
**Endpoint:** `https://api.ydc-index.io/news`
**Purpose:** Get breaking news on entities in knowledge graph

**Request:**
```json
{
  "query": "Neo4j graph database",
  "num_web_results": 5
}
```

**Response:** Recent news articles with timestamps

---

## Browser Extension Architecture

### File Structure

```
extension/
├── manifest.json                 # Extension configuration
├── background.js                 # Service worker (tab monitoring)
├── content.js                    # Content extraction script
├── popup/
│   ├── popup.html               # Main popup UI
│   ├── popup.js                 # Popup logic
│   └── popup.css                # Popup styling
├── graph/
│   ├── graph.html               # Full graph visualization
│   ├── graph.js                 # Cytoscape.js graph rendering
│   └── graph.css                # Graph styling
├── settings/
│   ├── settings.html            # Settings page
│   ├── settings.js              # Settings logic
│   └── settings.css             # Settings styling
├── icons/
│   ├── icon-16.png              # Extension icon (16x16)
│   ├── icon-48.png              # Extension icon (48x48)
│   └── icon-128.png             # Extension icon (128x128)
└── lib/
    ├── cytoscape.min.js         # Cytoscape library
    └── cytoscape-cose-bilkent.js # Layout algorithm
```

### manifest.json

```json
{
  "manifest_version": 3,
  "name": "TabGraph",
  "version": "1.0.0",
  "description": "AI-powered tab manager with temporal knowledge graph",
  "permissions": [
    "tabs",
    "tabGroups",
    "storage",
    "activeTab",
    "scripting"
  ],
  "host_permissions": [
    "http://localhost:8000/*",
    "<all_urls>"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16": "icons/icon-16.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png"
    }
  },
  "commands": {
    "mark-important": {
      "suggested_key": {
        "default": "Ctrl+Shift+I",
        "mac": "Command+Shift+I"
      },
      "description": "Mark current tab as important"
    }
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ]
}
```

### Key Extension Functions

#### background.js
```javascript
// Tab monitoring every 5 minutes
let monitorInterval = 5 * 60 * 1000;

function collectTabData() {
  chrome.tabs.query({}, async (tabs) => {
    const importantTabs = await getImportantTabs();

    const tabData = tabs.map(tab => ({
      id: tab.id,
      url: tab.url,
      title: tab.title,
      important: importantTabs.has(tab.id),
      favicon: tab.favIconUrl
    }));

    await sendToBackend('/api/tabs/ingest', { tabs: tabData });
  });
}

// Keyboard shortcut handler
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'mark-important') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await toggleImportant(tab.id);

    // Extract full content if marked as important
    if (await isImportant(tab.id)) {
      chrome.tabs.sendMessage(tab.id, { action: 'extract-content' });
    }
  }
});

// Tab Groups API integration
async function updateTabGroups(clusters) {
  const settings = await getSettings();

  if (settings.mode === 'reorganize') {
    // Remove all existing groups and recreate
    await ungroupAllTabs();
  }

  for (const cluster of clusters) {
    const tabIds = cluster.tabs.map(t => t.id);

    if (settings.mode === 'respect') {
      // Only group tabs that aren't already in a group
      const ungroupedTabs = await getUngroupedTabs(tabIds);
      if (ungroupedTabs.length > 0) {
        await createTabGroup(ungroupedTabs, cluster.name, cluster.color);
      }
    } else {
      // Reorganize all tabs
      await createTabGroup(tabIds, cluster.name, cluster.color);
    }
  }
}

async function createTabGroup(tabIds, name, color) {
  const groupId = await chrome.tabs.group({ tabIds });
  await chrome.tabGroups.update(groupId, {
    title: name,
    color: color
  });
}
```

#### content.js
```javascript
// Extract page content when tab marked as important
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract-content') {
    const content = {
      url: window.location.href,
      title: document.title,
      content: document.body.innerText.substring(0, 10000),
      important: true,
      timestamp: new Date().toISOString()
    };

    fetch('http://localhost:8000/api/tabs/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabs: [content] })
    });
  }
});
```

#### graph.js (Cytoscape)
```javascript
// Initialize Cytoscape graph
const cy = cytoscape({
  container: document.getElementById('graph-container'),

  style: [
    {
      selector: 'node',
      style: {
        'background-color': (node) => node.data('important') ? '#FFA500' : '#ADD8E6',
        'width': (node) => node.data('important') ? 20 : 15,
        'height': (node) => node.data('important') ? 20 : 15,
        'label': 'data(label)',
        'font-size': '10px'
      }
    },
    {
      selector: 'edge',
      style: {
        'width': 'data(strength)',
        'line-color': '#ccc',
        'target-arrow-color': '#ccc',
        'target-arrow-shape': 'triangle',
        'label': 'data(label)',
        'font-size': '8px'
      }
    }
  ],

  layout: {
    name: 'cose-bilkent',
    animate: true
  }
});

// Double-click to switch to tab
cy.on('dblclick', 'node', (event) => {
  const tabId = event.target.data('id');
  chrome.tabs.update(tabId, { active: true });
});

// Right-click context menu
cy.on('cxttap', 'node', (event) => {
  const node = event.target;
  showContextMenu(event.renderedPosition, {
    'Switch to Tab': () => chrome.tabs.update(node.data('id'), { active: true }),
    'Mark as Important': () => toggleImportant(node.data('id')),
    'Close Tab': () => chrome.tabs.remove(node.data('id'))
  });
});

// Click cluster to show recommendations
cy.on('tap', 'node[type="cluster"]', async (event) => {
  const cluster = event.target;
  const recommendations = await fetchRecommendations(cluster.id());
  showRecommendationPanel(recommendations, cluster.data('groupId'));
});
```

---

## Implementation Phases

### Phase 1: MVP - Must Have for Demo

**Goal:** Working tab auto-grouping with basic recommendations

**Backend:**
- FastAPI server setup with CORS
- POST /api/tabs/ingest endpoint
- GET /api/tabs/clusters endpoint
- Basic tab analyzer (metadata-only extraction)
- Simple clustering algorithm (entity overlap)
- You.com Search API integration
- SQLite knowledge graph storage

**Extension:**
- manifest.json with permissions
- background.js tab monitoring (5min interval)
- Tab Groups API integration (create/update groups)
- Basic popup UI showing clusters
- Keyboard shortcut for marking important
- Settings page with Respect/Reorganize toggle

**Deliverable:**
- Extension auto-groups tabs every 5 minutes
- Shows clusters in popup
- Basic recommendations from You.com Search
- Keyboard shortcut works
- Settings persist

---

### Phase 2: Enhanced - Interactive Visualization

**Goal:** Interactive graph visualization with color coding

**Backend:**
- GET /api/recommendations endpoint
- You.com Express API integration (deep analysis)
- Recommendation ranking algorithm
- Entity similarity calculation for edges

**Extension:**
- graph.html with Cytoscape.js
- Render nodes (color-coded: blue/gold)
- Render edges (shared entities)
- Cluster backgrounds/grouping
- Double-click to switch tabs
- Click cluster for recommendations
- Popup shows top 3 recommendations with "Open in Group"

**Deliverable:**
- Full interactive graph visualization
- Important tabs shown in gold
- Click to open recommendations in tab groups
- Visual entity relationships

---

### Phase 3: Full Feature Set - Polish & Advanced Features

**Goal:** Context menus, temporal insights, news alerts

**Backend:**
- GET /api/insights endpoint
- You.com News API integration
- Temporal tracking (topic evolution)
- Neo4j support (optional, for advanced temporal queries)

**Extension:**
- Context menus (right-click node/cluster)
- Close tab/group from graph
- Drag-and-drop to move tabs between groups
- Hover tooltips with tab previews
- Badge notifications for new recommendations
- Temporal insights panel
- Breaking news alerts

**Polish:**
- Icons and branding
- Error handling and loading states
- Performance optimization (caching)
- Privacy controls (exclude domains)

**Deliverable:**
- Complete feature set from PRD
- Context menus working
- Temporal insights displayed
- News alerts functional
- Production-ready extension

---

## Configuration & Setup

### Environment Variables (.env)

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# You.com API Configuration
YOU_API_KEY=your_you_com_api_key_here

# Model Configuration
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_LLM_MODEL=gpt-4o-mini

# Database Configuration
DB_PATH=./data/knowledge_graph.db

# Neo4j Configuration (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
NEO4J_DATABASE=neo4j

# FastAPI Server Configuration
SERVER_HOST=localhost
SERVER_PORT=8000
CORS_ORIGINS=chrome-extension://*,http://localhost:*

# Logging Level
LOG_LEVEL=INFO

# Tab Analysis Configuration
TAB_MONITOR_INTERVAL_MINUTES=5
MAX_CONTENT_LENGTH=10000
DEFAULT_CLUSTERING_THRESHOLD=0.6
```

### Installation & Running

**Backend:**
```bash
# Install dependencies
uv sync

# Run server
uv run python examples/start_server.py

# Server runs at http://localhost:8000
```

**Extension:**
```bash
# Load in Comet/Chrome
1. Open chrome://extensions
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select extension/ directory
5. Extension icon appears in toolbar
```

---

## Technical Challenges & Solutions

### Challenge 1: Tab Groups API Conflicts

**Problem:** User manually moves tabs while extension is reorganizing
**Solution:**
- Listen to `chrome.tabGroups.onUpdated` events
- Track user-initiated changes vs extension-initiated
- In Respect Mode, never override user changes
- Debounce clustering updates (don't run immediately after user action)

### Challenge 2: Content Extraction Performance

**Problem:** Extracting full content from 50+ tabs is slow
**Solution:**
- Only extract content for tabs marked as important
- Use content script injection on-demand (not persistent)
- Limit content to first 10k characters
- Cache extracted content (don't re-extract same page)

### Challenge 3: You.com API Rate Limits

**Problem:** API usage can be expensive
**Solution:**
- Cache You.com responses for 1 hour
- Batch recommendation requests (query once per cluster, not per tab)
- Use Search API for bulk queries, Express API only for important tabs
- Implement exponential backoff on rate limit errors

### Challenge 4: Clustering Accuracy

**Problem:** Tabs about different topics grouped together
**Solution:**
- Tune similarity threshold (default: 0.6, adjustable in settings)
- Use multiple signals: URL patterns + title + entities
- Allow manual overrides (drag-and-drop between groups)
- Learn from user corrections (track when users move tabs)

### Challenge 5: Privacy Concerns

**Problem:** Users don't want sensitive tabs analyzed
**Solution:**
- Domain exclusion list (banking, healthcare, social media)
- Clear indicator when tab is being analyzed
- All data stored locally by default
- "Clear history" button in popup
- No data sent to backend for excluded domains

---

## Future Enhancements

### v1.1: Collaboration
- Share knowledge graphs with team members
- Collaborative tab collections
- Team recommendations

### v1.2: Advanced Analytics
- Research session reports (PDF export)
- Time spent per topic
- Reading completion tracking
- Citation graph (who links to whom)

### v1.3: Mobile Support
- Sync knowledge graph to mobile
- Mobile app for viewing graph
- Cross-device tab continuity

### v1.4: AI Agents
- Custom You.com agents for specific domains
- Automated research briefs
- "Explain this topic to me" agent
- Literature review agent

### v1.5: Integrations
- Notion export
- Zotero integration
- Obsidian sync
- Readwise highlights

---

## Success Metrics

### User Value Metrics

- **Time Saved:** Average time to organize tabs (before: 5min, after: 0min)
- **Discovery:** Number of relevant recommendations clicked per session
- **Knowledge Growth:** Entities discovered per week
- **Engagement:** Daily active users, sessions per day
- **Retention:** % users returning after 7 days

---

## Appendix

### Glossary

- **Entity:** A distinct concept, person, organization, or thing extracted from text
- **Triplet:** A relationship between two entities (subject-predicate-object)
- **Cluster:** A group of tabs with shared entities/topics
- **Temporal Validity:** The time period during which a relationship is true
- **Knowledge Graph:** A network of entities and their relationships
- **Tab Group:** Chrome's native feature for organizing tabs
- **Important Tab:** User-marked tab that gets deep analysis
- **Cytoscape:** JavaScript library for graph visualization

### References

- [Chrome Tab Groups API](https://developer.chrome.com/docs/extensions/reference/tabGroups/)
- [You.com API Documentation](https://documentation.you.com/)
- [OpenAI Cookbook - Temporal Agents](https://cookbook.openai.com/examples/partners/temporal_agents_with_knowledge_graphs/)
- [Cytoscape.js Documentation](https://js.cytoscape.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-27
**Status:** Ready for Implementation
