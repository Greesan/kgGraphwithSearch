# TabGraph

**AI-Powered Tab Manager with Temporal Knowledge Graph**

Automatically organize browser tabs using AI clustering, build a personal knowledge graph, and get proactive content recommendations powered by You.com's APIs.

---

## Overview

TabGraph is a Chromium browser extension that solves tab overload for researchers, learners, and knowledge workers by:

1. **Auto-organizing tabs** into semantic groups using Chrome's Tab Groups API
2. **Building a temporal knowledge graph** that tracks entities and relationships over time
3. **Recommending related content** you haven't seen using You.com Search/News APIs
4. **Visualizing connections** between tabs in an interactive graph

---

## Key Features

### 🗂️ Smart Tab Grouping
- Monitors tabs every 5 minutes
- Clusters by topic using entity similarity
- Creates Chrome tab groups automatically
- **Settings:** Respect existing groups OR reorganize all tabs

### 🎯 Two-Tier Analysis
- **All tabs:** Fast metadata extraction (URL + title)
- **Important tabs:** Deep analysis via You.com Express API + OpenAI
- **Keyboard shortcut:** `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) to mark important

### 📊 Interactive Knowledge Graph
- **Cytoscape.js visualization** showing tab relationships
- **Color-coded nodes:** Regular tabs (blue) vs Important tabs (gold)
- **Context menus:** Close tabs, move between groups, view recommendations
- **Click cluster** to see recommended content for that topic

### 💡 Smart Recommendations
- You.com Search API: Related content you haven't seen
- You.com News API: Breaking news on your research topics
- **One-click:** Open recommendations directly in relevant tab groups

### ⏱️ Temporal Tracking
- Track knowledge graph growth over time
- See how your research focus evolves (e.g., "React" → "Next.js")
- Alerts for breaking news on entities in your graph

---

## Tech Stack

**Backend:**
- FastAPI (Python)
- SQLite or Neo4j (temporal knowledge graph)
- You.com APIs (Express, Search, News)
- OpenAI GPT-4o-mini (entity structuring)

**Extension:**
- Chromium Manifest V3
- Chrome Tab Groups API
- Cytoscape.js (graph visualization)
- Vanilla JS (popup, settings)

---

## Project Structure

```
kg-graph-search/
├── src/
│   └── kg_graph_search/
│       ├── server/              # FastAPI backend
│       ├── agents/              # Tab analyzer, clusterer, recommender
│       ├── graph/               # Knowledge graph (SQLite/Neo4j)
│       │   ├── base.py          # Abstract interface
│       │   ├── models.py        # Pydantic models
│       │   ├── database.py      # SQLite implementation
│       │   └── neo4j_store.py   # Neo4j implementation
│       ├── search/              # You.com API clients
│       └── config.py            # Configuration
├── extension/                   # Browser extension
│   ├── manifest.json
│   ├── background.js            # Tab monitoring
│   ├── content.js               # Content extraction
│   ├── popup/                   # Popup UI
│   ├── graph/                   # Graph visualization
│   └── settings/                # Settings page
├── examples/                    # Example scripts
├── PRD.md                       # Full product requirements
└── pyproject.toml              # Dependencies
```

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Chromium-based browser (Chrome, Comet, Brave, Edge, Arc)

### Installation

**1. Backend Setup**

```bash
# Clone and navigate to project
cd kgGraphwithSearch

# Install dependencies
uv sync

# Optional: Install Neo4j support
uv sync --extra neo4j

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY
# - YOU_API_KEY
```

**2. Start Backend Server**

```bash
uv run python examples/start_server.py

# Server runs at http://localhost:8000
```

**3. Load Browser Extension**

```bash
# In Chromium browser:
1. Go to chrome://extensions
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the extension/ directory
5. Extension icon appears in toolbar
```

---

## Usage

### Basic Workflow

1. **Open research tabs** (10+) on various topics
2. **Extension auto-analyzes** and creates tab groups every 5 minutes
3. **Mark important tabs** with `Ctrl+Shift+I` for deep analysis
4. **Click extension icon** to see clusters and recommendations
5. **View full graph** to explore connections between tabs
6. **Click recommendations** to open in relevant tab groups

### Configuration

**Settings (click ⚙️ in popup):**
- **Tab Grouping Mode:**
  - Respect Mode: Keep existing groups, add new ones
  - Reorganize Mode: AI reorganizes all tabs
- **Analysis Frequency:** How often to check tabs (default: 5 min)
- **Privacy:** Exclude sensitive domains (banking, social media)

---

## API Endpoints

### Backend

- `POST /api/tabs/ingest` - Receive tabs from extension
- `GET /api/tabs/clusters` - Get clustered tabs
- `GET /api/recommendations` - Get content suggestions
- `GET /api/insights` - Get temporal stats
- `POST /api/tabs/mark-important` - Mark tab for deep analysis

### You.com Integration

- **Express API:** Entity extraction from important tabs
- **Search API:** Find related content
- **News API:** Breaking news on research topics

---

## Development

### Implementation Phases

**Phase 1: MVP (12-16 hours)**
- Basic tab grouping
- Metadata-only analysis
- Simple recommendations
- Keyboard shortcut

**Phase 2: Enhanced (16-20 hours)**
- Interactive graph visualization
- Color-coded important tabs
- You.com Express API integration
- Recommendation panel

**Phase 3: Full (20-28 hours)**
- Context menus
- Temporal insights
- News alerts
- Drag-and-drop

See [PRD.md](./PRD.md) for complete specifications.

---

## Environment Variables

```env
# Required
OPENAI_API_KEY=your_key_here
YOU_API_KEY=your_key_here

# Optional
OPENAI_LLM_MODEL=gpt-4o-mini
DB_PATH=./data/knowledge_graph.db
SERVER_PORT=8000
TAB_MONITOR_INTERVAL_MINUTES=5

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your_password
```

---

## Architecture

```
┌──────────────────────────────────┐
│  Browser Extension               │
│  • Tab monitoring                │
│  • Tab Groups API                │
│  • Cytoscape graph               │
└──────────┬───────────────────────┘
           │ HTTP (localhost:8000)
           ▼
┌──────────────────────────────────┐
│  FastAPI Backend                 │
│  • Tab analyzer                  │
│  • Clustering engine             │
│  • Recommendation engine         │
│  • Knowledge graph (SQLite/Neo4j)│
└──────────┬───────────────────────┘
           │ API Calls
           ▼
┌──────────────────────────────────┐
│  External APIs                   │
│  • You.com (Express/Search/News) │
│  • OpenAI (GPT-4o-mini)          │
└──────────────────────────────────┘
```

---

## Contributing

See [PRD.md](./PRD.md) for detailed technical specifications and implementation guidelines.

---

## License

MIT License

---

## Resources

- [Chrome Tab Groups API](https://developer.chrome.com/docs/extensions/reference/tabGroups/)
- [You.com API Docs](https://documentation.you.com/)
- [OpenAI Cookbook - Temporal Agents](https://cookbook.openai.com/examples/partners/temporal_agents_with_knowledge_graphs/)
- [Cytoscape.js](https://js.cytoscape.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
