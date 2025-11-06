"""
Tab metadata generation providers.

Supports multiple AI providers for generating tab labels, sources, and summaries.
"""

from abc import ABC, abstractmethod
from typing import Optional, TypedDict
from urllib.parse import urlparse
import json
import re

from kg_graph_search.config import get_logger

logger = get_logger(__name__)


class TabMetadata(TypedDict):
    """Structured tab metadata."""
    label: str  # 6-word-max concise description
    source: str  # Author, org, or site name
    summary: str  # 2-3 sentence summary
    display_label: str  # Formatted: "{label} • {source}"


class MetadataProvider(ABC):
    """Abstract base for tab metadata providers."""

    @abstractmethod
    def generate_metadata(
        self,
        title: str,
        url: str
    ) -> Optional[TabMetadata]:
        """
        Generate metadata for a tab.

        Args:
            title: The browser tab title
            url: The tab URL

        Returns:
            TabMetadata dict or None if generation fails
        """
        pass

    def _extract_domain(self, url: str) -> str:
        """
        Extract clean domain name from URL.

        Examples:
            https://github.com/user/repo → GitHub
            https://docs.anthropic.com/... → Anthropic
            https://medium.com/@user → Medium
        """
        try:
            domain = urlparse(url).netloc
            domain = domain.replace('www.', '')

            # Handle subdomains
            if domain.startswith('docs.'):
                # docs.anthropic.com → Anthropic
                domain = domain.replace('docs.', '').split('.')[0].title()
            elif domain.startswith('api.'):
                # api.example.com → Example
                domain = domain.replace('api.', '').split('.')[0].title()
            else:
                # github.com → GitHub
                domain = domain.split('.')[0].title()

            return domain
        except:
            return "Web"

    def _fallback_metadata(self, title: str, url: str) -> TabMetadata:
        """Generate fallback metadata when AI generation fails."""
        domain = self._extract_domain(url)
        truncated_title = title[:50] if title else "Untitled"

        return TabMetadata(
            label=truncated_title,
            source=domain,
            summary="",
            display_label=f"{truncated_title} • {domain}"
        )
