# TabGraph Testing Guide

## Quick Start (5 minutes)

### Option A: Full Test (With API Keys)

**1. Set up environment:**
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your keys:
# - OPENAI_API_KEY=sk-...
# - YOU_API_KEY=... (optional for now)
```

**2. Start the backend server:**
```bash
uv run python examples/start_server.py
```

You should see:
```
================================================================================
TabGraph Backend Server
================================================================================

✓ Configuration loaded
  - OpenAI Model: gpt-4o-mini
  - Embedding Model: text-embedding-3-small
  - Database: ./data/knowledge_graph.db

Starting FastAPI server...
Server will be available at: http://localhost:8000
```

**3. Load the extension:**

1. Open Chrome/Brave/Arc
2. Go to `chrome://extensions`
3. Enable "Developer mode" (toggle in top-right)
4. Click "Load unpacked"
5. Navigate to and select: `/var/tmp/vibe-kanban/worktrees/26b0-you-take-the-prd/extension/`
6. The TabGraph icon should appear in your toolbar

**4. Test the extension:**

1. **Open 10+ tabs** on different topics. Try:
   - 5 tabs about React/JavaScript (react.dev, MDN, etc.)
   - 5 tabs about databases (neo4j.com, postgres docs)
   - 5 tabs about Python (python.org, pandas docs)

2. **Click the TabGraph extension icon** in toolbar
   - You should see the popup with stats (0 groups initially)

3. **Click the sync button (↻)** in popup
   - Button should re-enable in 2 seconds
   - Watch your Chrome tabs!
   - Tab Groups should appear within 3-5 seconds

4. **Check the grouping:**
   - React tabs should be grouped together
   - Database tabs in another group
   - Python tabs in a third group

5. **Test keyboard shortcut:**
   - Focus on any tab
   - Press `Ctrl+Shift+I` (Mac: `Cmd+Shift+I`)
   - Check background console: Should log "Tab X marked as IMPORTANT"

**5. Check the console logs:**

Open background service worker console:
1. Go to `chrome://extensions`
2. Find TabGraph → Click "Details"
3. Find "Service Worker" section → Click "service worker"
4. Console should show:
   ```
   Collected 15 tabs, sending to backend...
   Cache stats: 0 hits, 15 misses
   Tabs ingested: {status: 'success', processed: 15}
   Received 3 clusters from backend
   Updated group "React Development" with 5 tabs
   Updated group "Database Research" with 5 tabs
   Updated group "Python Programming" with 5 tabs
   ```

**6. Test caching (second sync):**

1. Click sync button again
2. Check console - should see:
   ```
   Cache stats: 15 hits, 0 misses  ← All tabs cached!
   ```
3. Grouping should be much faster (~0.5 seconds)

---

### Option B: Backend-Only Test (No Extension)

If you want to test just the backend API:

**1. Start server** (with .env file)

**2. Test API endpoints:**

```bash
# Health check
curl http://localhost:8000/health

# Ingest sample tabs
curl -X POST http://localhost:8000/api/tabs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "tabs": [
      {"id": 1, "url": "https://react.dev", "title": "React Documentation"},
      {"id": 2, "url": "https://neo4j.com", "title": "Neo4j Graph Database"},
      {"id": 3, "url": "https://react.dev/learn", "title": "Learn React"}
    ],
    "timestamp": "2025-10-28T10:00:00Z"
  }'

# Get clusters
curl http://localhost:8000/api/clusters
```

**3. Check OpenAPI docs:**
Open browser to http://localhost:8000/docs

---

### Option C: Test Without API Keys (Tests Only)

Run the test suite without needing real API keys:

```bash
# Run all backend tests (uses mocks)
uv run pytest tests/backend/ -v

# Run specific test
uv run pytest tests/backend/test_api_endpoints.py::TestTabsIngestEndpoint::test_ingest_tabs_returns_success -v
```

Expected: **10/11 tests passing**

---

## Detailed Testing Steps

### Performance Testing

**Test batch embedding optimization:**

1. Open 50+ tabs (more = better test)
2. Click sync
3. Watch background console
4. First sync: Should take ~2-3 seconds
5. Second sync: Should take ~0.5 seconds (cache hits!)

**Expected console output:**

```
First sync:
  Collected 50 tabs, sending to backend...
  Cache stats: 0 hits, 50 misses          ← No cache yet
  [~2-3 second pause]
  Received 3 clusters from backend

Second sync:
  Collected 50 tabs, sending to backend...
  Cache stats: 48 hits, 2 misses          ← Cache working!
  [~0.5 second pause]
  Received 3 clusters from backend
```

### Feature Testing

**1. Automatic Grouping:**
- Open tabs on 3 different topics
- Click sync
- Chrome should create 3 Tab Groups automatically
- Each group should have a descriptive name

**2. Keyboard Shortcut:**
- Focus on any tab
- Press `Ctrl+Shift+I`
- Tab should be marked as important
- Check background console for confirmation

**3. Important Tab Content Extraction:**
- Mark a tab as important
- Background should send message to content script
- Content script extracts first 10k chars
- Sends to backend for deep analysis

**4. Popup UI:**
- Click extension icon
- Should show:
  - Number of tab groups
  - Total tabs
  - Important tabs count
  - List of groups with tab counts

**5. Manual Sync:**
- Click sync button (↻)
- Button should gray out for 2 seconds
- UI should remain responsive
- Groups update progressively

---

## Troubleshooting

### "Unable to connect to backend"

**Problem:** Popup shows error message

**Solution:**
1. Make sure backend is running: `uv run python examples/start_server.py`
2. Check it's on port 8000: `curl http://localhost:8000/health`
3. Look for CORS errors in browser console

### "Configuration error: Field required"

**Problem:** Server won't start

**Solution:**
```bash
# Make sure .env exists
ls .env

# Check it has required keys
cat .env | grep OPENAI_API_KEY
cat .env | grep YOU_API_KEY

# If missing, add them
echo 'OPENAI_API_KEY=sk-your-key-here' >> .env
echo 'YOU_API_KEY=your-key-here' >> .env
```

### Extension not loading

**Problem:** Chrome says "Manifest file is invalid"

**Solution:**
1. Make sure you selected the `extension/` directory
2. Check `extension/manifest.json` exists
3. Try: Remove extension → Reload Chrome → Load again

### Tabs not grouping

**Problem:** Sync completes but no groups appear

**Solution:**
1. Check background console for errors
2. Make sure you have 10+ tabs (clustering needs volume)
3. Try tabs on very different topics (React vs Python vs Databases)
4. Check backend logs for clustering output

### Service worker not found

**Problem:** Can't find background console

**Solution:**
1. Go to `chrome://extensions`
2. Find TabGraph
3. Click "Details" button
4. Scroll down to "Inspect views"
5. Click "service worker" link

### Keyboard shortcut not working

**Problem:** Ctrl+Shift+I doesn't mark tab

**Solution:**
1. Check `chrome://extensions/shortcuts`
2. Make sure "Mark current tab as important" is enabled
3. Try different tab (some tabs can't be accessed)
4. Check for conflicts with other extensions

---

## Performance Benchmarks

Expected timings on a typical machine:

| Operation | First Run | Cached Run |
|-----------|-----------|------------|
| 10 tabs | 1.5s | 0.3s |
| 50 tabs | 2.3s | 0.6s |
| 100 tabs | 3.5s | 0.9s |

**If slower:**
- Check network latency to OpenAI API
- Check CPU usage (clustering is compute-heavy)
- Make sure backend isn't rate-limited

---

## What to Look For

### ✅ Success Indicators

1. **Backend console:**
   ```
   INFO:     127.0.0.1:XXXXX - "POST /api/tabs/ingest HTTP/1.1" 200 OK
   ```

2. **Extension console:**
   ```
   Tabs ingested: {status: 'success', processed: 50}
   Cache stats: 45 hits, 5 misses
   Updated group "React Development" with 5 tabs
   ```

3. **Chrome UI:**
   - Tab Groups appear with colored labels
   - Groups have descriptive names
   - Tabs are correctly categorized

4. **Popup UI:**
   - Shows accurate counts
   - Lists all groups
   - Sync button works

### ❌ Failure Indicators

1. **CORS errors** in console:
   ```
   Access-Control-Allow-Origin blocked
   ```
   → Backend needs CORS middleware (should already have it)

2. **API errors:**
   ```
   Failed to generate embedding: 401 Unauthorized
   ```
   → Check OPENAI_API_KEY is valid

3. **No clusters created:**
   ```
   Received 0 clusters from backend
   ```
   → Not enough tabs or all tabs too similar

---

## Next Steps After Testing

Once you verify everything works:

1. **Adjust monitoring interval** (optional):
   - Edit `extension/background.js`
   - Change `MONITOR_INTERVAL` from 5 min to your preference

2. **Customize colors** (optional):
   - Backend assigns colors automatically
   - Can customize in `tab_clusterer.py` color pool

3. **Add more test tabs**:
   - Try edge cases (very similar tabs, very different tabs)
   - Test with 100+ tabs to see scalability

4. **Monitor costs**:
   - Check OpenAI usage dashboard
   - Should see reduced API calls with caching

---

## Getting Help

If something doesn't work:

1. **Check logs:**
   - Backend: Terminal where server is running
   - Extension: Background service worker console
   - Popup: Right-click icon → Inspect

2. **Run tests:**
   ```bash
   uv run pytest tests/backend/ -v
   ```

3. **Check documentation:**
   - `extension/README.md` - Extension usage
   - `STREAM_4_SUMMARY.md` - Implementation details
   - `PERFORMANCE_OPTIMIZATIONS.md` - Performance guide

4. **Common issues in `STREAM_4_SUMMARY.md`** - See Troubleshooting section

---

## Expected Costs

For testing with 50 tabs:
- First sync: ~$0.001 (1 tenth of a cent)
- Subsequent syncs: ~$0.0001 (much cheaper with cache)

**Total for 1 hour of testing: < $0.01**

You won't break the bank testing this! 😊
