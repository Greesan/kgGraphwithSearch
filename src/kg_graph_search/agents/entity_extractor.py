"""
Entity extraction service for knowledge graph.

Extracts key concepts, technologies, and topics from tab titles and URLs.
Uses LLM for intelligent extraction with fallback to keyword-based extraction.
"""

import re
from typing import Optional
from openai import OpenAI


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
            print(f"LLM extraction failed: {e}, falling back to keyword extraction")

        # Fallback to keyword extraction
        return self._extract_with_keywords(title, url, max_entities)

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
        prompt = f"""Extract the most important technical concepts, technologies, tools, frameworks, and topics from this webpage.

{context}

Return 3-{max_entities} key entities as a comma-separated list. Focus on:
- Technologies (e.g., "React", "Python", "Neo4j")
- Frameworks (e.g., "Next.js", "Django")
- Concepts (e.g., "Machine Learning", "Graph Database")
- Tools (e.g., "Docker", "Git")

Return ONLY the entity names, comma-separated, nothing else."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at extracting key technical concepts from webpages. Return only entity names, comma-separated."},
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
