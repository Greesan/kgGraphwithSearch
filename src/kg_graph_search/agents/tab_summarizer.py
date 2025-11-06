"""
Tab summarization service using You.com API.

Generates concise summaries of webpage content for better context understanding.
"""

from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from kg_graph_search.config import get_logger
from kg_graph_search.search.you_client import YouAPIClient

logger = get_logger(__name__)


class TabSummarizer:
    """Service for generating tab summaries using You.com."""

    def __init__(self, you_client: YouAPIClient):
        """
        Initialize the tab summarizer.

        Args:
            you_client: You.com API client
        """
        self.you_client = you_client

    @retry(
        stop=stop_after_attempt(2),  # Lower retries for non-critical feature
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=False  # Don't raise on failure - tab can exist without summary
    )
    def summarize_tab(self, title: str, url: str) -> Optional[str]:
        """
        Generate a 2-3 sentence summary of a tab's content.

        Args:
            title: Tab title
            url: Tab URL

        Returns:
            Summary string or None if generation fails
        """
        try:
            summary = self.you_client.generate_tab_summary(title, url)
            if summary:
                logger.info(f"Generated summary for tab: {title[:50]}")
                return summary
            else:
                logger.warning(f"Failed to generate summary for tab: {title[:50]}")
                return None

        except Exception as e:
            logger.error(
                f"Error generating summary for tab '{title[:50]}': {e}",
                exc_info=True,
                extra={"title": title, "url": url}
            )
            return None
