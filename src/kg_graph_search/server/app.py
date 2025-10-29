"""
FastAPI application for TabGraph backend.

This server provides endpoints for:
- Tab ingestion and analysis
- Cluster retrieval
- Content recommendations
- Graph visualization
"""

import uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.server.models import (
    TabsIngestRequest,
    TabsIngestResponse,
    TabsClustersResponse,
    RecommendationsResponse,
    HealthResponse,
    ClusterResponse,
    TabResponse,
    TabRelationship,
    GraphVisualizationResponse,
    GraphNode,
    GraphNodeData,
    GraphEdge,
    GraphEdgeData,
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
_graph_db: KnowledgeGraphDB | None = None
_session_id: str = str(uuid.uuid4())


def get_graph_db() -> KnowledgeGraphDB:
    """Get or create the global KnowledgeGraphDB instance."""
    global _graph_db
    if _graph_db is None:
        db_path = Path("./data/knowledge_graph.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _graph_db = KnowledgeGraphDB(db_path)
    return _graph_db


def get_clusterer() -> TabClusterer:
    """Get or create the global TabClusterer instance with knowledge graph."""
    global _clusterer
    if _clusterer is None:
        graph_db = get_graph_db()
        _clusterer = TabClusterer(
            similarity_threshold=0.50,  # Lower threshold for hybrid scoring
            rename_threshold=3,
            graph_db=graph_db,
            entity_weight=0.5,  # 50% embeddings, 50% entities
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

    Only returns clusters with 2+ tabs (single-tab clusters are filtered out).

    Returns:
        All active clusters with tab assignments
    """
    clusterer = get_clusterer()
    clusters = clusterer.get_all_clusters()

    # Filter out single-tab clusters (no need to create tab groups for singletons)
    multi_tab_clusters = [c for c in clusters if c.tab_count >= 2]

    # Convert to response model
    cluster_responses = []
    relationships = []

    for cluster in multi_tab_clusters:
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


@app.get("/api/graph/visualization", response_model=GraphVisualizationResponse)
async def get_graph_visualization(
    include_singletons: bool = Query(
        default=False, description="Include tabs not in any cluster"
    ),
    time_range_hours: int | None = Query(
        default=None, description="Only tabs opened in last N hours"
    ),
    min_cluster_size: int = Query(
        default=2, description="Minimum tabs per cluster to show"
    ),
):
    """
    Get graph visualization data for Cytoscape.js rendering.

    Returns a simplified graph with:
    - Cluster nodes (colored circles with tab count)
    - Tab nodes (orbiting their parent cluster)
    - Edges connecting tabs to clusters

    Args:
        include_singletons: Include unclustered tabs (default: false)
        time_range_hours: Only include tabs from last N hours (default: all active)
        min_cluster_size: Minimum tabs per cluster (default: 2)

    Returns:
        Cytoscape.js-compatible graph data
    """
    clusterer = get_clusterer()
    clusters = clusterer.get_all_clusters()

    # Filter by time range if specified
    if time_range_hours is not None:
        cutoff_time = datetime.now(UTC) - timedelta(hours=time_range_hours)
        # Filter clusters to only include recent tabs
        filtered_clusters = []
        for cluster in clusters:
            recent_tabs = [
                tab
                for tab in cluster.tabs
                if tab.created_at >= cutoff_time
            ]
            if len(recent_tabs) >= min_cluster_size:
                # Create a filtered cluster
                filtered_cluster = cluster.model_copy()
                filtered_cluster.tabs = recent_tabs
                filtered_cluster.tab_count = len(recent_tabs)
                filtered_clusters.append(filtered_cluster)
        clusters = filtered_clusters
    else:
        # Filter by minimum cluster size only
        clusters = [c for c in clusters if c.tab_count >= min_cluster_size]

    nodes = []
    edges = []

    # Create cluster nodes and tab nodes
    for cluster in clusters:
        # Add cluster node
        cluster_node = GraphNode(
            data=GraphNodeData(
                id=f"cluster_{cluster.id}",
                type="cluster",
                label=cluster.name,
                color=cluster.color.value,
                tab_count=cluster.tab_count,
                shared_entities=cluster.shared_entities[:5],  # Top 5 entities
            )
        )
        nodes.append(cluster_node)

        # Add tab nodes for this cluster
        for tab in cluster.tabs:
            tab_node = GraphNode(
                data=GraphNodeData(
                    id=f"tab_{tab.id}",
                    type="tab",
                    label=tab.title[:50],  # Truncate long titles
                    parent=f"cluster_{cluster.id}",
                    url=tab.url,
                    important=False,  # TODO: Track important flag in Tab model
                    entities=tab.entities,
                    opened_at=tab.created_at.isoformat() if tab.created_at else None,
                )
            )
            nodes.append(tab_node)

            # Add edge from tab to cluster
            edge = GraphEdge(
                data=GraphEdgeData(
                    id=f"edge_tab{tab.id}_cluster{cluster.id}",
                    source=f"tab_{tab.id}",
                    target=f"cluster_{cluster.id}",
                    type="contains",
                )
            )
            edges.append(edge)

    # Handle singleton tabs if requested
    if include_singletons:
        all_clustered_tab_ids = {
            tab.id for cluster in clusters for tab in cluster.tabs
        }
        # Note: We don't have a way to get all tabs yet from clusterer
        # This would need to be implemented if we want singletons
        # For now, singletons are not included

    metadata = {
        "cluster_count": len(clusters),
        "tab_count": sum(c.tab_count for c in clusters),
        "time_range_hours": time_range_hours,
        "include_singletons": include_singletons,
        "min_cluster_size": min_cluster_size,
    }

    return GraphVisualizationResponse(
        nodes=nodes,
        edges=edges,
        timestamp=datetime.now(UTC).isoformat(),
        metadata=metadata,
    )
