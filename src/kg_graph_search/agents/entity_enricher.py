"""
Entity enrichment service using You.com API.

Enriches entities with descriptions, types, and related concepts from web sources.
Implements caching to minimize API costs.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional
from kg_graph_search.search.you_client import YouAPIClient


class EntityEnricher:
    """Service for enriching entities with You.com web data."""

    def __init__(self, you_client: YouAPIClient, cache_ttl_days: int = 7):
        """
        Initialize the entity enricher.

        Args:
            you_client: You.com API client
            cache_ttl_days: How long to cache enrichment data (default: 7 days)
        """
        self.you_client = you_client
        self.cache_ttl = timedelta(days=cache_ttl_days)

    def enrich_entity(self, entity_name: str) -> dict:
        """
        Enrich an entity with web information.

        Args:
            entity_name: Name of the entity to enrich

        Returns:
            Dictionary with enriched entity data:
            {
                "name": str,
                "description": str,
                "type": str,  # "Technology", "Framework", "Concept", etc.
                "related_concepts": list[str],
                "source_url": str,
                "is_enriched": bool
            }
        """
        try:
            # Search for entity information
            search_query = f"{entity_name} programming technology definition"
            search_results = self.you_client.search(
                query=search_query,
                num_results=3,
            )

            if not search_results.results:
                return self._empty_enrichment(entity_name)

            # Extract description from first result
            top_result = search_results.results[0]
            description = top_result.snippet[:200]  # Truncate long descriptions

            # Determine entity type from context
            entity_type = self._classify_entity_type(entity_name, description)

            # Extract related concepts
            related_concepts = self._extract_related_concepts(
                entity_name, search_results
            )

            return {
                "name": entity_name,
                "description": description,
                "type": entity_type,
                "related_concepts": related_concepts[:5],  # Top 5 related
                "source_url": top_result.url,
                "is_enriched": True,
                "enriched_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            print(f"Failed to enrich entity '{entity_name}': {e}")
            return self._empty_enrichment(entity_name)

    def _empty_enrichment(self, entity_name: str) -> dict:
        """Return empty enrichment data."""
        return {
            "name": entity_name,
            "description": None,
            "type": "Unknown",
            "related_concepts": [],
            "source_url": None,
            "is_enriched": False,
            "enriched_at": None,
        }

    def _classify_entity_type(self, entity_name: str, description: str) -> str:
        """
        Classify entity type based on name and description.

        Args:
            entity_name: Entity name
            description: Entity description

        Returns:
            Entity type category
        """
        description_lower = description.lower()
        name_lower = entity_name.lower()

        # Framework patterns
        if any(
            keyword in description_lower or keyword in name_lower
            for keyword in ["framework", "library", ".js", "react", "angular", "vue"]
        ):
            return "Framework"

        # Database patterns
        if any(
            keyword in description_lower
            for keyword in ["database", "db", "storage", "query"]
        ):
            return "Database"

        # Language patterns
        if any(
            keyword in description_lower
            for keyword in [
                "programming language",
                "language",
                "python",
                "javascript",
                "java",
            ]
        ):
            return "Programming Language"

        # Tool patterns
        if any(keyword in description_lower for keyword in ["tool", "cli", "command"]):
            return "Tool"

        # Platform patterns
        if any(
            keyword in description_lower
            for keyword in ["platform", "service", "cloud", "aws", "azure"]
        ):
            return "Platform"

        # Concept patterns
        if any(
            keyword in description_lower
            for keyword in ["concept", "paradigm", "methodology", "pattern"]
        ):
            return "Concept"

        # Default to Technology
        return "Technology"

    def _extract_related_concepts(
        self, entity_name: str, search_results
    ) -> list[str]:
        """
        Extract related concepts from search results.

        Args:
            entity_name: Entity name
            search_results: Search results from You.com

        Returns:
            List of related concept names
        """
        related = set()

        # Common tech keywords that might appear
        tech_keywords = {
            "react",
            "vue",
            "angular",
            "python",
            "javascript",
            "typescript",
            "node",
            "django",
            "flask",
            "api",
            "rest",
            "graphql",
            "docker",
            "kubernetes",
            "aws",
            "mongodb",
            "postgresql",
            "redis",
            "neo4j",
            "graph",
            "database",
            "ml",
            "ai",
            "pytorch",
            "tensorflow",
        }

        # Extract from snippets
        for result in search_results.results[:3]:
            snippet_lower = result.snippet.lower()

            # Look for tech keywords
            for keyword in tech_keywords:
                if keyword in snippet_lower and keyword.lower() != entity_name.lower():
                    related.add(keyword.title())

        return sorted(list(related))

    def check_trending(
        self, entity_name: str, days: int = 7
    ) -> Optional[dict]:
        """
        Check if an entity is trending in recent news.

        Args:
            entity_name: Entity to check
            days: Look back this many days (default: 7)

        Returns:
            Dictionary with trending information or None if not available
        """
        # Note: You.com doesn't have a dedicated news endpoint in basic API
        # This would use a news-specific search or RAG
        # For now, we'll return a placeholder
        return None
