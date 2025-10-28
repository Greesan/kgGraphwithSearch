"""
Tests for FastAPI backend endpoints.

Following TDD approach: Tests written first, then implementation.
"""

import pytest
from fastapi.testclient import TestClient


class TestTabsIngestEndpoint:
    """Tests for POST /api/tabs/ingest endpoint."""

    def test_ingest_tabs_returns_success(self, mock_settings, mock_openai, sample_tabs_data):
        """Test that ingesting tabs returns a successful response."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.post("/api/tabs/ingest", json=sample_tabs_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processed"] == 3
        assert "session_id" in data

    def test_ingest_tabs_creates_clusters(self, mock_settings, mock_openai, sample_tabs_data):
        """Test that ingesting tabs creates appropriate clusters."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.post("/api/tabs/ingest", json=sample_tabs_data)

        assert response.status_code == 200
        data = response.json()

        # Should process all tabs
        assert data["processed"] == 3

        # Now get clusters
        clusters_response = client.get("/api/tabs/clusters")
        assert clusters_response.status_code == 200
        clusters_data = clusters_response.json()

        # Should have at least one cluster
        assert len(clusters_data["clusters"]) >= 1

    def test_ingest_empty_tabs_list(self, mock_settings, mock_openai):
        """Test ingesting an empty tabs list."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.post("/api/tabs/ingest", json={"tabs": [], "timestamp": "2025-10-28T10:00:00Z"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processed"] == 0

    def test_ingest_tabs_with_important_flag(self, mock_settings, mock_openai, sample_tabs_data):
        """Test that important tabs are marked correctly."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.post("/api/tabs/ingest", json=sample_tabs_data)

        assert response.status_code == 200
        data = response.json()

        # One tab is marked important
        assert data["important_tabs"] == 1

    def test_ingest_tabs_validates_required_fields(self, mock_settings, mock_openai):
        """Test that endpoint validates required tab fields."""
        from kg_graph_search.server.app import app

        client = TestClient(app)

        # Missing title field
        invalid_data = {
            "tabs": [
                {
                    "id": 1,
                    "url": "https://example.com",
                    # title missing
                }
            ],
            "timestamp": "2025-10-28T10:00:00Z",
        }

        response = client.post("/api/tabs/ingest", json=invalid_data)
        assert response.status_code == 422  # Validation error


class TestTabsClustersEndpoint:
    """Tests for GET /api/tabs/clusters endpoint."""

    def test_get_clusters_returns_empty_initially(self, mock_settings, mock_openai):
        """Test that clusters endpoint returns empty list initially."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.get("/api/tabs/clusters")

        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data
        assert isinstance(data["clusters"], list)
        assert len(data["clusters"]) == 0

    def test_get_clusters_after_ingest(self, mock_settings, mock_openai, sample_tabs_data):
        """Test getting clusters after ingesting tabs."""
        from kg_graph_search.server.app import app

        client = TestClient(app)

        # First ingest tabs
        client.post("/api/tabs/ingest", json=sample_tabs_data)

        # Then get clusters
        response = client.get("/api/tabs/clusters")
        assert response.status_code == 200
        data = response.json()

        assert len(data["clusters"]) >= 1

        # Check cluster structure
        cluster = data["clusters"][0]
        assert "id" in cluster
        assert "name" in cluster
        assert "color" in cluster
        assert "tabs" in cluster
        assert "tab_count" in cluster

    def test_clusters_response_includes_relationships(self, mock_settings, mock_openai, sample_tabs_data):
        """Test that clusters response includes tab relationships."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        client.post("/api/tabs/ingest", json=sample_tabs_data)

        response = client.get("/api/tabs/clusters")
        assert response.status_code == 200
        data = response.json()

        assert "relationships" in data
        assert isinstance(data["relationships"], list)


class TestRecommendationsEndpoint:
    """Tests for GET /api/recommendations endpoint."""

    def test_recommendations_endpoint_exists(self, mock_settings):
        """Test that recommendations endpoint is accessible."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.get("/api/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data

    def test_recommendations_with_cluster_id_filter(self, mock_settings, mock_openai, sample_tabs_data):
        """Test filtering recommendations by cluster ID."""
        from kg_graph_search.server.app import app

        client = TestClient(app)

        # Ingest tabs first
        client.post("/api/tabs/ingest", json=sample_tabs_data)

        # Get clusters
        clusters_response = client.get("/api/tabs/clusters")
        clusters = clusters_response.json()["clusters"]

        if clusters:
            cluster_id = clusters[0]["id"]
            response = client.get(f"/api/recommendations?cluster_id={cluster_id}")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["recommendations"], list)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, mock_settings):
        """Test that health check endpoint works."""
        from kg_graph_search.server.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
