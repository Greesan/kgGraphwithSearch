# Deployment Guide - Entity Enrichment Refactor

## Pre-Deployment Checklist

- [ ] Review `REFACTOR_SUMMARY.md` for changes overview
- [ ] Ensure `.env` file has required API keys (`OPENAI_API_KEY`, `YOU_API_KEY`)
- [ ] Backup current database: `cp data/knowledge_graph.db data/knowledge_graph.db.backup`
- [ ] Run tests: `uv run python test_async_refactor.py`

---

## Deployment Steps

### Step 1: Stop Running Backend (if using Docker)
```bash
docker compose down
```

Or if running manually:
```bash
# Find and kill the uvicorn process
pkill -f uvicorn
```

### Step 2: Deploy Code Changes
```bash
# Already done - you're on the branch with changes
git status  # Verify modified files
```

### Step 3: Configure Settings (Optional)
Add to `.env` if you want to customize:
```bash
# Enable/disable background enrichment
ENABLE_BACKGROUND_ENRICHMENT=true

# Batch size for enrichment (how many entities to process at once)
ENRICHMENT_BATCH_SIZE=20

# Timeout for individual enrichment requests
ENRICHMENT_TIMEOUT_SECONDS=30.0
```

### Step 4: Start Backend

**Option A: Docker (Recommended)**
```bash
docker compose up --build
```

**Option B: Manual**
```bash
uv run python -m kg_graph_search.server.app
```

### Step 5: Verify Health
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-10-31T..."
}
```

### Step 6: Test Tab Ingestion
```bash
curl -X POST http://localhost:8000/api/tabs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "tabs": [
      {
        "id": 1,
        "url": "https://example.com",
        "title": "Test Tab",
        "important": false
      }
    ],
    "timestamp": "2025-10-31T00:00:00Z"
  }'
```

Expected: Response in **<2 seconds** (previously 5-10 seconds)

### Step 7: Monitor Logs
```bash
# Docker
docker compose logs -f backend

# Manual
# Logs will appear in terminal
```

Look for:
```
INFO: Queuing X entities for background enrichment
INFO: Background enrichment started for X entities
INFO: Background enrichment completed: X/X entities stored
```

---

## Rollback Plan

If you encounter issues:

### Quick Rollback (No Code Changes)
Disable background enrichment in `.env`:
```bash
ENABLE_BACKGROUND_ENRICHMENT=false
```

Restart backend:
```bash
docker compose restart backend
```

This reverts to synchronous enrichment without code changes.

### Full Rollback (Restore Previous Version)
```bash
# Restore database backup
cp data/knowledge_graph.db.backup data/knowledge_graph.db

# Checkout previous commit
git log  # Find commit hash before refactor
git checkout <previous-commit-hash>

# Rebuild and restart
docker compose up --build
```

---

## Performance Verification

### Before Refactor
```bash
# Time a tab ingestion request
time curl -X POST http://localhost:8000/api/tabs/ingest ...
```
Expected: 5-10 seconds

### After Refactor
```bash
# Same request
time curl -X POST http://localhost:8000/api/tabs/ingest ...
```
Expected: <2 seconds ✅

**Improvement:** 60-80% faster

---

## Monitoring & Observability

### Key Metrics to Watch

1. **API Response Time**
   - `/api/tabs/ingest` should be <2s
   - Check browser extension for snappiness

2. **Background Task Success Rate**
   - Monitor logs for "Background enrichment completed"
   - Check for error patterns

3. **Database Size**
   - Enriched entities should accumulate over time
   - Query: `SELECT COUNT(*) FROM entities WHERE is_enriched = 1`

4. **You.com API Usage**
   - Monitor API quota
   - Check for retry patterns (may indicate API issues)

### Sample Queries
```sql
-- Check enrichment status
SELECT
    COUNT(*) as total_entities,
    SUM(CASE WHEN is_enriched = 1 THEN 1 ELSE 0 END) as enriched_count,
    ROUND(100.0 * SUM(CASE WHEN is_enriched = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as enrichment_percentage
FROM entities;

-- Recent enrichments
SELECT name, entity_type, enriched_at
FROM entities
WHERE is_enriched = 1
ORDER BY enriched_at DESC
LIMIT 10;

-- Failed enrichments (empty descriptions)
SELECT name, entity_type, web_description
FROM entities
WHERE is_enriched = 0 OR web_description IS NULL
LIMIT 10;
```

---

## Troubleshooting

### Issue: Background enrichment not happening
**Symptoms:** Logs show "Skipping entity enrichment" but no background tasks

**Check:**
```bash
# Verify setting is enabled
grep ENABLE_BACKGROUND_ENRICHMENT .env

# Check if You.com API key is set
grep YOU_API_KEY .env
```

**Fix:** Set `ENABLE_BACKGROUND_ENRICHMENT=true` in `.env`

---

### Issue: SQLite errors about threading
**Symptoms:** `sqlite3.ProgrammingError: SQLite objects created in a thread...`

**Cause:** Background task trying to use main thread's DB connection

**Fix:** This should be handled by the refactor (thread-local connections), but if it occurs:
1. Check logs for stack trace
2. Verify `enrich_entities_in_background()` creates its own `KnowledgeGraphDB` instance
3. Report issue with full error message

---

### Issue: Duplicate enrichment API calls
**Symptoms:** Same entity enriched multiple times in logs

**Cause:** Multiple tab batches arriving simultaneously (race condition)

**Impact:** Wastes API quota but harmless (duplicate-safe)

**Fix (if critical):** Will require distributed locking with Redis (future enhancement)

---

### Issue: Background tasks queuing up
**Symptoms:** Enrichment tasks taking longer and longer

**Check:**
```bash
# Monitor thread pool
# Check CPU/memory usage
docker stats backend
```

**Fix:**
1. Reduce `ENRICHMENT_BATCH_SIZE` to process smaller chunks
2. Increase `ENRICHMENT_TIMEOUT_SECONDS` if API is slow
3. Consider scaling workers if needed

---

## Success Criteria

✅ API `/api/tabs/ingest` responds in <2 seconds
✅ Background enrichment tasks complete successfully (check logs)
✅ Entities show `is_enriched=1` in database
✅ No SQLite threading errors
✅ Browser extension feels snappier
✅ No increase in error rates

---

## Post-Deployment

### Week 1: Monitor
- Check logs daily for errors
- Verify enrichment success rate
- Monitor API usage/costs
- Get user feedback on performance

### Week 2: Optimize
- Adjust `ENRICHMENT_BATCH_SIZE` based on load
- Fine-tune retry logic if needed
- Consider adding enrichment status API

### Long-term: Consider Enhancements
- Add job queue (Celery + Redis) for better scaling
- Implement distributed locking for multi-worker setups
- Add enrichment progress API endpoint
- Full async/await refactor (if needed for scale)

---

## Support

If you encounter issues not covered here:

1. Check logs for detailed error messages
2. Review `REFACTOR_SUMMARY.md` for implementation details
3. Run `uv run python test_async_refactor.py` to verify core functionality
4. Use rollback plan to restore stability
5. Document issue for future improvement

---

**Deployment Date:** 2025-10-31
**Version:** 0.1.0
**Status:** ✅ Ready for production
