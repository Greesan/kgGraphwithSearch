"""
You.com metadata provider implementation.
"""

from typing import Optional
import json
import re

from kg_graph_search.agents.metadata_provider import MetadataProvider, TabMetadata
from kg_graph_search.search.you_client import YouAPIClient
from kg_graph_search.config import get_logger

logger = get_logger(__name__)


class YouMetadataProvider(MetadataProvider):
    """Tab metadata provider using You.com Express Agent."""

    def __init__(self, you_client: YouAPIClient):
        """
        Initialize You.com provider.

        Args:
            you_client: You.com API client instance
        """
        self.you_client = you_client

    def generate_metadata(
        self,
        title: str,
        url: str
    ) -> Optional[TabMetadata]:
        """Generate metadata using You.com Express Agent."""
        try:
            prompt = f"""Generate metadata for this webpage:

Title: {title}
URL: {url}

Respond with ONLY this JSON (no other text):
{{
  "label": "concise 6-word-max description",
  "source": "author/org/site (use 'Author, Publication' for articles/social media)",
  "summary": "2-3 sentence summary"
}}"""

            response = self.you_client.express_agent_search(prompt)

            # Parse JSON from response
            for output in response.get("output", []):
                if output.get("type") in ["message.answer", "chat_node.answer"]:
                    text = output.get("text", "").strip()
                    data = self._extract_json(text)
                    if data and self._validate_metadata(data):
                        return self._format_metadata(data, url)

            logger.warning(f"Failed to parse You.com response for: {title[:50]}")
            return self._fallback_metadata(title, url)

        except Exception as e:
            logger.error(f"Error generating metadata with You.com: {e}")
            return self._fallback_metadata(title, url)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from possibly noisy response."""
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass

        # Try to find JSON in text
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass

        logger.debug(f"Could not extract JSON from: {text[:100]}")
        return None

    def _validate_metadata(self, data: dict) -> bool:
        """Validate that metadata dict has required fields."""
        return (
            isinstance(data, dict) and
            "label" in data and
            "source" in data and
            "summary" in data
        )

    def _format_metadata(self, data: dict, url: str) -> TabMetadata:
        """Format raw data into TabMetadata."""
        label = str(data.get("label", ""))[:60].strip()
        source = str(data.get("source", ""))[:100].strip()
        summary = str(data.get("summary", ""))[:500].strip()

        # Fallback to domain if source is empty
        if not source:
            source = self._extract_domain(url)

        # Fallback to truncated label if label is empty
        if not label:
            label = "Untitled Page"

        return TabMetadata(
            label=label,
            source=source,
            summary=summary,
            display_label=f"{label} • {source}"
        )
