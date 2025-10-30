HOLY IT ACTUALLY KINDA WORKS!

<img width="1874" height="1013" alt="image" src="https://github.com/user-attachments/assets/6831e293-b731-4a8a-bdb8-88a5cc711cd6" />


# TabGraph

AI-powered browser extension that automatically organizes tabs into semantic groups using knowledge graphs and web APIs.

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
- Extension auto-groups tabs every 5 minutes (or click refresh in popup)
- Press `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) to mark tabs as important for deep analysis
- View the knowledge graph: `http://localhost:8000/docs`

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
- Click refresh button in popup to force sync
- Check service worker console: `chrome://extensions` → Details → Service Worker → Console

**Keyboard shortcut (`Ctrl+Shift+I`) not working:**
- Verify shortcut at `chrome://extensions/shortcuts`
- Check for conflicts with other extensions or OS shortcuts
- Try clicking extension icon and manually marking tabs as important

**Content not extracting from important tabs:**
- Extension cannot access `chrome://` pages or other extension pages (browser security restriction)
- Check page console (F12) for content script errors
- Ensure page is fully loaded before marking as important

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

## Advanced: Manual Installation (Linux/WSL)

If you prefer not to use Docker or need a development setup:

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv) package manager

**Setup:**
```bash
cd kgGraphwithSearch
uv sync                     # Install dependencies
uv pip install -e .         # Install package in editable mode
cp .env.example .env        # Configure API keys
uv run python -m kg_graph_search.server.app
```

**Note:** This method requires proper Python environment setup and may encounter platform-specific issues. Docker is recommended for most users.

## License

MIT
