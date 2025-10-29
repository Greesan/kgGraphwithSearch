"""
Entity enrichment service using You.com API.

Enriches entities with descriptions, types, and related concepts from web sources.
Uses You.com search API for reliable, individual entity enrichment.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional

from kg_graph_search.config import get_logger
from kg_graph_search.search.you_client import YouAPIClient

logger = get_logger(__name__)


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
        Enrich an entity using You.com Express Agent.

        Domain-agnostic approach works for entities from any field
        (technology, medicine, history, business, etc.)

        Args:
            entity_name: Name of the entity to enrich

        Returns:
            Dictionary with enriched entity data:
            {
                "name": str,
                "description": str,
                "type": str,  # Domain-agnostic types
                "related_concepts": list[str],
                "source_url": str,
                "is_enriched": bool
            }
        """
        try:
            # Use Express Agent for intelligent, domain-agnostic enrichment
            prompt = f"""Provide information about "{entity_name}". Include:
1. Entity Type: Choose ONE from [concept, tool, person, organization, method, resource, topic, standard, event, location, other]
2. Description: 2-3 sentences explaining what it is
3. Related Entities: List 3-5 related entities or concepts (can be from any domain)

Format your response as:
Type: [type]
Description: [description]
Related: [entity1, entity2, entity3]"""

            agent_response = self.you_client.express_agent_search(prompt)

            # Parse agent response
            response_text = ""
            for output in agent_response.get("output", []):
                if output.get("type") in ["message.answer", "chat_node.answer"]:
                    response_text = output.get("text", "")
                    break

            if not response_text:
                return self._empty_enrichment(entity_name)

            # Parse the structured response
            entity_type = "Other"
            description = ""
            related_concepts = []

            for line in response_text.split("\n"):
                line = line.strip()
                if line.startswith("Type:"):
                    entity_type = line.replace("Type:", "").strip().title()
                elif line.startswith("Description:"):
                    description = line.replace("Description:", "").strip()
                elif line.startswith("Related:"):
                    related_text = line.replace("Related:", "").strip()
                    # Split by comma and clean up
                    related_concepts = [r.strip() for r in related_text.split(",") if r.strip()]

            # Validate we got meaningful data
            if not description:
                return self._empty_enrichment(entity_name)

            return {
                "name": entity_name,
                "description": description[:300],  # Limit length
                "type": entity_type,
                "related_concepts": related_concepts[:5],  # Top 5
                "source_url": None,  # Agent doesn't provide specific URL
                "is_enriched": True,
                "enriched_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to enrich entity '{entity_name}': {e}")
            return self._empty_enrichment(entity_name)

    def enrich_entities(self, entity_names: list[str]) -> list[dict]:
        """
        Enrich multiple entities individually using You.com search API.

        Args:
            entity_names: List of entity names to enrich

        Returns:
            List of enriched entity dictionaries

        Example:
            >>> enricher.enrich_entities(["React", "Vue", "Angular"])
            [
                {"name": "React", "type": "Framework", "description": "...", ...},
                {"name": "Vue", "type": "Framework", "description": "...", ...}
            ]
        """
        if not entity_names:
            return []

        # Enrich each entity individually
        return [self.enrich_entity(name) for name in entity_names]

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
