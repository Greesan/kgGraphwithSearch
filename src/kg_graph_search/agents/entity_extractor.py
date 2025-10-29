"""
Entity extraction service for knowledge graph.

Extracts key topics, concepts, and keywords from tab content (any domain).
Uses LLM for intelligent extraction with fallback to keyword-based extraction.
"""

import json
import re
from typing import Optional

from openai import OpenAI

from kg_graph_search.config import get_logger

logger = get_logger(__name__)

# JSON Schema for batch entity extraction (OpenAI Structured Outputs)
BATCH_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 8
                    }
                },
                "required": ["entities"],
                "additionalProperties": False
            }
        }
    },
    "required": ["results"],
    "additionalProperties": False
}


class EntityExtractor:
    """Service for extracting entities from tab metadata."""

    def __init__(self, openai_client: OpenAI, model: str = "gpt-4o-mini"):
        """
        Initialize the entity extractor.

        Args:
            openai_client: OpenAI client for LLM calls
            model: Model to use for extraction
        """
        self.client = openai_client
        self.model = model

    def extract_entities(
        self,
        title: str,
        url: str,
        content: Optional[str] = None,
        max_entities: int = 8,
    ) -> list[str]:
        """
        Extract key entities from tab metadata.

        Args:
            title: Tab title
            url: Tab URL
            content: Optional page content (first ~500 chars)
            max_entities: Maximum number of entities to extract

        Returns:
            List of entity names (3-8 entities typically)
        """
        # Try LLM extraction first
        try:
            entities = self._extract_with_llm(title, url, content, max_entities)
            if entities:
                return entities
        except Exception as e:
            logger.warning(f"LLM extraction failed for '{title}': {e}, falling back to keyword extraction")

        # Fallback to keyword extraction
        return self._extract_with_keywords(title, url, max_entities)

    def extract_entities_batch(
        self,
        tabs: list[dict[str, str]],
        max_entities: int = 8,
    ) -> list[list[str]]:
        """
        Extract entities for multiple tabs in a single API call.

        Uses OpenAI Structured Outputs to guarantee correct JSON schema adherence.
        This is ~10-20x faster than calling extract_entities() for each tab individually.

        Args:
            tabs: List of dicts with 'title' and 'url' keys
            max_entities: Maximum entities per tab

        Returns:
            List of entity lists, maintaining input order (results[i] matches tabs[i])

        Example:
            >>> tabs = [
            ...     {"title": "React Hooks", "url": "https://react.dev/hooks"},
            ...     {"title": "FastAPI Tutorial", "url": "https://fastapi.tiangolo.com"}
            ... ]
            >>> extractor.extract_entities_batch(tabs)
            [["React", "Hooks", "JavaScript"], ["Python", "FastAPI", "API"]]
        """
        if not tabs:
            return []

        # Handle single tab edge case
        if len(tabs) == 1:
            return [self.extract_entities(tabs[0]["title"], tabs[0]["url"], max_entities=max_entities)]

        try:
            return self._extract_batch_with_llm(tabs, max_entities)
        except Exception as e:
            logger.warning(f"Batch LLM extraction failed: {e}, falling back to individual extraction")
            # Fallback: process each tab individually
            return [
                self.extract_entities(tab["title"], tab["url"], max_entities=max_entities)
                for tab in tabs
            ]

    def _extract_batch_with_llm(
        self,
        tabs: list[dict[str, str]],
        max_entities: int,
    ) -> list[list[str]]:
        """
        Extract entities for multiple tabs using LLM with Structured Outputs.

        Args:
            tabs: List of tabs with title and URL
            max_entities: Maximum entities per tab

        Returns:
            List of entity lists in same order as input
        """
        # Build structured input for the model
        tabs_text = "\n\n".join([
            f"Tab {i+1}:\nTitle: {tab['title']}\nURL: {tab['url']}"
            for i, tab in enumerate(tabs)
        ])

        prompt = f"""Extract key entities from each tab below. These are important keywords/topics related to the content. Return results in the SAME ORDER.

{tabs_text}

For EACH tab, extract 3-{max_entities} key entities. These can be:
- Main topics (e.g., "Photosynthesis", "French Revolution", "React")
- Key concepts (e.g., "Democracy", "Machine Learning", "Gene Editing")
- Important people, places, organizations (e.g., "Marie Curie", "Paris", "NASA")
- Specific subjects (e.g., "World War II", "JavaScript", "Climate Change")

Extract entities relevant to ANY domain (history, science, tech, business, etc.).
IMPORTANT: Maintain the exact order of tabs in your response."""

        # Call OpenAI with structured output (guarantees schema adherence)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting key topics and concepts. Extract entities relevant to the domain (tech, science, history, business, etc.) and maintain their order."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "batch_entity_extraction",
                    "schema": BATCH_ENTITY_SCHEMA,
                    "strict": True  # Enforces 100% schema adherence
                }
            },
            temperature=0.3,
            max_tokens=100 * len(tabs),  # Scale with number of tabs
        )

        # Parse structured response
        result = json.loads(response.choices[0].message.content)
        entities_list = [item["entities"] for item in result["results"]]

        # Validate we got the right number of results
        if len(entities_list) != len(tabs):
            raise ValueError(
                f"Expected {len(tabs)} results but got {len(entities_list)}"
            )

        return entities_list

    def _extract_with_llm(
        self,
        title: str,
        url: str,
        content: Optional[str],
        max_entities: int,
    ) -> list[str]:
        """
        Extract entities using LLM.

        Args:
            title: Tab title
            url: Tab URL
            content: Optional content
            max_entities: Maximum entities

        Returns:
            List of entity names
        """
        # Build context
        context = f"Title: {title}\nURL: {url}"
        if content:
            context += f"\nContent: {content[:500]}"

        # LLM prompt for entity extraction
        prompt = f"""Extract the most important keywords and topics from this content.

{context}

Return 3-{max_entities} key entities as a comma-separated list. These can be:
- Main topics (e.g., "Photosynthesis", "French Revolution", "React")
- Key concepts (e.g., "Democracy", "Machine Learning", "CRISPR")
- Important subjects (e.g., "World War II", "JavaScript", "Climate Change")

Extract entities relevant to ANY domain, not just technology.
Return ONLY the entity names, comma-separated, nothing else."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at extracting key topics and concepts. Return only entity names, comma-separated."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100,
        )

        # Parse response
        entities_text = response.choices[0].message.content.strip()
        entities = [e.strip() for e in entities_text.split(",")]

        # Clean and validate
        entities = [e for e in entities if e and len(e) > 1 and len(e) < 50]

        return entities[:max_entities]

    def _extract_with_keywords(
        self,
        title: str,
        url: str,
        max_entities: int,
    ) -> list[str]:
        """
        Fallback keyword-based entity extraction.

        Extracts capitalized words and common tech terms from title and URL.

        Args:
            title: Tab title
            url: Tab URL
            max_entities: Maximum entities

        Returns:
            List of entity names
        """
        entities = set()

        # Common tech keywords to look for
        tech_keywords = {
            "react", "vue", "angular", "python", "javascript", "typescript",
            "node", "django", "flask", "fastapi", "express",
            "docker", "kubernetes", "aws", "azure", "gcp",
            "mongodb", "postgresql", "mysql", "redis", "neo4j",
            "tensorflow", "pytorch", "ml", "ai", "api", "rest", "graphql",
            "git", "github", "gitlab", "nextjs", "next.js",
            "machine learning", "deep learning", "neural network",
            "database", "graph database", "sql", "nosql"
        }

        # Extract from title
        # Look for capitalized words (likely proper nouns)
        words = title.split()
        for word in words:
            cleaned = re.sub(r'[^\w\s-]', '', word)
            if cleaned and (cleaned[0].isupper() or cleaned.lower() in tech_keywords):
                if len(cleaned) > 2:
                    entities.add(cleaned)

        # Extract from URL
        # Look for tech terms in domain and path
        url_lower = url.lower()
        for keyword in tech_keywords:
            if keyword in url_lower:
                # Capitalize properly
                entities.add(keyword.title())

        # Extract domain name as potential entity
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            # Remove TLD
            domain_name = domain.split('.')[0]
            if domain_name and len(domain_name) > 2:
                entities.add(domain_name.title())

        # Convert to list and limit
        entity_list = sorted(list(entities))[:max_entities]

        # Ensure at least one entity
        if not entity_list:
            # Use domain or title as fallback
            if domain_match:
                entity_list = [domain_match.group(1).split('.')[0].title()]
            else:
                entity_list = [title.split()[0] if title else "Unknown"]

        return entity_list
