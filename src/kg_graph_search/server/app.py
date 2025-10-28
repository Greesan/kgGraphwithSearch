"""
FastAPI application for TabGraph backend.

This server provides endpoints for:
- Tab ingestion and analysis
- Cluster retrieval
- Content recommendations
"""

import uuid
from datetime import datetime, UTC
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.server.models import (
    TabsIngestRequest,
    TabsIngestResponse,
    TabsClustersResponse,
    RecommendationsResponse,
    HealthResponse,
    ClusterResponse,
    TabResponse,
    TabRelationship,
)

# ============================================================================
# FastAPI App Initialization
# ============================================================================

app = FastAPI(
    title="TabGraph API",
    description="AI-powered tab management with temporal knowledge graph",
    version="0.1.0",
)

# CORS middleware for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://*",
        "http://localhost:*",
        "https://localhost:*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global State (In-memory for now)
# ============================================================================

# In a production app, this would be in a database or cache
# For MVP, we keep it simple with in-memory storage
_clusterer: TabClusterer | None = None
_session_id: str = str(uuid.uuid4())


def get_clusterer() -> TabClusterer:
    """Get or create the global TabClusterer instance."""
    global _clusterer
    if _clusterer is None:
        _clusterer = TabClusterer(
            similarity_threshold=0.75,
            rename_threshold=3,
        )
    return _clusterer


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/api/tabs/ingest", response_model=TabsIngestResponse)
async def ingest_tabs(request: TabsIngestRequest):
    """
    Ingest tabs from browser extension for analysis and clustering.

    This endpoint:
    1. Receives tab metadata from the extension
    2. Generates embeddings for ALL tabs in one batch API call (10x faster!)
    3. Assigns tabs to clusters or creates new ones
    4. Returns processing summary

    Args:
        request: Tab data with metadata

    Returns:
        Processing summary with session ID
    """
    clusterer = get_clusterer()

    important_count = 0
    tabs = []

    # Convert input tabs to internal Tab model
    for tab_input in request.tabs:
        # Create Tab model
        tab = Tab(
            id=tab_input.id,
            url=tab_input.url,
            title=tab_input.title,
            favicon_url=tab_input.favicon_url,
            window_id=tab_input.window_id,
            group_id=tab_input.group_id,
        )

        # Count important tabs
        if tab_input.important:
            important_count += 1

        tabs.append(tab)

    # Process all tabs in batch (generates embeddings in single API call)
    clusterer.process_tabs_batch(tabs)

    return TabsIngestResponse(
        status="success",
        processed=len(request.tabs),
        important_tabs=important_count,
        session_id=_session_id,
    )


@app.get("/api/tabs/clusters", response_model=TabsClustersResponse)
async def get_clusters():
    """
    Get current tab clusters with their tabs and relationships.

    Returns:
        All active clusters with tab assignments
    """
    clusterer = get_clusterer()
    clusters = clusterer.get_all_clusters()

    # Convert to response model
    cluster_responses = []
    relationships = []

    for cluster in clusters:
        # Convert tabs to response model
        tab_responses = [
            TabResponse(
                id=tab.id,
                title=tab.title,
                url=tab.url,
                important=False,  # TODO: Track important flag
                entities=tab.entities,
            )
            for tab in cluster.tabs
        ]

        cluster_responses.append(
            ClusterResponse(
                id=cluster.id,
                name=cluster.name,
                color=cluster.color.value,
                tabs=tab_responses,
                shared_entities=cluster.shared_entities,
                tab_count=cluster.tab_count,
            )
        )

    return TabsClustersResponse(
        clusters=cluster_responses,
        relationships=relationships,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.get("/api/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(cluster_id: str | None = None, limit: int = 10):
    """
    Get content recommendations based on current knowledge graph.

    This is a stub for MVP - will be implemented in Phase 2.

    Args:
        cluster_id: Optional cluster ID to filter recommendations
        limit: Maximum recommendations to return

    Returns:
        List of recommended content
    """
    # TODO: Implement recommendations using You.com APIs
    # For now, return empty list
    return RecommendationsResponse(
        recommendations=[],
        total=0,
    )
