"""
Entity enrichment service using You.com API.

Enriches entities with descriptions, types, and related concepts from web sources.
Uses You.com search API for reliable, individual entity enrichment.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    def enrich_entity(
        self,
        entity_name: str,
        tab_id: Optional[int] = None,
        tab_url: Optional[str] = None,
        tab_title: Optional[str] = None,
        tab_summary: Optional[str] = None,
        related_entities: Optional[list[str]] = None,
    ) -> dict:
        """
        Enrich an entity using You.com Express Agent with optional tab context.

        When tab context is provided, generates context-aware descriptions
        (e.g., "tools" in OpenAI docs vs "tools" in hardware site).

        This method includes automatic retry logic with exponential backoff
        for transient network errors.

        Args:
            entity_name: Name of the entity to enrich
            tab_id: Optional tab ID for context tracking
            tab_url: Optional tab URL for context
            tab_title: Optional tab title for context
            tab_summary: Optional tab summary for context
            related_entities: Optional list of co-occurring entities

        Returns:
            Dictionary with enriched entity data:
            {
                "name": str,
                "description": str,
                "type": str,
                "related_concepts": list[str],
                "source_url": str,
                "is_enriched": bool,
                "tab_id": int (if provided)
            }
        """
        try:
            # Build context-aware prompt
            context_parts = []

            if tab_url:
                context_parts.append(f"URL: {tab_url}")

            if related_entities:
                context_parts.append(f"Related concepts: {', '.join(related_entities[:5])}")

            if tab_summary:
                context_parts.append(f"Page summary: {tab_summary}")
            elif tab_title:
                context_parts.append(f"Page title: {tab_title}")

            # Build prompt with or without context
            if context_parts:
                context_str = "\n".join(context_parts)
                prompt = f"""Provide information about "{entity_name}" in the context of this webpage:

{context_str}

Include:
1. Entity Type: Choose ONE from [concept, tool, person, organization, method, resource, topic, standard, event, location, other]
2. Description: 2-3 sentences explaining what it is IN THIS SPECIFIC CONTEXT
3. Related Entities: List 3-5 related entities from this domain

Format your response as:
Type: [type]
Description: [description]
Related: [entity1, entity2, entity3]"""
            else:
                # Fallback to generic enrichment (backward compatible)
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
                return self._empty_enrichment(entity_name, tab_id)

            result = {
                "name": entity_name,
                "description": description[:300],  # Limit length
                "type": entity_type,
                "related_concepts": related_concepts[:5],  # Top 5
                "source_url": None,  # Agent doesn't provide specific URL
                "is_enriched": True,
                "enriched_at": datetime.now(UTC).isoformat(),
            }

            # Include tab_id if provided (for per-tab context tracking)
            if tab_id is not None:
                result["tab_id"] = tab_id

            return result

        except Exception as e:
            logger.error(
                f"Failed to enrich entity '{entity_name}' after retries: {e}",
                exc_info=True,
                extra={"entity_name": entity_name}
            )
            return self._empty_enrichment(entity_name, tab_id)

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

    def _empty_enrichment(self, entity_name: str, tab_id: Optional[int] = None) -> dict:
        """Return empty enrichment data."""
        result = {
            "name": entity_name,
            "description": None,
            "type": "Unknown",
            "related_concepts": [],
            "source_url": None,
            "is_enriched": False,
            "enriched_at": None,
        }

        if tab_id is not None:
            result["tab_id"] = tab_id

        return result
