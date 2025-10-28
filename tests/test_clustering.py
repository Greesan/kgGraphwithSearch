"""
Unit tests for tab clustering functionality.

Tests the core clustering logic including:
- Centroid updates on add/remove
- Cluster naming and renaming
- Cluster deletion when < 2 tabs
- Similarity-based assignment
"""

import pytest
from unittest.mock import Mock, patch
import numpy as np
from datetime import datetime

from kg_graph_search.agents.models import Tab, TabCluster, ClusterColor
from kg_graph_search.agents.tab_clusterer import TabClusterer


@pytest.fixture
def mock_settings():
    """Mock settings to avoid requiring .env file."""
    with patch("kg_graph_search.agents.tab_clusterer.get_settings") as mock:
        settings = Mock()
        settings.openai_api_key = "test-api-key"
        settings.openai_embedding_model = "text-embedding-3-small"
        settings.openai_llm_model = "gpt-4o-mini"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_openai(mock_settings):
    """Mock OpenAI client for testing without API calls."""
    with patch("kg_graph_search.agents.tab_clusterer.OpenAI") as mock:
        # Mock embedding response
        mock_client = Mock()
        mock_embedding = Mock()
        mock_embedding.data = [Mock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_embedding

        # Mock chat completion response
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Test Cluster"))]
        mock_client.chat.completions.create.return_value = mock_completion

        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_tab():
    """Create a sample tab for testing."""
    return Tab(
        id=1,
        url="https://neo4j.com/docs",
        title="Neo4j Documentation",
        embedding=[0.1, 0.8, 0.2] + [0.0] * 1533,  # 1536-dim embedding
    )


@pytest.fixture
def sample_cluster(sample_tab):
    """Create a sample cluster with one tab."""
    cluster = TabCluster(
        id="test-cluster-1",
        name="Graph Database Research",
        color=ClusterColor.BLUE,
        tabs=[sample_tab],
        tab_count=1,
        confidence=1.0,
    )
    cluster.update_centroid()
    return cluster


class TestTabCluster:
    """Tests for TabCluster model."""

    def test_update_centroid_single_tab(self, sample_tab):
        """Test centroid calculation with single tab."""
        cluster = TabCluster(
            id="test-1",
            name="Test",
            tabs=[sample_tab],
        )
        cluster.update_centroid()

        assert cluster.centroid_embedding is not None
        assert len(cluster.centroid_embedding) == 1536
        # With single tab, centroid should equal tab embedding
        assert cluster.centroid_embedding == sample_tab.embedding

    def test_update_centroid_multiple_tabs(self):
        """Test centroid calculation with multiple tabs."""
        tab1 = Tab(id=1, url="test1", title="Test 1", embedding=[1.0, 0.0, 0.0])
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.0, 1.0, 0.0])
        tab3 = Tab(id=3, url="test3", title="Test 3", embedding=[0.0, 0.0, 1.0])

        cluster = TabCluster(
            id="test-1",
            name="Test",
            tabs=[tab1, tab2, tab3],
        )
        cluster.update_centroid()

        # Centroid should be mean of all embeddings
        expected = [1.0/3, 1.0/3, 1.0/3]
        np.testing.assert_array_almost_equal(
            cluster.centroid_embedding,
            expected,
            decimal=5
        )

    def test_update_centroid_empty_cluster(self):
        """Test centroid calculation with no tabs."""
        cluster = TabCluster(id="test-1", name="Test", tabs=[])
        cluster.update_centroid()

        assert cluster.centroid_embedding is None

    def test_add_tab_marks_centroid_dirty(self, sample_cluster, sample_tab):
        """Test that adding tab marks centroid as dirty."""
        new_tab = Tab(
            id=2,
            url="https://neo4j.com/cypher",
            title="Cypher Tutorial",
            embedding=[0.15, 0.75, 0.25] + [0.0] * 1533,
        )

        initial_centroid = sample_cluster.centroid_embedding.copy()
        sample_cluster.add_tab(new_tab)

        assert sample_cluster._centroid_dirty is True
        assert sample_cluster.tab_count == 2
        assert sample_cluster.tabs_added_since_naming == 1

    def test_remove_tab_marks_centroid_dirty(self, sample_cluster, sample_tab):
        """Test that removing tab marks centroid as dirty."""
        # Add another tab first
        new_tab = Tab(
            id=2,
            url="https://neo4j.com/cypher",
            title="Cypher Tutorial",
            embedding=[0.15, 0.75, 0.25] + [0.0] * 1533,
        )
        sample_cluster.add_tab(new_tab)
        sample_cluster.update_centroid()
        sample_cluster._centroid_dirty = False

        # Now remove it
        removed = sample_cluster.remove_tab(new_tab.id)

        assert removed is True
        assert sample_cluster._centroid_dirty is True
        assert sample_cluster.tab_count == 1

    def test_should_regenerate_name(self, sample_cluster):
        """Test cluster rename threshold."""
        assert sample_cluster.should_regenerate_name(threshold=3) is False

        sample_cluster.tabs_added_since_naming = 3
        assert sample_cluster.should_regenerate_name(threshold=3) is True

    def test_mark_for_deletion(self, sample_cluster):
        """Test cluster deletion condition."""
        # With 1 tab, should be marked for deletion
        assert sample_cluster.mark_for_deletion() is True

        # Add a tab to make it 2
        new_tab = Tab(id=2, url="test", title="Test", embedding=[0.1] * 1536)
        sample_cluster.add_tab(new_tab)
        assert sample_cluster.mark_for_deletion() is False


class TestTabClusterer:
    """Tests for TabClusterer service."""

    def test_initialization(self, mock_openai):
        """Test clusterer initialization."""
        clusterer = TabClusterer(
            similarity_threshold=0.8,
            rename_threshold=5,
        )

        assert clusterer.similarity_threshold == 0.8
        assert clusterer.rename_threshold == 5
        assert len(clusterer.clusters) == 0

    def test_cosine_similarity(self, mock_openai):
        """Test cosine similarity calculation."""
        clusterer = TabClusterer()

        # Identical vectors
        sim = clusterer._cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        assert sim == pytest.approx(1.0)

        # Orthogonal vectors
        sim = clusterer._cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        assert sim == pytest.approx(0.0)

        # Opposite vectors
        sim = clusterer._cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
        assert sim == pytest.approx(-1.0)

    def test_generate_embedding(self, mock_openai):
        """Test embedding generation via OpenAI."""
        clusterer = TabClusterer()
        embedding = clusterer.generate_embedding("Test text")

        assert embedding is not None
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    def test_create_new_cluster(self, mock_openai, sample_tab):
        """Test creating a new cluster."""
        clusterer = TabClusterer()
        cluster = clusterer.create_new_cluster(sample_tab)

        assert len(clusterer.clusters) == 1
        assert cluster.tab_count == 1
        assert sample_tab in cluster.tabs
        assert cluster.centroid_embedding is not None

    def test_add_tab_to_cluster_updates_centroid(self, mock_openai, sample_cluster):
        """Test that adding tab updates centroid."""
        clusterer = TabClusterer()
        clusterer.clusters.append(sample_cluster)

        initial_centroid = sample_cluster.centroid_embedding.copy()

        new_tab = Tab(
            id=2,
            url="https://neo4j.com/cypher",
            title="Cypher Tutorial",
            embedding=[0.2, 0.7, 0.3] + [0.0] * 1533,
        )

        clusterer.add_tab_to_cluster(sample_cluster, new_tab)

        # Centroid should be updated
        assert sample_cluster.centroid_embedding != initial_centroid
        assert sample_cluster.tab_count == 2
        assert sample_cluster.tabs_added_since_naming == 1

    def test_remove_tab_from_cluster_updates_centroid(self, mock_openai, sample_cluster):
        """Test that removing tab updates centroid (prevents ghost cluster)."""
        clusterer = TabClusterer()
        clusterer.clusters.append(sample_cluster)

        # Add two more tabs
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.2, 0.7, 0.3] + [0.0] * 1533)
        tab3 = Tab(id=3, url="test3", title="Test 3", embedding=[0.15, 0.75, 0.25] + [0.0] * 1533)

        clusterer.add_tab_to_cluster(sample_cluster, tab2)
        clusterer.add_tab_to_cluster(sample_cluster, tab3)

        centroid_before = sample_cluster.centroid_embedding.copy()

        # Remove tab2
        removed = clusterer.remove_tab_from_cluster(sample_cluster, tab2.id)

        assert removed is True
        assert sample_cluster.tab_count == 2
        # Centroid MUST be updated to reflect current tabs only
        assert sample_cluster.centroid_embedding != centroid_before

    def test_remove_tab_deletes_cluster_when_too_small(self, mock_openai, sample_cluster):
        """Test that cluster is deleted when it drops below 2 tabs."""
        clusterer = TabClusterer()
        clusterer.clusters.append(sample_cluster)

        # Add one more tab (total: 2)
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.1] * 1536)
        clusterer.add_tab_to_cluster(sample_cluster, tab2)

        assert len(clusterer.clusters) == 1

        # Remove one tab (down to 1)
        clusterer.remove_tab_from_cluster(sample_cluster, tab2.id)

        # Cluster should be deleted
        assert len(clusterer.clusters) == 0

    def test_rename_triggered_only_by_additions(self, mock_openai, sample_cluster):
        """Test that rename is only triggered by additions, not removals."""
        clusterer = TabClusterer(rename_threshold=2)
        clusterer.clusters.append(sample_cluster)

        # Add 2 tabs (should trigger rename)
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.1] * 1536)
        tab3 = Tab(id=3, url="test3", title="Test 3", embedding=[0.1] * 1536)

        initial_name = sample_cluster.name

        clusterer.add_tab_to_cluster(sample_cluster, tab2)
        clusterer.add_tab_to_cluster(sample_cluster, tab3)

        # Name should have changed (mocked to "Test Cluster")
        assert sample_cluster.name != initial_name
        assert sample_cluster.tabs_added_since_naming == 0  # Reset after rename

        # Now remove a tab
        current_name = sample_cluster.name
        clusterer.remove_tab_from_cluster(sample_cluster, tab3.id)

        # Name should NOT change on removal
        assert sample_cluster.name == current_name

    def test_find_best_cluster_above_threshold(self, mock_openai):
        """Test finding best cluster when similarity is above threshold."""
        clusterer = TabClusterer(similarity_threshold=0.75)

        # Create cluster with specific embedding
        tab1 = Tab(id=1, url="test1", title="Test 1", embedding=[1.0, 0.0, 0.0])
        cluster = clusterer.create_new_cluster(tab1)

        # Create similar tab (should match)
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.9, 0.1, 0.0])

        result = clusterer.find_best_cluster(tab2)

        assert result is not None
        best_cluster, similarity = result
        assert best_cluster.id == cluster.id
        assert similarity > 0.75

    def test_find_best_cluster_below_threshold(self, mock_openai):
        """Test that dissimilar tab doesn't match existing cluster."""
        clusterer = TabClusterer(similarity_threshold=0.75)

        # Create cluster with specific embedding
        tab1 = Tab(id=1, url="test1", title="Test 1", embedding=[1.0, 0.0, 0.0])
        cluster = clusterer.create_new_cluster(tab1)

        # Create dissimilar tab (should NOT match)
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.0, 1.0, 0.0])

        result = clusterer.find_best_cluster(tab2)

        assert result is None

    def test_process_tab_creates_new_cluster_when_no_match(self, mock_openai):
        """Test that process_tab creates new cluster when no match found."""
        clusterer = TabClusterer(similarity_threshold=0.9)

        # Use explicit different embeddings to avoid mock collision
        tab1 = Tab(id=1, url="test1", title="Test 1", embedding=[1.0, 0.0, 0.0])
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[0.0, 1.0, 0.0])

        clusterer.process_tab(tab1)
        assert len(clusterer.clusters) == 1

        # Second tab with very different embedding should create new cluster
        clusterer.process_tab(tab2)
        assert len(clusterer.clusters) == 2

    def test_process_tab_assigns_to_existing_cluster_when_match(self, mock_openai):
        """Test that process_tab assigns to existing cluster when match found."""
        clusterer = TabClusterer(similarity_threshold=0.5)

        # Create tabs with identical embeddings (will definitely match)
        tab1 = Tab(id=1, url="test1", title="Test 1", embedding=[1.0, 0.0, 0.0])
        tab2 = Tab(id=2, url="test2", title="Test 2", embedding=[1.0, 0.0, 0.0])

        clusterer.process_tab(tab1)
        assert len(clusterer.clusters) == 1

        clusterer.process_tab(tab2)
        assert len(clusterer.clusters) == 1  # Should join existing cluster
        assert clusterer.clusters[0].tab_count == 2

    def test_get_cluster_stats(self, mock_openai, sample_tab):
        """Test cluster statistics generation."""
        clusterer = TabClusterer()
        clusterer.create_new_cluster(sample_tab)

        stats = clusterer.get_cluster_stats()

        assert stats["total_clusters"] == 1
        assert stats["total_tabs"] == 1
        assert stats["avg_tabs_per_cluster"] == 1.0
        assert len(stats["clusters"]) == 1


class TestCentroidConsistency:
    """Integration tests for centroid consistency across operations."""

    def test_centroid_reflects_current_tabs_only(self, mock_openai):
        """
        Test that centroid always reflects current tabs, not deleted ones.
        This is the "ghost cluster" prevention test.
        """
        clusterer = TabClusterer(similarity_threshold=0.7)

        # Create cluster with React and Vue tabs
        react_tabs = [
            Tab(id=1, url="react1", title="React 1", embedding=[0.2, 0.8, 0.0]),
            Tab(id=2, url="react2", title="React 2", embedding=[0.25, 0.75, 0.0]),
            Tab(id=3, url="react3", title="React 3", embedding=[0.2, 0.8, 0.0]),
        ]

        vue_tabs = [
            Tab(id=4, url="vue1", title="Vue 1", embedding=[0.8, 0.2, 0.0]),
            Tab(id=5, url="vue2", title="Vue 2", embedding=[0.75, 0.25, 0.0]),
        ]

        # Create mixed cluster
        cluster = clusterer.create_new_cluster(react_tabs[0])
        for tab in react_tabs[1:] + vue_tabs:
            clusterer.add_tab_to_cluster(cluster, tab)

        # Centroid should be mixed
        mixed_centroid = cluster.centroid_embedding.copy()

        # Remove all Vue tabs
        for vue_tab in vue_tabs:
            clusterer.remove_tab_from_cluster(cluster, vue_tab.id)

        # Centroid should now be pure React (NOT mixed)
        pure_react_centroid = cluster.centroid_embedding.copy()

        # Verify centroid changed
        assert pure_react_centroid != mixed_centroid

        # New Vue tab should NOT match pure React centroid
        new_vue_tab = Tab(id=6, url="vue3", title="Vue 3", embedding=[0.8, 0.2, 0.0])
        similarity = clusterer._cosine_similarity(
            new_vue_tab.embedding,
            cluster.centroid_embedding
        )

        # Similarity should be low (Vue vs React)
        assert similarity < 0.7  # Below threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
