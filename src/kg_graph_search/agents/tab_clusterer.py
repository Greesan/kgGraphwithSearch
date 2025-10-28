"""
Tab clustering service with centroid-based assignment.

This module implements intelligent tab clustering using semantic embeddings
and centroid-based similarity matching. It handles dynamic cluster updates,
automatic naming, and maintains cluster consistency across tab additions
and removals.
"""

import uuid
from typing import Optional
from datetime import datetime, UTC
import numpy as np
from openai import OpenAI

from kg_graph_search.config import get_settings
from kg_graph_search.agents.models import (
    Tab,
    TabCluster,
    ClusterColor,
    ClusteringResult,
)


class TabClusterer:
    """
    Manages tab clustering using centroid-based similarity matching.

    This class implements the core clustering logic:
    1. Assigns tabs to clusters based on centroid similarity
    2. Updates centroids on both additions and removals
    3. Triggers cluster renaming when enough tabs are added
    4. Manages cluster lifecycle (creation, updates, deletion)

    Key Design Decisions:
    - Centroid updates on BOTH add and remove (prevents "ghost cluster" problem)
    - Rename triggered ONLY on additions (not removals)
    - Clusters with < 2 tabs are automatically deleted
    - Similarity threshold determines if tab joins existing cluster or creates new one

    Attributes:
        similarity_threshold: Minimum cosine similarity for cluster assignment (0-1)
        rename_threshold: Number of tabs added before triggering rename
        openai_client: OpenAI client for embeddings and naming
        clusters: Active clusters being managed
        color_pool: Available colors for new clusters
    """

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        rename_threshold: int = 3,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize the TabClusterer.

        Args:
            similarity_threshold: Minimum cosine similarity (0-1) for cluster assignment.
                Higher values = stricter clustering. Default: 0.75
            rename_threshold: Number of tabs added before triggering cluster rename.
                Default: 3
            openai_api_key: OpenAI API key. If not provided, loaded from config.
        """
        self.similarity_threshold = similarity_threshold
        self.rename_threshold = rename_threshold

        # Load configuration
        settings = get_settings()
        api_key = openai_api_key or settings.openai_api_key
        self.openai_client = OpenAI(api_key=api_key)
        self.embedding_model = settings.openai_embedding_model
        self.llm_model = settings.openai_llm_model

        # Cluster management
        self.clusters: list[TabCluster] = []
        self.color_pool: list[ClusterColor] = list(ClusterColor)
        self._next_color_index = 0

    def _get_next_color(self) -> ClusterColor:
        """Get the next available color for a new cluster (round-robin)."""
        color = self.color_pool[self._next_color_index]
        self._next_color_index = (self._next_color_index + 1) % len(self.color_pool)
        return color

    def _cosine_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1, where 1 is most similar)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Handle zero vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text using OpenAI API.

        Args:
            text: Text to embed (typically tab title + URL)

        Returns:
            Embedding vector

        Raises:
            Exception: If OpenAI API call fails
        """
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model, input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {e}")

    def generate_cluster_name(
        self, cluster: TabCluster, max_tabs_to_consider: int = 10
    ) -> str:
        """
        Generate a semantic name for a cluster using LLM.

        Analyzes tab titles and entities to create a concise, descriptive name.

        Args:
            cluster: The cluster to name
            max_tabs_to_consider: Maximum tabs to include in prompt (default: 10)

        Returns:
            Generated cluster name (e.g., "Graph Database Research")
        """
        # Get sample of tab titles
        tab_titles = cluster.get_tab_titles()[:max_tabs_to_consider]
        entities = cluster.shared_entities[:10]  # Top 10 shared entities

        # Build prompt
        prompt = f"""You are naming a browser tab group. Generate a concise, descriptive name (2-4 words) that captures the common theme.

Tab titles in this group:
{chr(10).join(f"- {title}" for title in tab_titles)}

Common entities:
{chr(10).join(f"- {entity}" for entity in entities) if entities else "None"}

Rules:
- Use 2-4 words maximum
- Be specific but concise
- Focus on the main topic or purpose
- Use title case

Examples:
- "Graph Database Research"
- "React Component Design"
- "Machine Learning Papers"
- "API Documentation"

Generate the name (no quotes, just the name):"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.3,
            )

            name = response.choices[0].message.content.strip()
            # Remove quotes if present
            name = name.strip('"').strip("'")
            return name

        except Exception as e:
            # Fallback to simple naming
            print(f"Warning: Failed to generate cluster name via LLM: {e}")
            return f"Cluster {cluster.id[:8]}"

    def find_best_cluster(self, tab: Tab) -> Optional[tuple[TabCluster, float]]:
        """
        Find the best matching cluster for a tab based on centroid similarity.

        Args:
            tab: The tab to find a cluster for

        Returns:
            Tuple of (best_cluster, similarity_score) or None if no good match
        """
        if not tab.embedding:
            return None

        if not self.clusters:
            return None

        best_cluster = None
        best_similarity = -1.0

        for cluster in self.clusters:
            if cluster.centroid_embedding is None:
                continue

            similarity = self._cosine_similarity(
                tab.embedding, cluster.centroid_embedding
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster

        # Only return if similarity exceeds threshold
        if best_similarity >= self.similarity_threshold:
            return (best_cluster, best_similarity)

        return None

    def add_tab_to_cluster(self, cluster: TabCluster, tab: Tab) -> None:
        """
        Add a tab to an existing cluster and update cluster state.

        This method:
        1. Adds the tab to the cluster
        2. Updates the centroid (eager evaluation)
        3. Checks if rename is needed
        4. Triggers rename if threshold reached

        Args:
            cluster: The cluster to add the tab to
            tab: The tab to add
        """
        # Add tab and update state
        cluster.add_tab(tab)

        # Update centroid (eager evaluation - always recalculate)
        cluster.update_centroid()

        # Check if rename needed (only triggered by additions)
        if cluster.should_regenerate_name(self.rename_threshold):
            new_name = self.generate_cluster_name(cluster)
            cluster.name = new_name
            cluster.tabs_added_since_naming = 0  # Reset counter
            print(f"Renamed cluster {cluster.id[:8]} to: {new_name}")

    def remove_tab_from_cluster(self, cluster: TabCluster, tab_id: int) -> bool:
        """
        Remove a tab from a cluster and update cluster state.

        This method:
        1. Removes the tab from the cluster
        2. Updates the centroid (prevents "ghost cluster" problem)
        3. Does NOT trigger rename (removals don't change cluster theme)
        4. Marks cluster for deletion if < 2 tabs remain

        Args:
            cluster: The cluster to remove the tab from
            tab_id: ID of the tab to remove

        Returns:
            True if tab was removed successfully, False otherwise
        """
        removed = cluster.remove_tab(tab_id)

        if removed:
            # Update centroid (eager evaluation)
            cluster.update_centroid()

            # Check if cluster should be deleted
            if cluster.mark_for_deletion():
                self.clusters.remove(cluster)
                print(
                    f"Deleted cluster {cluster.id[:8]} '{cluster.name}' (< 2 tabs remaining)"
                )

        return removed

    def create_new_cluster(self, tab: Tab, initial_name: Optional[str] = None) -> TabCluster:
        """
        Create a new cluster with the given tab as the seed.

        Args:
            tab: Initial tab for the cluster
            initial_name: Optional initial name. If not provided, will be generated.

        Returns:
            The newly created cluster
        """
        cluster = TabCluster(
            id=str(uuid.uuid4()),
            name=initial_name or f"New Cluster",
            color=self._get_next_color(),
            tabs=[],
            confidence=1.0,  # High confidence for single-tab cluster
            created_at=datetime.now(UTC),
        )

        # Add the initial tab
        self.add_tab_to_cluster(cluster, tab)

        # Generate initial name
        if not initial_name:
            cluster.name = self.generate_cluster_name(cluster)
            cluster.tabs_added_since_naming = 0  # Reset since we just named it

        self.clusters.append(cluster)
        print(f"Created new cluster: {cluster.name} (ID: {cluster.id[:8]})")

        return cluster

    def process_tab(self, tab: Tab) -> TabCluster:
        """
        Process a single tab: assign to existing cluster or create new one.

        This is the main entry point for tab clustering. It:
        1. Generates embedding if not present
        2. Finds best matching cluster
        3. Either adds to existing cluster or creates new one

        Args:
            tab: The tab to process

        Returns:
            The cluster the tab was assigned to
        """
        # Generate embedding if not present
        if not tab.embedding:
            text = f"{tab.title} {tab.url}"
            tab.embedding = self.generate_embedding(text)

        # Find best cluster
        result = self.find_best_cluster(tab)

        if result:
            cluster, similarity = result
            print(
                f"Assigning tab '{tab.title}' to cluster '{cluster.name}' (similarity: {similarity:.2f})"
            )
            self.add_tab_to_cluster(cluster, tab)
            return cluster
        else:
            # Create new cluster
            print(f"Creating new cluster for tab '{tab.title}'")
            return self.create_new_cluster(tab)

    def process_tabs_batch(self, tabs: list[Tab]) -> ClusteringResult:
        """
        Process multiple tabs in batch.

        Args:
            tabs: List of tabs to cluster

        Returns:
            ClusteringResult with clustering statistics
        """
        for tab in tabs:
            self.process_tab(tab)

        return ClusteringResult(
            clusters=self.clusters.copy(),
            unclustered_tabs=[],  # All tabs are assigned in centroid-based approach
            total_tabs_processed=len(tabs),
            timestamp=datetime.now(UTC),
        )

    def get_cluster_by_id(self, cluster_id: str) -> Optional[TabCluster]:
        """Get a cluster by its ID.

        Args:
            cluster_id: The cluster ID to search for

        Returns:
            The cluster if found, None otherwise
        """
        for cluster in self.clusters:
            if cluster.id == cluster_id:
                return cluster
        return None

    def get_all_clusters(self) -> list[TabCluster]:
        """Get all active clusters.

        Returns:
            List of all clusters
        """
        return self.clusters.copy()

    def get_cluster_stats(self) -> dict:
        """Get statistics about current clusters.

        Returns:
            Dictionary with cluster statistics
        """
        total_tabs = sum(cluster.tab_count for cluster in self.clusters)

        return {
            "total_clusters": len(self.clusters),
            "total_tabs": total_tabs,
            "avg_tabs_per_cluster": (
                total_tabs / len(self.clusters) if self.clusters else 0
            ),
            "clusters": [
                {
                    "id": cluster.id,
                    "name": cluster.name,
                    "color": cluster.color.value,
                    "tab_count": cluster.tab_count,
                    "tabs_added_since_naming": cluster.tabs_added_since_naming,
                }
                for cluster in self.clusters
            ],
        }
