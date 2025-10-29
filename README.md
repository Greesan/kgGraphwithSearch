HOLY IT ACTUALLY KINDA WORKS!

<img width="1874" height="1013" alt="image" src="https://github.com/user-attachments/assets/6831e293-b731-4a8a-bdb8-88a5cc711cd6" />


# TabGraph

AI-powered browser extension that automatically organizes tabs into semantic groups using knowledge graphs and web APIs.

## Quick Start

**1. Backend Setup**
```bash
cd kgGraphwithSearch
uv sync
cp .env.example .env  # Add OPENAI_API_KEY and YOU_API_KEY
uv run python -m kg_graph_search.server.app
```

**2. Load Extension**
1. Open `chrome://extensions` in any Chromium browser
2. Enable "Developer mode"
3. Click "Load unpacked" → select `extension/` directory
4. Extension icon appears in toolbar

**3. Start Using**
- Open 10+ tabs on different topics
- Extension auto-groups tabs every 5 minutes (or click refresh in popup)
- Press `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) to mark tabs as important for deep analysis

## Features

- **Automatic Tab Grouping** - Clusters tabs by semantic similarity every 5 minutes
- **Chrome Tab Groups Integration** - Creates native Chrome tab groups with names and colors
- **Keyboard Shortcut** - `Ctrl+Shift+I` marks tab as important for deep content analysis
- **Two-Tier Analysis** - Fast metadata extraction for all tabs, deep AI analysis for important ones
- **Knowledge Graph** - Tracks entities and relationships (Neo4j or SQLite)
- **Content Recommendations** - Suggests related content via You.com APIs
- **Privacy-First** - Excludes chrome:// and extension pages, runs locally

## How It Works

```
Browser Tabs → Extension → Backend (localhost:8000)
            → Tab Analysis + Clustering
            → Returns Groups
            → Creates Chrome Tab Groups
```

**Important Tab Flow:**
```
Ctrl+Shift+I → Extract content → Backend enrichment
            → Store in knowledge graph
            → Enhanced clustering with entity data
```

## Tech Stack

**Extension:** Manifest V3, Chrome Tab Groups API, Vanilla JS
**Backend:** FastAPI, OpenAI GPT-4o-mini
**Graph:** Neo4j or SQLite
**APIs:** You.com (Search, News, Express)

## Project Structure

```
extension/
├── manifest.json          # Extension config
├── background.js          # Tab monitoring & clustering
├── content.js             # Content extraction
└── popup/                 # Popup UI

src/kg_graph_search/
├── server/                # FastAPI backend
├── agents/                # Tab analyzer, clusterer
├── graph/                 # Knowledge graph (SQLite)
└── search/                # You.com API clients
```

## Troubleshooting

**Extension shows "Unable to connect to backend"**
- Ensure backend is running: `uv run python -m kg_graph_search.server.app`
- Check `http://localhost:8000` is accessible

**Tabs not grouping**
- Click refresh button in popup to force sync
- Need 10+ tabs for optimal clustering
- Check service worker console: `chrome://extensions` → Details → Service Worker

**Keyboard shortcut not working**
- Verify at `chrome://extensions/shortcuts`
- Check for conflicts with other extensions

**Content not extracting from important tabs**
- Cannot access chrome:// or other extension pages
- Check page console (F12) for content script errors

## Configuration

Create `.env` file with:

```env
# Required
OPENAI_API_KEY=your_key_here
YOU_API_KEY=your_key_here

# Optional
OPENAI_LLM_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
USE_NEO4J=false
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
DB_PATH=./data/knowledge_graph.db
```

## API Documentation

Backend runs at `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

Key endpoints:
- `POST /api/tabs/ingest` - Send tabs for clustering
- `GET /api/tabs/clusters` - Get tab groups
- `GET /api/recommendations` - Get content suggestions

See [PRD.md](./PRD.md) for complete specifications.

## License

MIT
