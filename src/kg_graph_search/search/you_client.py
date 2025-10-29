"""
You.com API client for web search integration.
"""

from typing import Any, Optional

import httpx
from pydantic import BaseModel


class SearchResult(BaseModel):
    """Individual search result from You.com."""

    title: str
    url: str
    snippet: str
    thumbnail_url: Optional[str] = None


class YouSearchResponse(BaseModel):
    """Response from You.com search API."""

    query: str
    results: list[SearchResult]
    hits_count: Optional[int] = None


class YouAPIClient:
    """Client for interacting with You.com API."""

    BASE_URL = "https://api.ydc-index.io"
    AGENT_BASE_URL = "https://api.you.com"  # Separate base URL for agent APIs

    def __init__(self, api_key: str):
        """
        Initialize the You.com API client.

        Args:
            api_key: Your You.com API key
        """
        self.api_key = api_key
        self.client = httpx.Client(
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # Separate client for agent APIs (uses Bearer token)
        self.agent_client = httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,  # Agents may take longer
        )

    async def async_client(self) -> httpx.AsyncClient:
        """Get an async HTTP client."""
        return httpx.AsyncClient(
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def search(
        self,
        query: str,
        num_results: int = 10,
        safesearch: str = "moderate",
        country: str = "US",
    ) -> YouSearchResponse:
        """
        Perform a web search using You.com API.

        Args:
            query: Search query string
            num_results: Number of results to return (default: 10)
            safesearch: Safe search level: "off", "moderate", or "strict"
            country: Country code for search results (default: "US")

        Returns:
            YouSearchResponse containing search results
        """
        response = self.client.get(
            f"{self.BASE_URL}/search",
            params={
                "query": query,
                "num_web_results": num_results,
                "safesearch": safesearch,
                "country": country,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Parse the response into our model
        results = []
        for hit in data.get("hits", []):
            results.append(
                SearchResult(
                    title=hit.get("title", ""),
                    url=hit.get("url", ""),
                    snippet=hit.get("description", ""),
                    thumbnail_url=hit.get("thumbnail_url"),
                )
            )

        return YouSearchResponse(
            query=query,
            results=results,
            hits_count=len(results),
        )

    async def async_search(
        self,
        query: str,
        num_results: int = 10,
        safesearch: str = "moderate",
        country: str = "US",
    ) -> YouSearchResponse:
        """
        Async version of search method.

        Args:
            query: Search query string
            num_results: Number of results to return (default: 10)
            safesearch: Safe search level: "off", "moderate", or "strict"
            country: Country code for search results (default: "US")

        Returns:
            YouSearchResponse containing search results
        """
        async with await self.async_client() as client:
            response = await client.get(
                f"{self.BASE_URL}/search",
                params={
                    "query": query,
                    "num_web_results": num_results,
                    "safesearch": safesearch,
                    "country": country,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Parse the response into our model
            results = []
            for hit in data.get("hits", []):
                results.append(
                    SearchResult(
                        title=hit.get("title", ""),
                        url=hit.get("url", ""),
                        snippet=hit.get("description", ""),
                        thumbnail_url=hit.get("thumbnail_url"),
                    )
                )

            return YouSearchResponse(
                query=query,
                results=results,
                hits_count=len(results),
            )

    def rag_search(
        self,
        query: str,
        num_results: int = 5,
    ) -> dict[str, Any]:
        """
        Perform a RAG (Retrieval Augmented Generation) search.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            RAG search response with generated answer
        """
        response = self.client.get(
            f"{self.BASE_URL}/rag",
            params={
                "query": query,
                "num_web_results": num_results,
            },
        )
        response.raise_for_status()
        return response.json()

    def express_agent_search(
        self,
        input: str,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Use You.com Express Agent for intelligent search with reasoning.

        Express Agent is optimized for low-latency queries that require web search.
        It provides more contextualized answers than basic search.

        Args:
            input: Query or prompt for the agent
            stream: Enable server-sent events for streaming (default: False)

        Returns:
            Agent response with answer and web search results

        Example:
            >>> client.express_agent_search(
            ...     "What are the best practices for React Hooks in 2025?"
            ... )
            {
                "output": [
                    {"type": "web_search.results", "content": "...", ...},
                    {"type": "chat_node.answer", "text": "Based on current best practices..."}
                ]
            }
        """
        payload = {
            "agent": "express",
            "input": input,
            "stream": stream,
        }

        response = self.agent_client.post(
            f"{self.AGENT_BASE_URL}/v1/agents/runs",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def custom_agent_run(
        self,
        agent_id: str,
        input: str,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Run a Custom Agent with specific instructions.

        Custom Agents allow you to define specialized behaviors and instructions
        for specific use cases (e.g., summarization, analysis, etc.).

        Args:
            agent_id: ID of your custom agent (created via You.com UI)
            input: Query or prompt for the agent
            stream: Enable server-sent events for streaming (default: False)

        Returns:
            Agent response based on custom instructions

        Note:
            Custom agents must be created via the You.com dashboard first.
        """
        payload = {
            "agent": agent_id,
            "input": input,
            "stream": stream,
        }

        response = self.agent_client.post(
            f"{self.AGENT_BASE_URL}/v1/agents/runs",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def advanced_agent_run(
        self,
        input: str,
        context: Optional[list[dict]] = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Use You.com Advanced Agent for complex multi-step reasoning.

        Advanced Agent can handle complex queries requiring planning, research,
        and multi-step reasoning across multiple sources.

        Args:
            input: Query or prompt for the agent
            context: Optional conversation context for continuity
            stream: Enable server-sent events for streaming (default: False)

        Returns:
            Agent response with detailed reasoning and sources

        Example:
            >>> client.advanced_agent_run(
            ...     "Analyze the trade-offs between REST and GraphQL APIs",
            ...     context=[{"role": "user", "content": "I'm building a mobile app"}]
            ... )
        """
        payload = {
            "agent": "advanced",
            "input": input,
            "stream": stream,
        }

        if context:
            payload["context"] = context

        response = self.agent_client.post(
            f"{self.AGENT_BASE_URL}/v1/agents/runs",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP clients."""
        self.client.close()
        self.agent_client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
