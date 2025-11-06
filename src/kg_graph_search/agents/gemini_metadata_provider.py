"""
Gemini metadata provider implementations.

Supports both non-grounding (fast) and grounding (slow/accurate) modes.
"""

from typing import Optional
import json

from kg_graph_search.agents.metadata_provider import MetadataProvider, TabMetadata
from kg_graph_search.config import get_logger

logger = get_logger(__name__)


class GeminiMetadataProvider(MetadataProvider):
    """Tab metadata provider using Gemini (non-grounding, fast)."""

    def __init__(self, api_key: str):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google Gemini API key
        """
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.genai = genai

            # JSON schema for structured output
            self.response_schema = {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "maxLength": 60,
                        "description": "Concise 6-word-max description"
                    },
                    "source": {
                        "type": "string",
                        "description": "Author/org/site (use 'Author, Publication' for articles/social)"
                    },
                    "summary": {
                        "type": "string",
                        "maxLength": 500,
                        "description": "2-3 sentence summary"
                    }
                },
                "required": ["label", "source", "summary"]
            }

            logger.info("Initialized Gemini metadata provider (non-grounding)")

        except ImportError:
            logger.error("google-generativeai package not installed. Run: pip install google-generativeai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            raise

    def generate_metadata(
        self,
        title: str,
        url: str
    ) -> Optional[TabMetadata]:
        """Generate metadata using Gemini with structured output."""
        try:
            prompt = f"""Generate metadata for this webpage:

Title: {title}
URL: {url}

Provide:
- label: Concise 6-word-max description
- source: Most relevant attribution (for social/articles use "Author, Platform")
- summary: 2-3 sentence summary"""

            response = self.model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": self.response_schema
                }
            )

            # Guaranteed valid JSON from Gemini!
            data = json.loads(response.text)

            return TabMetadata(
                label=data["label"],
                source=data["source"],
                summary=data["summary"],
                display_label=f"{data['label']} • {data['source']}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            return self._fallback_metadata(title, url)
        except Exception as e:
            logger.error(f"Error generating metadata with Gemini: {e}")
            return self._fallback_metadata(title, url)


class GeminiGroundedProvider(GeminiMetadataProvider):
    """Tab metadata provider using Gemini with web grounding (slow but accurate)."""

    def __init__(self, api_key: str):
        """
        Initialize Gemini grounded provider.

        Args:
            api_key: Google Gemini API key
        """
        super().__init__(api_key)

        try:
            # Enable grounding tool
            from google.generativeai.types import Tool, GoogleSearchRetrieval
            self.search_tool = Tool(google_search_retrieval=GoogleSearchRetrieval())
            logger.info("Initialized Gemini metadata provider (WITH grounding)")
        except Exception as e:
            logger.error(f"Failed to initialize grounding tool: {e}")
            raise

    def generate_metadata(
        self,
        title: str,
        url: str
    ) -> Optional[TabMetadata]:
        """Generate metadata using Gemini with web grounding."""
        try:
            prompt = f"""Fetch and analyze this webpage to generate accurate metadata:

URL: {url}
Title (for reference): {title}

Provide based on actual page content:
- label: Concise 6-word-max description
- source: Most relevant attribution from the page
- summary: 2-3 sentence summary of actual content"""

            response = self.model.generate_content(
                prompt,
                tools=[self.search_tool],  # Enable grounding
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": self.response_schema
                }
            )

            data = json.loads(response.text)

            return TabMetadata(
                label=data["label"],
                source=data["source"],
                summary=data["summary"],
                display_label=f"{data['label']} • {data['source']}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            return self._fallback_metadata(title, url)
        except Exception as e:
            logger.error(f"Error generating grounded metadata with Gemini: {e}")
            return self._fallback_metadata(title, url)
