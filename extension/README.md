# TabGraph Browser Extension

AI-powered tab management with automatic clustering and Chrome Tab Groups integration.

## Features

- ✅ **Automatic Tab Grouping**: Tabs are automatically clustered by semantic similarity
- ✅ **Chrome Tab Groups Integration**: Creates native Chrome tab groups based on clusters
- ✅ **Keyboard Shortcut**: `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) to mark tabs as important
- ✅ **Periodic Monitoring**: Checks tabs every 5 minutes and updates groupings
- ✅ **Content Extraction**: Deep analysis for important tabs
- ✅ **Simple Popup UI**: Quick overview of tab groups and statistics

## Installation

### Prerequisites

1. **Backend Server Running**
   - The extension requires the TabGraph backend server to be running
   - Start it with: `uv run python examples/start_server.py`
   - Server should be accessible at `http://localhost:8000`

2. **Chromium-Based Browser**
   - Chrome, Brave, Edge, Arc, or any Chromium-based browser

### Loading the Extension

1. Open your browser and navigate to:
   - Chrome: `chrome://extensions`
   - Brave: `brave://extensions`
   - Edge: `edge://extensions`

2. Enable **Developer mode** (toggle in top-right corner)

3. Click **"Load unpacked"**

4. Navigate to and select the `extension/` directory

5. The TabGraph icon should appear in your extensions toolbar

## Usage

### Basic Workflow

1. **Open Multiple Tabs** (10+)
   - Open tabs on different topics (e.g., React docs, Neo4j docs, Python tutorials)

2. **Click the Extension Icon**
   - View statistics: number of groups, total tabs, important tabs
   - See your tab groups listed

3. **Wait for Auto-Sync** (5 minutes)
   - Or click the refresh button (↻) in the popup to sync immediately
   - The extension will send tab data to the backend
   - Backend clusters tabs by semantic similarity
   - Chrome Tab Groups are created/updated automatically

4. **Mark Important Tabs**
   - Press `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) on any tab
   - The tab will be marked for deep content analysis
   - Content will be extracted and sent to backend

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`) | Mark/unmark current tab as important |

## Architecture

### Files

```
extension/
├── manifest.json           # Extension configuration
├── background.js           # Service worker (tab monitoring, clustering)
├── content.js              # Content extraction script
├── popup/
│   ├── popup.html         # Popup UI
│   ├── popup.css          # Popup styling
│   └── popup.js           # Popup logic
└── icons/
    ├── icon-16.png
    ├── icon-48.png
    └── icon-128.png
```

### Data Flow

```
1. background.js monitors all tabs every 5 minutes
   ↓
2. Sends tab metadata to POST /api/tabs/ingest
   ↓
3. Backend clusters tabs by similarity
   ↓
4. Extension fetches GET /api/tabs/clusters
   ↓
5. background.js creates/updates Chrome Tab Groups
   ↓
6. User sees tabs organized in native Chrome groups
```

### Important Tab Flow

```
1. User presses Ctrl+Shift+I on active tab
   ↓
2. background.js marks tab as important
   ↓
3. content.js extracts page content (10k chars)
   ↓
4. Content sent to backend for deep analysis
   ↓
5. Backend generates entities and relationships
```

## Configuration

The extension connects to `http://localhost:8000` by default.

To change the backend URL, edit `BACKEND_URL` in:
- `extension/background.js`
- `extension/popup/popup.js`

## Troubleshooting

### Extension Icon Shows Error

**Problem**: Popup shows "Unable to connect to backend"

**Solution**:
1. Ensure backend server is running: `uv run python examples/start_server.py`
2. Check server is accessible at `http://localhost:8000`
3. Check browser console for CORS errors

### Tabs Not Grouping

**Problem**: Tabs aren't being automatically grouped

**Solution**:
1. Click the refresh (↻) button in popup to force sync
2. Check you have 10+ tabs open (clustering works better with more tabs)
3. Open background service worker console (chrome://extensions → Details → Service Worker)
4. Look for errors in console

### Keyboard Shortcut Not Working

**Problem**: `Ctrl+Shift+I` doesn't mark tab as important

**Solution**:
1. Check chrome://extensions/shortcuts
2. Verify the shortcut is enabled for TabGraph
3. Check for conflicts with other extensions

### Content Not Extracting

**Problem**: Important tabs don't seem to extract content

**Solution**:
1. Check the page isn't a chrome:// or extension page (these can't be accessed)
2. Open the page's console (F12) and look for errors
3. Verify content.js is loaded (check Sources tab in DevTools)

## Development

### Testing

Run backend API tests:
```bash
uv run pytest tests/backend/ -v
```

### Debugging

1. **Background Script Console**:
   - Go to `chrome://extensions`
   - Find TabGraph → Details
   - Click "Service Worker" to open console

2. **Content Script Console**:
   - Open any page
   - Press F12
   - Look for "TabGraph content script loaded" message

3. **Popup Console**:
   - Right-click extension icon → Inspect popup
   - Console will show popup script logs

## Limitations

- Requires backend server to be running locally
- Tab monitoring runs every 5 minutes (not real-time)
- Content extraction limited to 10,000 characters
- Cannot access chrome:// pages or other extensions
- Clustering quality depends on having sufficient tabs (10+)

## Next Steps

**Planned Features** (not yet implemented):
- Full graph visualization page
- Recommendations panel
- Settings page (adjust monitoring interval)
- Privacy controls (exclude domains)
- Historical session tracking

See `PRD.md` for complete feature roadmap.

## License

MIT License
