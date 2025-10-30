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

from kg_graph_search.config import get_logger, get_settings
from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB

logger = get_logger(__name__)
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
                important=tab.important,
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
    Get intelligent content recommendations using You.com Express Agent.

    Uses AI reasoning to provide contextualized recommendations based on
    the user's current research topics and knowledge graph.

    Args:
        cluster_id: Optional cluster ID for targeted recommendations
        limit: Maximum recommendations to return

    Returns:
        List of intelligent recommendations with reasoning
    """
    clusterer = get_clusterer()
    settings = get_settings()

    # Check if You.com API is configured
    if not settings.you_api_key:
        logger.warning("You.com API key not configured - returning empty recommendations")
        return RecommendationsResponse(recommendations=[], total=0)

    try:
        from kg_graph_search.search.you_client import YouAPIClient

        you_client = YouAPIClient(settings.you_api_key)

        # Get cluster context and discover relationships (on-demand)
        if cluster_id:
            cluster = clusterer.get_cluster_by_id(cluster_id)
            if not cluster:
                return RecommendationsResponse(recommendations=[], total=0)

            # Build context from specific cluster with shared entities
            query_context = f"researching {cluster.name} with focus on: {', '.join(cluster.shared_entities[:5])}"
        else:
            # Build context from all clusters
            clusters = clusterer.get_all_clusters()
            if not clusters:
                return RecommendationsResponse(recommendations=[], total=0)

            top_clusters = sorted(clusters, key=lambda c: c.tab_count, reverse=True)[:3]
            topics = [c.name for c in top_clusters]
            query_context = f"researching topics: {', '.join(topics)}"

        # Use Express Agent for intelligent recommendations
        agent_query = f"What are the best resources, tutorials, and articles for someone {query_context}? Suggest {limit} high-quality, current resources."

        agent_response = you_client.express_agent_search(agent_query)

        # Parse agent response
        recommendations = []

        # Extract answer and search results from agent output
        answer_text = ""
        search_results = []

        for output in agent_response.get("output", []):
            # Handle both "chat_node.answer" and "message.answer" types
            if output.get("type") in ["chat_node.answer", "message.answer"]:
                answer_text = output.get("text", "")
            elif output.get("type") == "web_search.results":
                # Agent includes search results in response
                search_results = output.get("results", [])

        # Convert search results to recommendations
        for idx, result in enumerate(search_results[:limit]):
            recommendations.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", "")[:200],
                "reason": f"Recommended by AI: {answer_text[:100]}..." if answer_text else "Relevant to your research",
                "relevance_score": 1.0 - (idx * 0.1),  # Descending relevance
                "source": "you_express_agent",
                "cluster_id": cluster_id,
                "is_news": False,
            })

        you_client.close()

        return RecommendationsResponse(
            recommendations=recommendations,
            total=len(recommendations),
        )

    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        # Graceful fallback
        return RecommendationsResponse(recommendations=[], total=0)


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
    entity_nodes_map = {}  # Track entities: {entity_name: {id, cluster_ids}}

    # Create cluster nodes and tab nodes
    for cluster in clusters:
        cluster_id = f"cluster_{cluster.id}"

        # Add cluster node
        cluster_node = GraphNode(
            data=GraphNodeData(
                id=cluster_id,
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
            tab_id = f"tab_{tab.id}"

            tab_node = GraphNode(
                data=GraphNodeData(
                    id=tab_id,
                    type="tab",
                    label=tab.title[:50],  # Truncate long titles
                    # DO NOT set parent - causes compound nodes (boxes)
                    # Store cluster info for entity view color-coding
                    cluster_id=cluster_id,  # Custom field for entity view
                    color=cluster.color.value,  # Store cluster color
                    url=tab.url,
                    important=tab.important,
                    entities=tab.entities,
                    opened_at=tab.created_at.isoformat() if tab.created_at else None,
                )
            )
            nodes.append(tab_node)

            # Add edge from cluster to tab (high weight for cluster view)
            edge = GraphEdge(
                data=GraphEdgeData(
                    id=f"edge_cluster{cluster.id}_tab{tab.id}",
                    source=cluster_id,
                    target=tab_id,
                    type="contains",
                    weight=10.0,  # High weight keeps tabs near cluster
                )
            )
            edges.append(edge)

            # Track entities for this tab
            for entity_name in tab.entities:
                if entity_name not in entity_nodes_map:
                    entity_nodes_map[entity_name] = {
                        "cluster_ids": set(),
                        "tab_ids": set()
                    }
                entity_nodes_map[entity_name]["cluster_ids"].add(cluster_id)
                entity_nodes_map[entity_name]["tab_ids"].add(tab_id)

    # Add entity nodes
    graph_db = get_graph_db()
    logger.info(f"Adding {len(entity_nodes_map)} entity nodes to graph")

    for entity_name, entity_info in entity_nodes_map.items():
        # Fetch entity from database to get enrichment data
        entity = graph_db.get_entity_by_name(entity_name)
        entity_id = f"entity_{entity.id}" if entity else f"entity_{hash(entity_name) % 100000}"

        entity_node = GraphNode(
            data=GraphNodeData(
                id=entity_id,
                type="entity",
                label=entity_name,
                description=entity.web_description if entity and entity.web_description else None,
                cluster_ids=list(entity_info["cluster_ids"]),
            )
        )
        nodes.append(entity_node)
        logger.debug(f"Added entity node: {entity_name} ({entity_id})")

        # Add edges from tabs to this entity
        for tab_id in entity_info["tab_ids"]:
            edge = GraphEdge(
                data=GraphEdgeData(
                    id=f"edge_{tab_id}_{entity_id}",
                    source=tab_id,
                    target=entity_id,
                    type="references",
                    weight=1.0,  # Low weight for entity view
                )
            )
            edges.append(edge)

    # Add entity-entity relationship edges (from knowledge graph triplets)
    if graph_db:
        try:
            # Get top relationships between entities in this graph
            entity_ids_in_graph = [
                entity.id for entity_name in entity_nodes_map.keys()
                if (entity := graph_db.get_entity_by_name(entity_name))
            ]

            # Fetch triplets between these entities (limit to prevent overcrowding)
            triplets = graph_db.get_all_triplets(limit=50)

            for triplet in triplets:
                subject_id = f"entity_{triplet.subject_id}"
                object_id = f"entity_{triplet.object_id}"

                # Only add edge if both entities are in our graph
                if any(n.data.id == subject_id for n in nodes) and any(n.data.id == object_id for n in nodes):
                    edge = GraphEdge(
                        data=GraphEdgeData(
                            id=f"edge_rel_{triplet.subject_id}_{triplet.object_id}",
                            source=subject_id,
                            target=object_id,
                            type="relationship",
                            label=triplet.predicate[:20],  # Truncate long predicates
                            weight=triplet.confidence,
                            confidence=triplet.confidence,
                        )
                    )
                    edges.append(edge)
        except Exception as e:
            logger.warning(f"Failed to fetch entity relationships: {e}")

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
        "entity_count": len(entity_nodes_map),
        "relationship_count": len([e for e in edges if e.data.type == "relationship"]),
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
