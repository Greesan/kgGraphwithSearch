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

from kg_graph_search.config import get_settings, get_logger

logger = get_logger(__name__)
from kg_graph_search.agents.models import (
    Tab,
    TabCluster,
    ClusterColor,
    ClusteringResult,
)
from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.graph.models import Entity
from kg_graph_search.agents.entity_extractor import EntityExtractor
from kg_graph_search.agents.entity_enricher import EntityEnricher
from kg_graph_search.agents.tab_summarizer import TabSummarizer, get_metadata_provider
from kg_graph_search.search.you_client import YouAPIClient


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
        graph_db: Optional[KnowledgeGraphDB] = None,
        entity_weight: float = 0.5,
    ):
        """
        Initialize the TabClusterer.

        Args:
            similarity_threshold: Minimum cosine similarity (0-1) for cluster assignment.
                Higher values = stricter clustering. Default: 0.75
            rename_threshold: Number of tabs added before triggering cluster rename.
                Default: 3
            openai_api_key: OpenAI API key. If not provided, loaded from config.
            graph_db: Knowledge graph database for storing tab-entity relationships.
                If None, clustering will use embeddings only.
            entity_weight: Weight for entity overlap in hybrid scoring (0-1).
                0 = embeddings only, 1 = entities only. Default: 0.5 (equal weight)
        """
        self.similarity_threshold = similarity_threshold
        self.rename_threshold = rename_threshold
        self.entity_weight = entity_weight

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

        # Knowledge graph integration
        self.graph_db = graph_db

        # Entity extraction
        self.entity_extractor = EntityExtractor(self.openai_client, self.llm_model)

        # Entity enrichment and tab summarization (optional - requires API key)
        self.entity_enricher = None
        self.tab_summarizer = None
        if settings.you_api_key:
            you_client = YouAPIClient(api_key=settings.you_api_key)
            self.entity_enricher = EntityEnricher(you_client, cache_ttl_days=7)

            # Create metadata provider based on config
            metadata_provider = get_metadata_provider(settings, you_client)
            self.tab_summarizer = TabSummarizer(metadata_provider)

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

    def _entity_overlap_score(self, entities1: list[str], entities2: list[str]) -> float:
        """
        Calculate Jaccard similarity between two entity lists.

        Args:
            entities1: First list of entity names
            entities2: Second list of entity names

        Returns:
            Jaccard similarity score (0-1, where 1 means identical sets)
        """
        if not entities1 or not entities2:
            return 0.0

        set1 = set(entities1)
        set2 = set(entities2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return float(intersection / union)

    def _hybrid_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
        entities1: list[str],
        entities2: list[str],
    ) -> float:
        """
        Calculate hybrid similarity combining embeddings and entity overlap.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            entities1: First list of entities
            entities2: Second list of entities

        Returns:
            Hybrid similarity score (0-1)
        """
        # Calculate embedding similarity
        embedding_sim = self._cosine_similarity(embedding1, embedding2)

        # Calculate entity overlap
        entity_sim = self._entity_overlap_score(entities1, entities2)

        # Weighted combination
        hybrid_score = (
            (1 - self.entity_weight) * embedding_sim +
            self.entity_weight * entity_sim
        )

        return hybrid_score

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

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a single API call.

        This is much faster than calling generate_embedding() repeatedly.
        OpenAI supports up to 2048 inputs per batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors in same order as input

        Raises:
            Exception: If OpenAI API call fails
        """
        if not texts:
            return []

        try:
            # OpenAI API supports batching up to 2048 inputs
            response = self.openai_client.embeddings.create(
                model=self.embedding_model, input=texts
            )
            # Extract embeddings in order
            return [data.embedding for data in response.data]
        except Exception as e:
            raise Exception(f"Failed to generate batch embeddings: {e}")

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
        prompt = f"""You are naming a browser tab group. Generate a broad, general category name (1-3 words) that captures the overarching theme.

Tab titles in this group:
{chr(10).join(f"- {title}" for title in tab_titles)}

Common entities:
{chr(10).join(f"- {entity}" for entity in entities) if entities else "None"}

Rules:
- Use 1-3 words maximum
- Be GENERAL and BROAD - think high-level categories
- Prefer single-word or two-word labels when possible
- Avoid overly specific details
- Use title case

Examples:
- "Development" (not "React Development")
- "Databases" (not "Graph Database Research")
- "Machine Learning" (not "ML Papers on Transformers")
- "Documentation" (not "API Documentation")
- "Research" (not "Academic Paper Review")

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
            logger.warning(f"Failed to generate cluster name via LLM: {e}")
            return f"Cluster {cluster.id[:8]}"

    def generate_cluster_names_batch(
        self, clusters: list[TabCluster], max_tabs_per_cluster: int = 10
    ) -> list[str]:
        """
        Generate names for multiple clusters in a single API call.

        This is ~5x faster than calling generate_cluster_name() sequentially.
        Uses OpenAI Structured Outputs for guaranteed JSON schema adherence.

        Args:
            clusters: List of clusters to name
            max_tabs_per_cluster: Maximum tabs to include per cluster (default: 10)

        Returns:
            List of cluster names in same order as input clusters
        """
        if not clusters:
            return []

        # Build batch descriptions
        cluster_descriptions = []
        for i, cluster in enumerate(clusters):
            tab_titles = cluster.get_tab_titles()[:max_tabs_per_cluster]
            entities = cluster.shared_entities[:10]

            cluster_descriptions.append({
                "index": i,
                "tab_titles": tab_titles,
                "common_entities": entities
            })

        # Build prompt
        import json
        prompt = f"""You are naming browser tab groups. Generate a broad, general category name (1-3 words) for each group.

{json.dumps(cluster_descriptions, indent=2)}

Rules:
- Use 1-3 words maximum per name
- Be GENERAL and BROAD - think high-level categories
- Use title case
- Avoid overly specific details

Examples:
- "Development" (not "React Development")
- "Databases" (not "Graph Database Research")
- "Research" (not "Academic Paper Review")

Return JSON with "names" array (one name per cluster, in order):"""

        # Define schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["names"]
        }

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "cluster_names",
                        "schema": schema,
                        "strict": True
                    }
                },
                max_tokens=200,
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)
            names = result.get("names", [])

            # Validate we got the right number of names
            if len(names) != len(clusters):
                logger.warning(f"Expected {len(clusters)} names, got {len(names)}. Falling back to sequential naming.")
                raise ValueError(f"Mismatch in cluster count: expected {len(clusters)}, got {len(names)}")

            # Clean up names (remove quotes if present)
            names = [name.strip('"').strip("'") for name in names]

            logger.info(f"Successfully generated {len(names)} cluster names in batch")
            return names

        except Exception as e:
            # Fallback to sequential naming on error
            logger.warning(f"Batch cluster naming failed: {e}. Falling back to sequential naming.")
            return [self.generate_cluster_name(c, max_tabs_per_cluster) for c in clusters]

    def _store_tab_in_graph(self, tab: Tab) -> None:
        """
        Store tab and its entities in the knowledge graph.

        Also computes and stores relationships to other tabs.

        Args:
            tab: The tab to store
        """
        if not self.graph_db:
            return

        # Store tab in database
        self.graph_db.add_tab(
            tab_id=tab.id,
            url=tab.url,
            title=tab.title,
            favicon_url=tab.favicon_url,
            embedding=tab.embedding,
            window_id=tab.window_id,
            group_id=tab.group_id,
        )

        # Generate tab summary asynchronously (non-blocking)
        if self.tab_summarizer and not tab.summary:
            self._generate_summary_async(tab.id, tab.title, tab.url)

        # Store entities and link to tab
        for entity_name in tab.entities:
            # Create or get entity
            entity = self.graph_db.find_entity_by_name(entity_name)
            if not entity:
                entity = Entity(
                    name=entity_name,
                    entity_type="Concept",  # Default type
                    description=None,
                    created_at=datetime.now(UTC),
                )
                entity_id = self.graph_db.add_entity(entity)

                # Enrich new entity if enricher is available (with tab context)
                if self.entity_enricher:
                    self._enrich_entity_async(entity_id, entity_name, tab)
            else:
                entity_id = entity.id

                # Check if we need to enrich this entity for this specific tab
                # Always enrich if we don't have a context for this (entity, tab) pair
                if self.entity_enricher:
                    existing_context = self.graph_db.get_entity_tab_context(entity_id, tab.id)
                    if not existing_context:
                        self._enrich_entity_async(entity_id, entity_name, tab)

            # Link tab to entity
            self.graph_db.link_tab_to_entity(tab.id, entity_id)

        # Compute and store relationships to other tabs
        if tab.entities:  # Only compute if tab has entities
            self.graph_db.compute_and_store_tab_relationships(tab.id, min_shared=1)

    def _generate_summary_async(self, tab_id: int, title: str, url: str) -> None:
        """
        Generate tab metadata asynchronously.

        This method generates metadata (label, source, summary) in the background
        without blocking tab processing.

        Args:
            tab_id: Tab ID
            title: Tab title
            url: Tab URL
        """
        if not self.tab_summarizer or not self.graph_db:
            return

        try:
            # Generate metadata (label, source, summary, display_label)
            metadata = self.tab_summarizer.summarize_tab(title, url)

            if metadata:
                # Save all metadata fields to database
                self.graph_db.update_tab_metadata(
                    tab_id=tab_id,
                    summary=metadata.get("summary"),
                    label=metadata.get("label"),
                    source=metadata.get("source"),
                    display_label=metadata.get("display_label"),
                )
                logger.info(f"Generated metadata for tab {tab_id}: {metadata.get('display_label', title[:50])}")
        except Exception as e:
            # Silently fail metadata generation - don't block tab processing
            logger.warning(f"Failed to generate metadata for tab {tab_id}: {e}")

    def _enrich_entity_async(self, entity_id: int, entity_name: str, tab: Tab) -> None:
        """
        Enrich an entity with web data asynchronously using tab context.

        Generates context-aware descriptions by providing tab URL, title, summary,
        and related entities to the enricher.

        This method enriches entities in the background without blocking
        tab processing. In production, this should be done with proper
        async/queue infrastructure.

        Args:
            entity_id: ID of the entity to enrich
            entity_name: Name of the entity
            tab: Source tab providing context
        """
        if not self.entity_enricher or not self.graph_db:
            return

        try:
            # Get tab summary if available (may not be generated yet)
            tab_data = self.graph_db.get_tab(tab.id)
            tab_summary = tab_data.get("summary") if tab_data else None

            # Get other entities from this tab for context
            related_entities = [e for e in tab.entities if e != entity_name]

            # Get enrichment data from You.com with tab context
            enrichment_data = self.entity_enricher.enrich_entity(
                entity_name=entity_name,
                tab_id=tab.id,
                tab_url=tab.url,
                tab_title=tab.title,
                tab_summary=tab_summary,
                related_entities=related_entities,
            )

            if enrichment_data["is_enriched"]:
                # Save per-tab contextual description
                if enrichment_data.get("tab_id") and enrichment_data["description"]:
                    self.graph_db.save_entity_tab_context(
                        entity_id=entity_id,
                        tab_id=tab.id,
                        description=enrichment_data["description"],
                    )

                # Also update global enrichment fields (for backward compatibility)
                self.graph_db.update_entity_enrichment(
                    entity_id=entity_id,
                    web_description=enrichment_data["description"],
                    entity_type=enrichment_data["type"],
                    related_concepts=enrichment_data["related_concepts"],
                    source_url=enrichment_data["source_url"],
                )
        except Exception as e:
            # Silently fail enrichment - don't block tab processing
            logger.warning(f"Failed to enrich entity '{entity_name}' for tab {tab.id}: {e}")

    def _update_cluster_shared_entities(self, cluster: TabCluster) -> None:
        """
        Update the shared_entities list for a cluster based on current tabs.

        Finds entities that appear in multiple tabs within the cluster.

        Args:
            cluster: The cluster to update
        """
        if not cluster.tabs:
            cluster.shared_entities = []
            return

        # Count entity occurrences across all tabs
        entity_counts: dict[str, int] = {}
        for tab in cluster.tabs:
            for entity in tab.entities:
                entity_counts[entity] = entity_counts.get(entity, 0) + 1

        # Include entities that appear in at least 2 tabs, or if cluster has only 1 tab, all entities
        min_occurrences = 2 if len(cluster.tabs) > 1 else 1
        shared = [
            entity for entity, count in entity_counts.items()
            if count >= min_occurrences
        ]

        # Sort by frequency (most common first)
        cluster.shared_entities = sorted(
            shared, key=lambda e: entity_counts[e], reverse=True
        )

    def find_best_cluster(self, tab: Tab) -> Optional[tuple[TabCluster, float]]:
        """
        Find the best matching cluster for a tab using hybrid scoring.

        If graph_db is available, uses both embedding similarity and entity overlap.
        Otherwise, falls back to embedding-only matching.

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

            # Use hybrid similarity if we have entities
            if self.entity_weight > 0 and tab.entities and cluster.shared_entities:
                similarity = self._hybrid_similarity(
                    tab.embedding,
                    cluster.centroid_embedding,
                    tab.entities,
                    cluster.shared_entities,
                )
            else:
                # Fall back to embedding-only similarity
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
        3. Updates shared entities
        4. Stores tab in knowledge graph
        5. Checks if rename is needed
        6. Triggers rename if threshold reached

        Args:
            cluster: The cluster to add the tab to
            tab: The tab to add
        """
        # Add tab and update state
        cluster.add_tab(tab)

        # Update centroid (eager evaluation - always recalculate)
        # Pass graph_db to enable entity-based centroids
        cluster.update_centroid(graph_db=self.graph_db)

        # Update shared entities for the cluster
        self._update_cluster_shared_entities(cluster)

        # Store tab in knowledge graph
        self._store_tab_in_graph(tab)

        # Check if rename needed (only triggered by additions)
        if cluster.should_regenerate_name(self.rename_threshold):
            new_name = self.generate_cluster_name(cluster)
            cluster.name = new_name
            cluster.tabs_added_since_naming = 0  # Reset counter
            logger.info(f"Renamed cluster {cluster.id[:8]} to: {new_name}")

    def remove_tab(self, tab_id: int) -> bool:
        """
        Remove a tab from its cluster.

        Args:
            tab_id: ID of the tab to remove

        Returns:
            True if tab was found and removed, False otherwise
        """
        # Find which cluster contains this tab
        for cluster in self.clusters:
            if any(tab.id == tab_id for tab in cluster.tabs):
                return self.remove_tab_from_cluster(cluster, tab_id)
        return False

    def remove_tab_from_cluster(self, cluster: TabCluster, tab_id: int) -> bool:
        """
        Remove a tab from a cluster and update cluster state.

        This method:
        1. Removes the tab from the cluster
        2. Updates the centroid (prevents "ghost cluster" problem)
        3. Updates shared entities
        4. Removes tab from knowledge graph
        5. Does NOT trigger rename (removals don't change cluster theme)
        6. Marks cluster for deletion if < 2 tabs remain

        Args:
            cluster: The cluster to remove the tab from
            tab_id: ID of the tab to remove

        Returns:
            True if tab was removed successfully, False otherwise
        """
        removed = cluster.remove_tab(tab_id)

        if removed:
            # Update centroid (eager evaluation)
            # Pass graph_db to enable entity-based centroids
            cluster.update_centroid(graph_db=self.graph_db)

            # Update shared entities
            self._update_cluster_shared_entities(cluster)

            # Remove from knowledge graph
            if self.graph_db:
                self.graph_db.remove_tab(tab_id)

            # Check if cluster should be deleted
            if cluster.mark_for_deletion():
                self.clusters.remove(cluster)
                logger.info(
                    f"Deleted cluster {cluster.id[:8]} '{cluster.name}' (< 2 tabs remaining)"
                )

        return removed

    def create_new_cluster(self, tab: Tab, initial_name: Optional[str] = None, defer_naming: bool = False) -> TabCluster:
        """
        Create a new cluster with the given tab as the seed.

        Args:
            tab: Initial tab for the cluster
            initial_name: Optional initial name. If not provided, will be generated.
            defer_naming: If True, skip LLM naming and use placeholder (saves API calls during batch ingestion)

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
        # Temporarily disable naming during add to avoid immediate LLM call
        original_threshold = self.rename_threshold
        if defer_naming:
            self.rename_threshold = 999  # Prevent naming during add

        self.add_tab_to_cluster(cluster, tab)

        if defer_naming:
            self.rename_threshold = original_threshold  # Restore threshold

        # Generate initial name only if not deferring
        if not initial_name and not defer_naming:
            cluster.name = self.generate_cluster_name(cluster)
            cluster.tabs_added_since_naming = 0  # Reset since we just named it

        self.clusters.append(cluster)
        logger.info(f"Created new cluster: {cluster.name} (ID: {cluster.id[:8]})")

        return cluster

    def process_tab(self, tab: Tab) -> TabCluster:
        """
        Process a single tab: assign to existing cluster or create new one.

        This is the main entry point for tab clustering. It:
        1. Extracts entities if not present
        2. Generates embedding if not present
        3. Finds best matching cluster (using hybrid scoring if enabled)
        4. Either adds to existing cluster or creates new one
        5. Stores tab in knowledge graph

        Args:
            tab: The tab to process

        Returns:
            The cluster the tab was assigned to
        """
        # Extract entities if not present (single-tab fallback)
        # Note: For batch processing, entities are extracted in process_tabs_batch()
        if not tab.entities:
            tab.entities = self.entity_extractor.extract_entities(
                title=tab.title,
                url=tab.url,
                max_entities=8,
            )

        # Generate embedding if not present
        if not tab.embedding:
            text = f"{tab.title} {tab.url}"
            tab.embedding = self.generate_embedding(text)

        # Find best cluster (uses hybrid scoring if entity_weight > 0)
        result = self.find_best_cluster(tab)

        if result:
            cluster, similarity = result
            logger.info(
                f"Assigning tab '{tab.title}' to cluster '{cluster.name}' (similarity: {similarity:.2f})"
            )
            self.add_tab_to_cluster(cluster, tab)
            return cluster
        else:
            # Create new cluster
            logger.info(f"Creating new cluster for tab '{tab.title}'")
            return self.create_new_cluster(tab)

    def _enrich_entities_for_tabs(self, tabs: list[Tab]) -> list[dict]:
        """
        Extract and enrich unique entities from a batch of tabs.

        This method:
        1. Collects all unique entities across tabs
        2. Batch checks which ones need enrichment (eliminating N+1 queries)
        3. Enriches missing entities via You.com API
        4. Stores enriched data in knowledge graph

        Args:
            tabs: List of tabs to extract entities from

        Returns:
            List of enrichment result dictionaries

        Note:
            This is a BLOCKING operation that makes external API calls.
            For async/background enrichment, call this from a background task.
        """
        if not self.entity_enricher or not self.graph_db:
            return []

        # Collect all unique entities across all tabs
        all_entity_names = set()
        for tab in tabs:
            if tab.entities:
                all_entity_names.update(tab.entities)

        if not all_entity_names:
            return []

        # Batch fetch existing entities (eliminates N+1 query pattern)
        entity_names_list = list(all_entity_names)
        existing_entities = self.graph_db.get_entities_by_names(entity_names_list)

        # Filter to only enriched entities
        enriched_names = {e.name for e in existing_entities if e.is_enriched}

        # Determine which entities need enrichment
        entities_needing_enrichment = [
            name for name in entity_names_list
            if name not in enriched_names
        ]

        if not entities_needing_enrichment:
            logger.debug("All entities already enriched")
            return []

        # Enrich entities via You.com API
        logger.info(f"Enriching {len(entities_needing_enrichment)} entities...")
        enriched_data = self.entity_enricher.enrich_entities(entities_needing_enrichment)

        # Batch generate embeddings for all entity names (1 API call!)
        logger.info(f"Generating embeddings for {len(entities_needing_enrichment)} entity names...")
        entity_embeddings_map = {}
        try:
            entity_embeddings = self.generate_embeddings_batch(entities_needing_enrichment)
            entity_embeddings_map = dict(zip(entities_needing_enrichment, entity_embeddings))
            logger.debug(f"Generated {len(entity_embeddings_map)} entity embeddings")
        except Exception as e:
            logger.warning(f"Failed to generate entity embeddings: {e}")
            # Continue without embeddings (will use tab embeddings for centroid)

        # Store enriched entities in knowledge graph (with embeddings)
        stored_count = 0
        for enrichment in enriched_data:
            if enrichment.get("is_enriched"):
                from kg_graph_search.graph.models import Entity

                entity_name = enrichment["name"]
                entity = Entity(
                    name=entity_name,
                    entity_type=enrichment["type"],
                    description=None,  # Optional field, use web_description for actual content
                    web_description=enrichment["description"],
                    related_concepts=enrichment.get("related_concepts", []),
                    source_url=enrichment.get("source_url"),
                    is_enriched=True,
                    enriched_at=datetime.now(UTC),
                    embedding=entity_embeddings_map.get(entity_name),  # Add embedding
                )
                self.graph_db.add_entity(entity)
                stored_count += 1

        logger.info(f"Successfully enriched and stored {stored_count} entities with embeddings")
        return enriched_data

    def process_tabs_batch(self, tabs: list[Tab], skip_enrichment: bool = False) -> ClusteringResult:
        """
        Process multiple tabs in batch with optimized embedding generation.

        This method generates embeddings for all tabs in a single API call,
        which is ~10x faster than processing tabs individually.

        Args:
            tabs: List of tabs to cluster
            skip_enrichment: If True, skip entity enrichment (for fast response).
                Enrichment can be done later in a background task.

        Returns:
            ClusteringResult with clustering statistics
        """
        # Separate tabs that need embeddings from those that already have them
        tabs_needing_embeddings = [tab for tab in tabs if not tab.embedding]
        tabs_with_embeddings = [tab for tab in tabs if tab.embedding]

        # Batch generate embeddings for all tabs that need them
        if tabs_needing_embeddings:
            texts = [f"{tab.title} {tab.url}" for tab in tabs_needing_embeddings]
            embeddings = self.generate_embeddings_batch(texts)

            # Assign embeddings back to tabs
            for tab, embedding in zip(tabs_needing_embeddings, embeddings):
                tab.embedding = embedding

        # Batch extract entities for all tabs that need them
        tabs_needing_entities = [tab for tab in tabs if not tab.entities]
        if tabs_needing_entities:
            tabs_data = [{"title": tab.title, "url": tab.url} for tab in tabs_needing_entities]
            all_entities = self.entity_extractor.extract_entities_batch(tabs_data, max_entities=8)

            # Assign entities back to tabs
            for tab, entities in zip(tabs_needing_entities, all_entities):
                tab.entities = entities

            logger.info(f"Batch extracted entities for {len(tabs_needing_entities)} tabs")

        # Enrich entities if enabled (BLOCKING - can take several seconds)
        if not skip_enrichment:
            self._enrich_entities_for_tabs(tabs)
        else:
            logger.debug("Skipping entity enrichment (skip_enrichment=True)")

        # Track which clusters were created during this batch
        clusters_before = set(c.id for c in self.clusters)

        # Now process all tabs (clustering assignment)
        for tab in tabs:
            # Skip embedding generation since we already have it
            result = self.find_best_cluster(tab)

            if result:
                cluster, similarity = result
                logger.info(
                    f"Assigning tab '{tab.title}' to cluster '{cluster.name}' (similarity: {similarity:.2f})"
                )
                self.add_tab_to_cluster(cluster, tab)
            else:
                # Create new cluster with deferred naming
                logger.info(f"Creating new cluster for tab '{tab.title}'")
                self.create_new_cluster(tab, defer_naming=True)

        # Name all newly created clusters in batch (after they have multiple tabs)
        # Skip naming single-tab clusters (no point in creating tab groups for them)
        clusters_after = set(c.id for c in self.clusters)
        new_cluster_ids = clusters_after - clusters_before

        # Collect clusters that need naming (2+ tabs, unnamed)
        clusters_to_name = [
            c for c in self.clusters
            if c.id in new_cluster_ids and c.name == "New Cluster" and c.tab_count >= 2
        ]

        if clusters_to_name:
            # Batch name all clusters in a single API call (5x faster!)
            logger.info(f"Batch naming {len(clusters_to_name)} clusters...")
            names = self.generate_cluster_names_batch(clusters_to_name)

            # Assign names back to clusters
            for cluster, name in zip(clusters_to_name, names):
                cluster.name = name
                cluster.tabs_added_since_naming = 0
                logger.info(f"Named new cluster: {cluster.name} (ID: {cluster.id[:8]})")

        # Log skipped single-tab clusters
        skipped_count = sum(
            1 for c in self.clusters
            if c.id in new_cluster_ids and c.name == "New Cluster" and c.tab_count < 2
        )
        if skipped_count > 0:
            logger.debug(f"Skipped naming {skipped_count} single-tab cluster(s)")

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

    def get_hub_entities(self, cluster: TabCluster, top_n: int = 3) -> list[str]:
        """
        Get the most common entities in a cluster (hub entities).

        Hub entities are those that appear in the most tabs within the cluster.
        These are used for efficient relationship discovery.

        Args:
            cluster: The cluster to analyze
            top_n: Number of top entities to return (default: 3)

        Returns:
            List of entity names, sorted by frequency (most common first)

        Example:
            >>> hub_entities = clusterer.get_hub_entities(cluster, top_n=3)
            ['React', 'JavaScript', 'Hooks']
        """
        from collections import Counter

        # Count entity occurrences across all tabs in cluster
        entity_counts = Counter()

        for tab in cluster.tabs:
            if tab.entities:
                entity_counts.update(tab.entities)

        # Return top N most common entities
        return [entity for entity, count in entity_counts.most_common(top_n)]

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
