# TabGraph Extension Configuration Guide

## Quick Start

All extension settings are in **`extension/config.js`** - just edit this one file!

```javascript
const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',
  MONITOR_INTERVAL_MINUTES: 5,
  SIMILARITY_THRESHOLD: 0.70,
};
```

## Configuration Options

### `BACKEND_URL`
**Default:** `'http://localhost:8000'`

Where the TabGraph backend server is running.

**Examples:**
- Local with different port: `'http://localhost:3000'`
- Remote server: `'http://192.168.1.100:8000'`
- HTTPS: `'https://tabgraph.example.com'`

### `MONITOR_INTERVAL_MINUTES`
**Default:** `5`

How often the extension checks tabs and updates grouping (in minutes).

**Examples:**
- More frequent: `2` (every 2 minutes)
- Less frequent: `10` (every 10 minutes)
- Manual only: `999` (effectively disables auto-sync, use refresh button only)

### `SIMILARITY_THRESHOLD`
**Default:** `0.70`

How similar tabs need to be to group together (0.0 - 1.0).

- **Lower (0.60-0.65):** More general grouping, more tabs per group
- **Medium (0.70-0.75):** Balanced grouping (recommended)
- **Higher (0.80-0.90):** Very specific grouping, more groups with fewer tabs

**Note:** This should match the backend setting in `src/kg_graph_search/server/app.py`.

## Browser Compatibility

The extension works on **all Chromium-based browsers** without code changes:
- Google Chrome
- Microsoft Edge
- Brave
- Arc
- Vivaldi
- Any Chromium-based browser

Just load the extension in `chrome://extensions` (or equivalent).

## After Making Changes

1. Edit `extension/config.js`
2. Go to `chrome://extensions`
3. Click the reload icon (↻) on the TabGraph extension
4. Done!

No need to restart the browser or backend server.
