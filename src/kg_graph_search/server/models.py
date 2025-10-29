"""
Pydantic models for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class TabInput(BaseModel):
    """Input model for a browser tab from the extension."""

    id: int
    url: str
    title: str
    favicon_url: Optional[str] = None
    important: bool = False
    content: Optional[str] = None  # Only for important tabs
    window_id: Optional[int] = None
    group_id: Optional[int] = None


class TabsIngestRequest(BaseModel):
    """Request model for /api/tabs/ingest endpoint."""

    tabs: list[TabInput]
    timestamp: str  # ISO format timestamp


# ============================================================================
# Response Models
# ============================================================================


class TabsIngestResponse(BaseModel):
    """Response model for /api/tabs/ingest endpoint."""

    status: str
    processed: int
    important_tabs: int = 0
    session_id: str


class TabResponse(BaseModel):
    """Response model for a single tab."""

    id: int
    title: str
    url: str
    important: bool = False
    entities: list[str] = Field(default_factory=list)


class TabRelationship(BaseModel):
    """Response model for relationship between tabs."""

    from_tab_id: int
    to_tab_id: int
    shared_entities: list[str]
    strength: float = Field(ge=0.0, le=1.0)


class ClusterResponse(BaseModel):
    """Response model for a tab cluster."""

    id: str
    name: str
    color: str
    tabs: list[TabResponse]
    shared_entities: list[str] = Field(default_factory=list)
    tab_count: int


class TabsClustersResponse(BaseModel):
    """Response model for /api/tabs/clusters endpoint."""

    clusters: list[ClusterResponse]
    relationships: list[TabRelationship] = Field(default_factory=list)
    timestamp: str


class RecommendationResponse(BaseModel):
    """Response model for a single recommendation."""

    title: str
    url: str
    snippet: str
    reason: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    source: str  # "you_search" or "you_news"
    cluster_id: Optional[str] = None
    is_news: bool = False


class RecommendationsResponse(BaseModel):
    """Response model for /api/recommendations endpoint."""

    recommendations: list[RecommendationResponse] = Field(default_factory=list)
    total: int = 0


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""

    status: str
    version: str = "0.1.0"
    timestamp: str


# ============================================================================
# Graph Visualization Models
# ============================================================================


class GraphNodeData(BaseModel):
    """Data payload for a graph node."""

    id: str
    type: str  # "cluster", "tab", or "entity"
    label: str
    color: Optional[str] = None
    cluster_id: Optional[str] = None  # For tabs - which cluster they belong to (NOT parent, to avoid compound nodes)
    url: Optional[str] = None  # For tabs
    important: Optional[bool] = None  # For tabs
    entities: Optional[list[str]] = None  # For tabs
    opened_at: Optional[str] = None  # For tabs
    tab_count: Optional[int] = None  # For clusters
    shared_entities: Optional[list[str]] = None  # For clusters
    description: Optional[str] = None  # For entities
    cluster_ids: Optional[list[str]] = None  # For entities - which clusters reference this entity


class GraphNode(BaseModel):
    """Node in the graph visualization."""

    data: GraphNodeData


class GraphEdgeData(BaseModel):
    """Data payload for a graph edge."""

    id: str
    source: str
    target: str
    type: str  # "contains" (cluster->tab), "references" (tab->entity), "relationship" (entity->entity)
    label: Optional[str] = None  # For relationship edges (predicate)
    weight: Optional[float] = None  # Edge weight for layout algorithm (higher = stronger attraction)
    confidence: Optional[float] = None  # For relationship edges


class GraphEdge(BaseModel):
    """Edge in the graph visualization."""

    data: GraphEdgeData


class GraphVisualizationResponse(BaseModel):
    """Response model for /api/graph/visualization endpoint."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    timestamp: str
    metadata: dict = Field(default_factory=dict)
