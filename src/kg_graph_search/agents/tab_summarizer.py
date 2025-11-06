"""
Tab summarization service with pluggable metadata providers.

Supports multiple AI providers (You.com, Gemini) for generating tab metadata.
"""

from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

from kg_graph_search.config import get_logger, get_settings, Settings
from kg_graph_search.agents.metadata_provider import MetadataProvider, TabMetadata
from kg_graph_search.agents.you_metadata_provider import YouMetadataProvider
from kg_graph_search.search.you_client import YouAPIClient

logger = get_logger(__name__)


def get_metadata_provider(
    settings: Settings,
    you_client: Optional[YouAPIClient] = None
) -> MetadataProvider:
    """
    Get the configured metadata provider.

    Args:
        settings: Application settings
        you_client: You.com client (required if using You.com provider)

    Returns:
        Configured metadata provider instance
    """
    provider = settings.tab_metadata_provider.lower()

    if provider == "you":
        if not you_client:
            raise ValueError("You.com provider requires you_client parameter")
        return YouMetadataProvider(you_client)

    elif provider == "gemini":
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set, falling back to You.com")
            if not you_client:
                raise ValueError("Fallback requires you_client parameter")
            return YouMetadataProvider(you_client)

        from kg_graph_search.agents.gemini_metadata_provider import GeminiMetadataProvider
        return GeminiMetadataProvider(settings.gemini_api_key)

    elif provider == "gemini_grounded":
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set, falling back to You.com")
            if not you_client:
                raise ValueError("Fallback requires you_client parameter")
            return YouMetadataProvider(you_client)

        from kg_graph_search.agents.gemini_metadata_provider import GeminiGroundedProvider
        return GeminiGroundedProvider(settings.gemini_api_key)

    else:
        logger.warning(f"Unknown provider '{provider}', using You.com")
        if not you_client:
            raise ValueError("Fallback requires you_client parameter")
        return YouMetadataProvider(you_client)


class TabSummarizer:
    """Service for generating tab metadata using configured provider."""

    def __init__(self, provider: MetadataProvider):
        """
        Initialize the tab summarizer.

        Args:
            provider: Metadata provider instance
        """
        self.provider = provider

    @retry(
        stop=stop_after_attempt(2),  # Lower retries for non-critical feature
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False  # Don't raise on failure - tab can exist without metadata
    )
    def summarize_tab(self, title: str, url: str) -> Optional[TabMetadata]:
        """
        Generate metadata for a tab (label, source, summary).

        Args:
            title: Tab title
            url: Tab URL

        Returns:
            TabMetadata dict or None if generation fails
        """
        try:
            metadata = self.provider.generate_metadata(title, url)
            if metadata:
                logger.info(f"Generated metadata for tab: {title[:50]}")
                return metadata
            else:
                logger.warning(f"Failed to generate metadata for tab: {title[:50]}")
                return None

        except Exception as e:
            logger.error(
                f"Error generating metadata for tab '{title[:50]}': {e}",
                exc_info=True,
                extra={"title": title, "url": url}
            )
            return None
