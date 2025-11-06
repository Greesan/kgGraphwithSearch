"""
Data models for tab clustering and management.

This module defines the core data structures for representing browser tabs,
tab clusters, and their relationships within the TabGraph system.
"""

from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
import numpy as np


class Tab(BaseModel):
    """Represents a browser tab with its metadata and embeddings.

    Attributes:
        id: Unique identifier for the tab
        url: The URL of the tab
        title: The title of the tab
        favicon_url: URL to the tab's favicon
        summary: AI-generated 2-3 sentence summary of tab content
        entities: List of extracted entities from the tab content
        embedding: Vector embedding of the tab content (from text-embedding-3-small)
        created_at: When the tab was created/opened
        last_accessed: When the tab was last accessed
        window_id: Browser window ID containing this tab
        group_id: Chrome Tab Group ID (if assigned)
        important: Whether the tab is marked as important by the user
    """

    id: int
    url: str
    title: str
    favicon_url: Optional[str] = None
    summary: Optional[str] = None
    entities: list[str] = Field(default_factory=list)
    embedding: Optional[list[float]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    window_id: Optional[int] = None
    group_id: Optional[int] = None
    important: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('entities', mode='before')
    @classmethod
    def convert_none_to_empty_list(cls, v):
        """Convert None to empty list for entities field."""
        return v if v is not None else []


class ClusterColor(str, Enum):
    """Available colors for tab clusters (Chrome Tab Group colors)."""
    GREY = "grey"
    BLUE = "blue"
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    PINK = "pink"
    PURPLE = "purple"
    CYAN = "cyan"
    ORANGE = "orange"


class TabCluster(BaseModel):
    """Represents a cluster of semantically related tabs.

    This class manages a group of tabs that share common themes or topics.
    It tracks the centroid embedding for efficient similarity computation
    and handles lazy evaluation of centroid updates.

    Attributes:
        id: Unique identifier for the cluster
        name: Human-readable name generated from cluster content
        color: Visual color for the cluster (from ClusterColor enum)
        tabs: List of tabs in this cluster
        shared_entities: Common entities across tabs in this cluster
        confidence: Confidence score for the clustering (0-1)
        created_at: When the cluster was created
        tab_count: Number of tabs currently in the cluster
        tabs_added_since_naming: Counter for triggering cluster rename
        centroid_embedding: Average embedding vector of all tabs
        _centroid_dirty: Internal flag indicating centroid needs recalculation
    """

    id: str
    name: str
    color: ClusterColor = ClusterColor.BLUE
    tabs: list[Tab] = Field(default_factory=list)
    shared_entities: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tab_count: int = 0
    tabs_added_since_naming: int = 0
    centroid_embedding: Optional[list[float]] = None
    _centroid_dirty: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def update_centroid(self, graph_db=None) -> None:
        """Recalculate the centroid embedding based on current tabs.

        Prefers entity embeddings (cleaner signal) when available, falls back to tab embeddings.

        Args:
            graph_db: Optional KnowledgeGraphDB to fetch entity embeddings

        Note: This implementation uses eager evaluation. For lazy evaluation,
        see the property-based approach in TabClusterer.
        """
        if not self.tabs:
            self.centroid_embedding = None
            self._centroid_dirty = False
            return

        # Strategy 1: Try entity-based centroid (cleaner, more stable)
        if graph_db:
            entity_embeddings = self._get_entity_embeddings(graph_db)
            if entity_embeddings:
                self.centroid_embedding = np.mean(entity_embeddings, axis=0).tolist()
                self._centroid_dirty = False
                return

        # Strategy 2: Fall back to tab embeddings (original behavior)
        tab_embeddings = [tab.embedding for tab in self.tabs if tab.embedding is not None]
        if tab_embeddings:
            self.centroid_embedding = np.mean(tab_embeddings, axis=0).tolist()
            self._centroid_dirty = False
            return

        # Strategy 3: No embeddings available
        self.centroid_embedding = None
        self._centroid_dirty = False

    def _get_entity_embeddings(self, graph_db) -> list[list[float]]:
        """Get cached entity embeddings for all entities in this cluster.

        Args:
            graph_db: KnowledgeGraphDB instance

        Returns:
            List of entity embedding vectors (empty if none available)
        """
        # Collect unique entity names across all tabs
        all_entity_names = set()
        for tab in self.tabs:
            if tab.entities:
                all_entity_names.update(tab.entities)

        if not all_entity_names:
            return []

        # Batch fetch entities from DB (with embeddings)
        entities = graph_db.get_entities_by_names(list(all_entity_names))

        # Extract embeddings (only from entities that have them)
        entity_embeddings = [e.embedding for e in entities if e.embedding is not None]

        return entity_embeddings

    def should_regenerate_name(self, threshold: int = 3) -> bool:
        """Determine if cluster name should be regenerated.

        Clusters are renamed when enough new tabs have been added to
        potentially shift the cluster's semantic focus.

        Args:
            threshold: Number of tabs added before triggering rename (default: 3)

        Returns:
            True if cluster should be renamed, False otherwise
        """
        return self.tabs_added_since_naming >= threshold

    def mark_for_deletion(self) -> bool:
        """Check if cluster should be deleted (< 2 tabs).

        Returns:
            True if cluster has fewer than 2 tabs and should be deleted
        """
        return self.tab_count < 2

    def add_tab(self, tab: Tab) -> None:
        """Add a tab to the cluster and mark centroid as dirty.

        This method is idempotent - calling it multiple times with the same
        tab ID will not create duplicates.

        Args:
            tab: The tab to add to this cluster
        """
        # Check if tab already exists in cluster (prevents duplicates on re-sync)
        if any(t.id == tab.id for t in self.tabs):
            return

        self.tabs.append(tab)
        self.tab_count += 1
        self.tabs_added_since_naming += 1
        self._centroid_dirty = True

    def remove_tab(self, tab_id: int) -> bool:
        """Remove a tab from the cluster and mark centroid as dirty.

        Args:
            tab_id: The ID of the tab to remove

        Returns:
            True if tab was found and removed, False otherwise
        """
        initial_count = len(self.tabs)
        self.tabs = [t for t in self.tabs if t.id != tab_id]

        if len(self.tabs) < initial_count:
            self.tab_count = len(self.tabs)
            self._centroid_dirty = True
            return True

        return False

    def get_tab_titles(self) -> list[str]:
        """Get list of all tab titles in this cluster.

        Returns:
            List of tab titles
        """
        return [tab.title for tab in self.tabs]

    def get_tab_urls(self) -> list[str]:
        """Get list of all tab URLs in this cluster.

        Returns:
            List of tab URLs
        """
        return [tab.url for tab in self.tabs]


class ClusteringResult(BaseModel):
    """Result of a clustering operation.

    Attributes:
        clusters: List of created/updated clusters
        unclustered_tabs: Tabs that didn't fit into any cluster
        total_tabs_processed: Total number of tabs processed
        timestamp: When the clustering was performed
    """

    clusters: list[TabCluster]
    unclustered_tabs: list[Tab] = Field(default_factory=list)
    total_tabs_processed: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(arbitrary_types_allowed=True)
