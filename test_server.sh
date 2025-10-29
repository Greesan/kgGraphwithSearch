#!/bin/bash

# Test script for the TabGraph server

echo "🚀 Starting TabGraph server..."
echo "================================"
echo ""

# Start server in background
uv run uvicorn src.kg_graph_search.server.app:app --reload --port 8000 &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

echo "✅ Server started on http://localhost:8000"
echo ""
echo "📖 Available endpoints:"
echo "  - Health: http://localhost:8000/health"
echo "  - Docs: http://localhost:8000/docs"
echo "  - POST /api/tabs/ingest - Send tabs"
echo "  - GET /api/tabs/clusters - Get clusters"
echo "  - GET /api/graph/visualization - Get graph data"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Wait for Ctrl+C
wait $SERVER_PID
