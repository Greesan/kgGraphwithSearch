"""
Pytest configuration and fixtures for backend API tests.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_clusterer():
    """Reset the global clusterer state between tests."""
    import kg_graph_search.server.app as app_module

    # Reset global clusterer
    app_module._clusterer = None
    yield
    # Clean up after test
    app_module._clusterer = None


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings to avoid requiring .env file in tests."""
    with patch("kg_graph_search.agents.tab_clusterer.get_settings") as mock_clusterer_settings, \
         patch("kg_graph_search.config.get_settings") as mock_config_settings:
        settings = Mock()
        settings.openai_api_key = "test-api-key"
        settings.you_api_key = "test-you-api-key"
        settings.openai_embedding_model = "text-embedding-3-small"
        settings.openai_llm_model = "gpt-4o-mini"
        settings.db_path = ":memory:"  # In-memory SQLite for tests
        mock_clusterer_settings.return_value = settings
        mock_config_settings.return_value = settings
        yield settings


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client to avoid real API calls in tests."""
    with patch("kg_graph_search.agents.tab_clusterer.OpenAI") as mock:
        mock_client = Mock()

        def mock_embeddings_create(model, input):
            """Mock embeddings.create that handles both single and batch inputs."""
            mock_response = Mock()
            if isinstance(input, list):
                # Batch mode: return multiple embeddings
                mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in input]
            else:
                # Single mode: return one embedding
                mock_response.data = [Mock(embedding=[0.1] * 1536)]
            return mock_response

        mock_client.embeddings.create.side_effect = mock_embeddings_create

        # Mock chat completion response
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Test Cluster"))]
        mock_client.chat.completions.create.return_value = mock_completion

        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_tabs_data():
    """Sample tab data for testing API endpoints."""
    return {
        "tabs": [
            {
                "id": 1,
                "url": "https://neo4j.com/docs",
                "title": "Neo4j Documentation - Graph Database",
                "favicon_url": "https://neo4j.com/favicon.ico",
                "important": False,
            },
            {
                "id": 2,
                "url": "https://react.dev/learn",
                "title": "React Documentation - Learn React",
                "favicon_url": "https://react.dev/favicon.ico",
                "important": False,
            },
            {
                "id": 3,
                "url": "https://neo4j.com/cypher",
                "title": "Cypher Query Language Guide",
                "favicon_url": "https://neo4j.com/favicon.ico",
                "important": True,
                "content": "Cypher is a declarative graph query language...",
            },
        ],
        "timestamp": "2025-10-28T10:00:00Z",
    }
