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
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from kg_graph_search.config import get_logger, get_settings
from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.agents.entity_enricher import EntityEnricher
from kg_graph_search.search.you_client import YouAPIClient

logger = get_logger(__name__)
from kg_graph_search.server.models import (
    TabsIngestRequest,
    TabsIngestResponse,
    TabsDeleteRequest,
    TabsDeleteResponse,
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
# Background Tasks
# ============================================================================


def enrich_entities_in_background(
    entity_names: list[str],
    db_path: Path,
    you_api_key: str,
) -> None:
    """
    Enrich entities in a background thread with thread-local resources.

    This function creates its own database connection and API clients to avoid
    SQLite thread-safety issues and resource sharing conflicts.

    Args:
        entity_names: List of entity names to enrich
        db_path: Path to SQLite database
        you_api_key: You.com API key

    Note:
        This runs in a separate thread via FastAPI BackgroundTasks.
        All resources are thread-local and cleaned up after completion.
    """
    if not entity_names:
        logger.debug("No entities to enrich in background")
        return

    logger.info(f"Background enrichment started for {len(entity_names)} entities")

    # Create thread-local database connection (SQLite requirement)
    graph_db = None
    you_client = None
    enricher = None

    try:
        # Initialize thread-local resources
        graph_db = KnowledgeGraphDB(db_path)
        you_client = YouAPIClient(you_api_key)
        enricher = EntityEnricher(you_client, cache_ttl_days=7)

        # Batch fetch to check which entities actually need enrichment
        # (Avoid duplicate work if multiple requests came in)
        existing_entities = graph_db.get_entities_by_names(entity_names)
        enriched_names = {e.name for e in existing_entities if e.is_enriched}

        # Filter to only unenriched entities
        entities_to_enrich = [
            name for name in entity_names
            if name not in enriched_names
        ]

        if not entities_to_enrich:
            logger.info("Background enrichment: All entities already enriched")
            return

        logger.info(f"Background enrichment: Enriching {len(entities_to_enrich)} new entities")

        # Enrich entities (includes retry logic from EntityEnricher)
        enriched_data = enricher.enrich_entities(entities_to_enrich)

        # Batch generate embeddings for entity names (1 API call!)
        from openai import OpenAI
        settings = get_settings()
        openai_client = OpenAI(api_key=settings.openai_api_key)

        logger.info(f"Generating embeddings for {len(entities_to_enrich)} entity names...")
        entity_embeddings_map = {}
        try:
            response = openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=entities_to_enrich
            )
            embeddings = [data.embedding for data in response.data]
            entity_embeddings_map = dict(zip(entities_to_enrich, embeddings))
            logger.debug(f"Generated {len(entity_embeddings_map)} entity embeddings")
        except Exception as e:
            logger.warning(f"Failed to generate entity embeddings in background: {e}")
            # Continue without embeddings

        # Store enriched entities in database (with embeddings)
        from kg_graph_search.graph.models import Entity

        stored_count = 0
        for enrichment in enriched_data:
            if enrichment.get("is_enriched"):
                entity_name = enrichment["name"]
                entity = Entity(
                    name=entity_name,
                    entity_type=enrichment["type"],
                    description=None,
                    web_description=enrichment["description"],
                    related_concepts=enrichment.get("related_concepts", []),
                    source_url=enrichment.get("source_url"),
                    is_enriched=True,
                    enriched_at=datetime.now(UTC),
                    embedding=entity_embeddings_map.get(entity_name),  # Add embedding
                )
                graph_db.add_entity(entity)
                stored_count += 1

        logger.info(f"Background enrichment completed: {stored_count}/{len(entities_to_enrich)} entities stored with embeddings")

    except Exception as e:
        logger.error(
            f"Background enrichment failed: {e}",
            exc_info=True,
            extra={"entity_count": len(entity_names)}
        )
    finally:
        # Clean up thread-local resources
        if you_client:
            you_client.close()
        if graph_db:
            graph_db.close()


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
async def ingest_tabs(request: TabsIngestRequest, background_tasks: BackgroundTasks):
    """
    Ingest tabs from browser extension for analysis and clustering.

    This endpoint:
    1. Receives tab metadata from the extension (GROUND TRUTH from browser)
    2. Reconciles database with browser state (marks closed tabs as inactive)
    3. Generates embeddings for ALL tabs in one batch API call (10x faster!)
    4. Assigns tabs to clusters or creates new ones (FAST - skips enrichment)
    5. Cleans up orphaned entities from closed tabs
    6. Queues entity enrichment for background processing (non-blocking)

    Args:
        request: Tab data with metadata
        background_tasks: FastAPI background tasks for async enrichment

    Returns:
        Processing summary with session ID (returns quickly, enrichment happens in background)
    """
    clusterer = get_clusterer()
    graph_db = get_graph_db()

    important_count = 0
    tabs = []
    cache_hits = 0
    cache_misses = 0

    # Convert input tabs to internal Tab model
    for tab_input in request.tabs:
        # Create Tab model (use cached data if available)
        tab = Tab(
            id=tab_input.id,
            url=tab_input.url,
            title=tab_input.title,
            favicon_url=tab_input.favicon_url,
            window_id=tab_input.window_id,
            group_id=tab_input.group_id,
            embedding=tab_input.embedding,  # From browser cache
            entities=tab_input.entities,     # From browser cache
        )

        # Track cache hits/misses
        if tab_input.embedding and tab_input.entities:
            cache_hits += 1
        else:
            cache_misses += 1

        # Count important tabs
        if tab_input.important:
            important_count += 1

        tabs.append(tab)

    logger.info(f"Cache stats: {cache_hits} hits, {cache_misses} misses")

    # RECONCILIATION: Browser tabs are ground truth
    # Mark any tabs in DB that are NOT in the browser as closed
    active_tab_ids = {tab.id for tab in tabs}
    db_active_tabs = graph_db.get_active_tabs()

    closed_count = 0
    for db_tab in db_active_tabs:
        if db_tab['id'] not in active_tab_ids:
            # Tab was closed in browser but still active in DB
            logger.info(f"Tab {db_tab['id']} closed in browser, marking as inactive: {db_tab['title']}")
            graph_db.close_tab(db_tab['id'])
            clusterer.remove_tab(db_tab['id'])
            closed_count += 1

    # Clean up orphaned entities after removing closed tabs
    orphaned_count = 0
    if closed_count > 0:
        orphaned_count = graph_db.remove_orphaned_entities()
        logger.info(f"Reconciliation: Marked {closed_count} tabs as closed, removed {orphaned_count} orphaned entities")

    # Process all tabs in batch (FAST - skips enrichment for quick response)
    clusterer.process_tabs_batch(tabs, skip_enrichment=True)

    # Queue entity enrichment for background processing
    settings = get_settings()
    if settings.enable_background_enrichment:
        # Collect all unique entity names from processed tabs
        all_entity_names = set()
        for tab in tabs:
            if tab.entities:
                all_entity_names.update(tab.entities)

        if all_entity_names:
            entity_names_list = list(all_entity_names)
            logger.info(f"Queuing {len(entity_names_list)} entities for background enrichment")

            # Add background task (runs in thread pool after response is sent)
            background_tasks.add_task(
                enrich_entities_in_background,
                entity_names=entity_names_list,
                db_path=settings.db_path,
                you_api_key=settings.you_api_key,
            )
        else:
            logger.debug("No entities to enrich in background")
    else:
        logger.debug("Background enrichment disabled in settings")

    # Return tab data for browser caching (embeddings + entities)
    from kg_graph_search.server.models import TabDataResponse
    tab_data_for_cache = [
        TabDataResponse(
            id=tab.id,
            embedding=tab.embedding,
            entities=tab.entities
        )
        for tab in tabs
        if tab.embedding and tab.entities  # Only return successfully processed tabs
    ]

    return TabsIngestResponse(
        status="success",
        processed=len(request.tabs),
        important_tabs=important_count,
        session_id=_session_id,
        tab_data=tab_data_for_cache,  # Data for browser to cache
    )


@app.post("/api/tabs/delete", response_model=TabsDeleteResponse)
async def delete_tabs(request: TabsDeleteRequest):
    """
    Delete tabs from the database and remove orphaned entities.

    This endpoint:
    1. Deletes tabs from the database
    2. Removes tab-entity relationships (via CASCADE)
    3. Identifies entities that are now orphaned (no tab connections)
    4. Deletes orphaned entities and their relationships from the database

    Args:
        request: Tab IDs to delete

    Returns:
        Summary of deleted tabs and entities
    """
    graph_db = get_graph_db()
    clusterer = get_clusterer()

    deleted_count = 0

    # Remove each tab from clusterer (which also deletes from DB)
    for tab_id in request.tab_ids:
        if clusterer.remove_tab(tab_id):
            deleted_count += 1

    # Find and remove orphaned entities
    orphaned_entity_ids = graph_db.get_orphaned_entities()
    deleted_entities = graph_db.remove_orphaned_entities()

    logger.info(f"Deleted {deleted_count} tabs and {deleted_entities} orphaned entities")

    return TabsDeleteResponse(
        status="success",
        deleted_tabs=deleted_count,
        deleted_entities=deleted_entities,
        orphaned_entity_ids=orphaned_entity_ids,
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
    graph_db = get_graph_db()
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

            # Get tab summary from database if available
            tab_data = graph_db.get_tab(tab.id) if graph_db else None
            tab_summary = tab_data.get("summary") if tab_data else None

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
                    summary=tab_summary,  # AI-generated summary
                    important=tab.important,
                    entities=tab.entities,
                    opened_at=tab.created_at.isoformat() if tab.created_at else None,
                    window_id=tab.window_id,  # Browser window ID
                    group_id=tab.group_id,  # Chrome tab group ID
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

        # Get all per-tab contextual descriptions for this entity
        tab_contexts = {}
        if entity and entity.id:
            all_contexts = graph_db.get_all_entity_tab_contexts(entity.id)
            # Map from tab string IDs (e.g., "tab_123") to descriptions
            tab_contexts = {f"tab_{tab_id}": desc for tab_id, desc in all_contexts.items()}

        entity_node = GraphNode(
            data=GraphNodeData(
                id=entity_id,
                type="entity",
                label=entity_name,
                description=entity.web_description if entity and entity.web_description else None,
                tab_contexts=tab_contexts,  # Per-tab descriptions {tab_id: description}
                cluster_ids=list(entity_info["cluster_ids"]),
            )
        )
        nodes.append(entity_node)
        logger.debug(f"Added entity node: {entity_name} ({entity_id}) with {len(tab_contexts)} tab contexts")

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


@app.post("/api/entities/re-enrich")
async def re_enrich_entities(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Force re-enrichment even if already enriched")
):
    """
    Trigger re-enrichment of all entities with context-aware descriptions.

    This endpoint will regenerate descriptions for all (entity, tab) pairs
    using the new context-aware enrichment logic.

    Args:
        force: If true, re-enrich all entities. If false, only enrich missing contexts.
        background_tasks: FastAPI background tasks for async processing

    Returns:
        Status message with count of entities queued for enrichment
    """
    graph_db = get_graph_db()

    # Get all entity-tab pairs that need enrichment
    cursor = graph_db.conn.cursor()

    if force:
        # Get all entity-tab pairs
        cursor.execute("""
            SELECT DISTINCT te.entity_id, te.tab_id, e.name, t.url, t.title
            FROM tab_entities te
            JOIN entities e ON te.entity_id = e.id
            JOIN tabs t ON te.tab_id = t.id
            WHERE t.is_active = 1
        """)
    else:
        # Only get pairs that don't have a context yet
        cursor.execute("""
            SELECT DISTINCT te.entity_id, te.tab_id, e.name, t.url, t.title
            FROM tab_entities te
            JOIN entities e ON te.entity_id = e.id
            JOIN tabs t ON te.tab_id = t.id
            LEFT JOIN entity_tab_contexts etc
                ON etc.entity_id = te.entity_id AND etc.tab_id = te.tab_id
            WHERE t.is_active = 1 AND etc.entity_id IS NULL
        """)

    pairs = cursor.fetchall()
    entity_names = [row["name"] for row in pairs]

    if not entity_names:
        return {
            "status": "success",
            "message": "No entities need re-enrichment",
            "queued_count": 0
        }

    # Trigger background enrichment
    background_tasks.add_task(
        _background_re_enrich_entities,
        pairs=list(pairs),
        db_path=graph_db.db_path,
        you_api_key=get_settings().you_api_key
    )

    logger.info(f"Queued {len(pairs)} entity-tab pairs for re-enrichment")

    return {
        "status": "success",
        "message": f"Queued {len(pairs)} entity-tab pairs for background enrichment",
        "queued_count": len(pairs)
    }


def _background_re_enrich_entities(
    pairs: list,
    db_path: Path,
    you_api_key: str
):
    """
    Background task to re-enrich entities with context-aware descriptions.

    Args:
        pairs: List of (entity_id, tab_id, name, url, title) tuples
        db_path: Path to database
        you_api_key: You.com API key
    """
    try:
        # Initialize thread-local resources
        graph_db = KnowledgeGraphDB(db_path)
        you_client = YouAPIClient(you_api_key)
        enricher = EntityEnricher(you_client, cache_ttl_days=7)

        success_count = 0
        fail_count = 0

        for row in pairs:
            entity_id = row["entity_id"]
            tab_id = row["tab_id"]
            entity_name = row["name"]
            tab_url = row["url"]
            tab_title = row["title"]

            try:
                # Get tab summary and related entities
                tab_data = graph_db.get_tab(tab_id)
                tab_summary = tab_data.get("summary") if tab_data else None

                # Get related entities from this tab
                tab_entities = graph_db.get_entities_for_tab(tab_id)
                related_entities = [e.name for e in tab_entities if e.name != entity_name]

                # Enrich with context
                enrichment_data = enricher.enrich_entity(
                    entity_name=entity_name,
                    tab_id=tab_id,
                    tab_url=tab_url,
                    tab_title=tab_title,
                    tab_summary=tab_summary,
                    related_entities=related_entities,
                )

                if enrichment_data["is_enriched"] and enrichment_data.get("description"):
                    # Save per-tab context
                    graph_db.save_entity_tab_context(
                        entity_id=entity_id,
                        tab_id=tab_id,
                        description=enrichment_data["description"],
                    )

                    # Also update global enrichment
                    graph_db.update_entity_enrichment(
                        entity_id=entity_id,
                        web_description=enrichment_data["description"],
                        entity_type=enrichment_data["type"],
                        related_concepts=enrichment_data["related_concepts"],
                        source_url=enrichment_data["source_url"],
                    )

                    success_count += 1
                    logger.info(f"Re-enriched entity '{entity_name}' for tab {tab_id}")
                else:
                    fail_count += 1
                    logger.warning(f"Failed to re-enrich entity '{entity_name}' for tab {tab_id}")

            except Exception as e:
                fail_count += 1
                logger.error(f"Error re-enriching entity '{entity_name}' for tab {tab_id}: {e}")

        logger.info(f"Re-enrichment complete: {success_count} succeeded, {fail_count} failed")

    except Exception as e:
        logger.error(f"Background re-enrichment failed: {e}", exc_info=True)
