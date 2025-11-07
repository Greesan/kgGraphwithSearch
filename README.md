<img width="1691" height="1057" alt="image" src="https://github.com/user-attachments/assets/fd71bf39-4a14-4d6e-a1a0-438298008174" />


# TabGraph

AI-powered browser extension that automatically organizes tabs into semantic clusters using knowledge graphs, with interactive visualization and intelligent tab labeling.

## ✨ Key Features

- **🎨 Interactive Graph Visualization** - Explore your browsing context with Cytoscape.js powered knowledge graphs showing tabs, clusters, and entity relationships
- **🤖 AI-Generated Tab Metadata** - Concise 6-word labels, source attribution, and summaries replace ugly browser titles
- **🔄 Multi-Provider AI Support** - Choose between You.com, Google Gemini (fast), or Gemini with grounding (accurate) for metadata generation
- **🔗 Two-Way Chrome Tab Group Sync** - Visualization and browser tab groups stay in sync; collapse/expand from either interface
- **📊 Hybrid Semantic Clustering** - Combines OpenAI embeddings with entity overlap for accurate grouping
- **🌐 Contextual Entity Enrichment** - Per-tab entity descriptions with web-sourced information
- **💡 Smart Recommendations** - AI-powered content suggestions based on your browsing context
- **⚡ High Performance** - Batch processing, caching, and async operations handle 100+ tabs efficiently

## Quick Start with Docker

**Why Docker?** Works identically on Windows, Mac, and Linux. No Python version conflicts, no module import errors, no platform-specific issues. Just install Docker and you're ready to go.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed

**1. Clone and Configure**
```bash
git clone <your-repo-url>
cd kgGraphwithSearch
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and YOU_API_KEY
```

**2. Start Backend**
```bash
docker compose up
```

The backend will start at `http://localhost:8000`. Check health: `http://localhost:8000/health`

**3. Load Extension**
1. Open `chrome://extensions` in any Chromium browser (Chrome, Edge, Brave, etc.)
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked" → select the `extension/` directory
4. Extension icon appears in toolbar

**4. Start Using**
- Open 10+ tabs on different topics
- Click the extension icon and click "Sync Tabs" to trigger clustering
- View the interactive knowledge graph: `http://localhost:8000/static/graph.html`
- Click on tab nodes to see AI-generated labels and summaries
- Double-click clusters to collapse/expand Chrome tab groups

## How It Works

```
Browser Tabs → Extension → Backend API (localhost:8000)
                              ↓
                   Tab Analysis + AI Metadata
                              ↓
                   Semantic Clustering (embeddings + entities)
                              ↓
                   Knowledge Graph Storage
                              ↓
         Chrome Tab Groups ← → Interactive Visualization
```

**Flow:**
1. Extension collects open tabs and sends to backend
2. Backend extracts entities, generates embeddings, creates AI metadata
3. Hybrid clustering algorithm groups tabs by similarity
4. Knowledge graph stores relationships between tabs, entities, clusters
5. Chrome tab groups are created/updated to match clusters
6. Interactive graph visualization shows the complete context

## Interactive Visualization

Access the graph at `http://localhost:8000/static/graph.html`

**Features:**
- **Node Types:** Clusters (large), Tabs (medium), Entities (small)
- **Color Coding:** Clusters use distinct colors (blue, red, green, etc.)
- **Interactions:**
  - Click tab nodes: Show label, source, summary, entities
  - Double-click clusters: Collapse/expand Chrome tab groups
  - Drag nodes: Reorganize layout
  - Escape key: Deselect all
- **Legend:** Shows cluster colors, tab counts, and statistics
- **Real-time sync:** Changes in Chrome reflect in visualization

## Tab Metadata Providers

Choose your AI provider via the `TAB_METADATA_PROVIDER` environment variable:

### **You.com** (default: `TAB_METADATA_PROVIDER=you`)
- Uses You.com Express Agent
- Enhanced JSON prompts for structured output
- Regex fallback for parsing
- **Latency:** 1-3s | **Cost:** Existing API key

### **Gemini** (`TAB_METADATA_PROVIDER=gemini`)
- Google Gemini 1.5 Flash model
- **Guaranteed structured JSON** via JSON Schema validation
- No web grounding (fast, uses title + URL only)
- **Latency:** 0.5-2s | **Cost:** Free tier (15 RPM)
- Requires: `GEMINI_API_KEY` in `.env`

### **Gemini Grounded** (`TAB_METADATA_PROVIDER=gemini_grounded`)
- Gemini with web grounding enabled
- Fetches and analyzes actual webpage content
- Most accurate metadata generation
- **Latency:** 2-6s | **Cost:** $35/1000 after 1500/day free tier
- Requires: `GEMINI_API_KEY` in `.env`

**Output Format (all providers):**
```json
{
  "label": "Machine Learning Tutorial",
  "source": "Medium",
  "summary": "Comprehensive guide to neural networks...",
  "display_label": "Machine Learning Tutorial • Medium"
}
```

## Tech Stack

**Extension:**
- Manifest V3
- Chrome Tab Groups API
- Vanilla JavaScript
- ES6 modules

**Backend:**
- FastAPI (Python 3.12+)
- OpenAI API (GPT-4o-mini, text-embedding-3-small)
- You.com Express Agent
- Google Gemini 1.5 Flash (optional)
- SQLite with vector embeddings
- Async batch processing

**Visualization:**
- Cytoscape.js graph library
- WebSocket for real-time updates
- Responsive layout algorithms

**Architecture:**
- Provider pattern for pluggable AI services
- Centroid-based clustering with hybrid scoring (embeddings + entity overlap)
- Database auto-migration for schema updates
- Multi-level caching (embeddings, entities, metadata)
- Graceful degradation throughout

## Project Structure

```
extension/
├── manifest.json          # Extension config
├── background.js          # Tab sync & Chrome API integration
├── content.js             # Content extraction (unused currently)
├── popup/                 # Extension popup UI
└── graph/
    └── graph.js           # Cytoscape visualization

src/kg_graph_search/
├── server/
│   ├── app.py            # FastAPI routes
│   └── models.py         # Pydantic schemas
├── agents/
│   ├── tab_clusterer.py  # Clustering logic
│   ├── entity_extractor.py
│   ├── entity_enricher.py
│   ├── metadata_provider.py      # Base interface
│   ├── you_metadata_provider.py  # You.com implementation
│   └── gemini_metadata_provider.py  # Gemini implementations
├── graph/
│   ├── database.py       # SQLite knowledge graph
│   └── models.py         # Entity/Triplet models
└── search/
    └── you_client.py     # You.com API client
```

## Configuration

Create `.env` file with:

```env
# Required
OPENAI_API_KEY=your_openai_key_here
YOU_API_KEY=your_you_api_key_here

# Optional - for Gemini providers
GEMINI_API_KEY=your_gemini_key_here

# AI Provider Selection
TAB_METADATA_PROVIDER=you  # Options: you, gemini, gemini_grounded

# Model Configuration
OPENAI_LLM_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database
DB_PATH=./data/knowledge_graph.db
USE_NEO4J=false
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Clustering (optional tuning)
SIMILARITY_THRESHOLD=0.75
ENTITY_WEIGHT=0.5
```

## API Documentation

Backend runs at `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

**Key Endpoints:**
- `POST /api/tabs/ingest` - Send tabs for clustering (returns tab_data with embeddings/entities)
- `GET /api/tabs/clusters` - Get current clusters with tabs
- `GET /api/graph/visualization` - Get Cytoscape graph data (nodes + edges)
- `GET /api/recommendations` - Get AI-powered content recommendations
- `GET /health` - Backend health check

**Visualization:**
- `http://localhost:8000/static/graph.html` - Interactive knowledge graph

See [PRD.md](./PRD.md) for complete specifications.

## Troubleshooting

### Backend Connection Issues

**"Unable to connect to backend" error:**
1. Ensure Docker is running: `docker --version`
2. Check backend is up: `docker compose ps`
3. Verify health endpoint: `http://localhost:8000/health`
4. View logs: `docker compose logs -f backend`

**Docker-specific issues:**
- **Port already in use:** Another service is using port 8000. Stop it or edit `docker-compose.yml` to use a different port
- **Container keeps restarting:** Check logs with `docker compose logs backend` for error messages
- **Build fails:** Try `docker compose build --no-cache`
- **Clean restart:** Run `docker compose down && docker compose up --build`

**Manual installation issues (Linux/WSL only):**
- **"No module named 'kg_graph_search'"** - Run `uv pip install -e .` from project root
- **Import errors** - Ensure you're running from the correct directory with `pyproject.toml`
- **uv not found** - Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Extension Issues

**Tabs not grouping:**
- Need 10+ tabs for optimal clustering (fewer tabs may not cluster)
- Click "Sync Tabs" button in extension popup to force sync
- Check service worker console: `chrome://extensions` → Details → Service Worker → Console
- Look for errors in `collectAndSendTabs()` function

**Tab groups not appearing in Chrome:**
- Check background console for `[TAB GROUP]` logs
- Verify clusters have 2+ tabs (single-tab clusters are skipped)
- Check if tabs span multiple windows (groups created per-window)
- Look for Chrome API errors

**Visualization not updating:**
- Check browser console (F12) on graph page
- Verify backend is returning data: `http://localhost:8000/api/graph/visualization`
- Try hard refresh (Ctrl+Shift+R)

**Metadata not generating:**
- Check `TAB_METADATA_PROVIDER` setting in `.env`
- For Gemini providers, verify `GEMINI_API_KEY` is set
- Check backend logs for provider initialization messages
- View API logs: `docker compose logs backend | grep metadata`

**Visualization performance with many tabs:**
- Graph handles 100+ tabs efficiently
- Layout may take a few seconds on first load
- Use browser zoom (Ctrl +/-) to fit more nodes

## Advanced: Manual Installation (Linux/WSL)

If you prefer not to use Docker or need a development setup:

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv) package manager

**Setup:**
```bash
cd kgGraphwithSearch
uv sync                     # Install dependencies
uv pip install -e .         # Install package in editable mode
cp .env.example .env        # Configure API keys

# For Gemini support
uv pip install google-generativeai

# Run backend
uv run python -m kg_graph_search.server.app
```

**Note:** This method requires proper Python environment setup and may encounter platform-specific issues. Docker is recommended for most users.

## Performance

- **Batch Embedding Generation:** 10x faster than sequential (single API call for all tabs)
- **Cached Embeddings:** Sub-2s clustering with cache hits
- **Hybrid Scoring:** Combines semantic similarity + entity overlap for better accuracy
- **Async Enrichment:** Non-blocking entity enrichment doesn't delay clustering
- **Database Optimization:** Indexed queries, batch operations, auto-migration

## Privacy

- All processing runs locally (localhost:8000)
- No data sent to third parties except AI APIs (OpenAI, You.com, Gemini)
- Excludes `chrome://` and extension pages
- Tab data stored in local SQLite database

## License

MIT
