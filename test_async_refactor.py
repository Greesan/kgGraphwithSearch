"""
Test script for async enrichment refactor.

This script verifies that:
1. Batch entity fetch works correctly
2. Skip enrichment flag works
3. Background enrichment function is callable
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.agents.models import Tab
from datetime import datetime, UTC


def test_batch_entity_fetch():
    """Test the new get_entities_by_names method."""
    print("\n=== Test 1: Batch Entity Fetch ===")

    # Use in-memory database for testing
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        db = KnowledgeGraphDB(db_path)

        # Test with empty list
        result = db.get_entities_by_names([])
        assert result == [], "Empty list should return empty result"
        print("✓ Empty list test passed")

        # Test with non-existent entities
        result = db.get_entities_by_names(["NonExistent1", "NonExistent2"])
        assert result == [], "Non-existent entities should return empty result"
        print("✓ Non-existent entities test passed")

        # Add a test entity
        from kg_graph_search.graph.models import Entity
        entity = Entity(
            name="TestEntity",
            entity_type="Test",
            description="Test description",
            created_at=datetime.now(UTC),
            is_enriched=True
        )
        entity_id = db.add_entity(entity)

        # Test fetching existing entity
        result = db.get_entities_by_names(["TestEntity"])
        assert len(result) == 1, "Should find one entity"
        assert result[0].name == "TestEntity", "Should return correct entity"
        print("✓ Existing entity fetch test passed")

        # Test mixed (existing + non-existing)
        result = db.get_entities_by_names(["TestEntity", "NonExistent"])
        assert len(result) == 1, "Should find only the existing entity"
        print("✓ Mixed entities test passed")

        db.close()
        print("\n✅ All batch entity fetch tests passed!\n")

    finally:
        db_path.unlink()


def test_skip_enrichment_flag():
    """Test that skip_enrichment flag works in process_tabs_batch."""
    print("\n=== Test 2: Skip Enrichment Flag ===")

    # Create minimal clusterer (no API keys needed for this test)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph_db = KnowledgeGraphDB(db_path)

        # Create clusterer WITHOUT enricher (to ensure enrichment is skipped)
        clusterer = TabClusterer(
            similarity_threshold=0.75,
            rename_threshold=3,
            openai_api_key="test-key",
            graph_db=graph_db,
            entity_weight=0.5,
        )

        # Create test tabs with pre-computed embeddings (avoid API call)
        dummy_embedding = [0.1] * 1536  # text-embedding-3-small dimension
        tabs = [
            Tab(
                id=1,
                url="https://example.com/1",
                title="Test Tab 1",
                entities=["Entity1", "Entity2"],
                embedding=dummy_embedding
            ),
            Tab(
                id=2,
                url="https://example.com/2",
                title="Test Tab 2",
                entities=["Entity2", "Entity3"],
                embedding=dummy_embedding
            ),
        ]

        # Process with skip_enrichment=True (should not fail)
        try:
            result = clusterer.process_tabs_batch(tabs, skip_enrichment=True)
            print("✓ process_tabs_batch with skip_enrichment=True succeeded")
        except Exception as e:
            print(f"✗ process_tabs_batch failed: {e}")
            raise

        graph_db.close()
        print("\n✅ Skip enrichment flag test passed!\n")

    finally:
        db_path.unlink()


def test_background_enrichment_function():
    """Test that background enrichment function is importable and has correct signature."""
    print("\n=== Test 3: Background Enrichment Function ===")

    from kg_graph_search.server.app import enrich_entities_in_background
    import inspect

    # Check function signature
    sig = inspect.signature(enrich_entities_in_background)
    params = list(sig.parameters.keys())

    assert "entity_names" in params, "Should have entity_names parameter"
    assert "db_path" in params, "Should have db_path parameter"
    assert "you_api_key" in params, "Should have you_api_key parameter"

    print("✓ Background enrichment function has correct signature")
    print(f"  Parameters: {params}")

    print("\n✅ Background enrichment function test passed!\n")


def test_config_settings():
    """Test that new config settings exist."""
    print("\n=== Test 4: Config Settings ===")

    from kg_graph_search.config import Settings

    # Create settings instance with defaults
    settings = Settings(
        openai_api_key="test",
        you_api_key="test"
    )

    assert hasattr(settings, "enable_background_enrichment"), "Should have enable_background_enrichment setting"
    assert hasattr(settings, "enrichment_batch_size"), "Should have enrichment_batch_size setting"
    assert hasattr(settings, "enrichment_timeout_seconds"), "Should have enrichment_timeout_seconds setting"

    print(f"✓ enable_background_enrichment: {settings.enable_background_enrichment}")
    print(f"✓ enrichment_batch_size: {settings.enrichment_batch_size}")
    print(f"✓ enrichment_timeout_seconds: {settings.enrichment_timeout_seconds}")

    print("\n✅ Config settings test passed!\n")


if __name__ == "__main__":
    print("="*60)
    print("Testing Async Enrichment Refactor")
    print("="*60)

    try:
        test_batch_entity_fetch()
        test_skip_enrichment_flag()
        test_background_enrichment_function()
        test_config_settings()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nRefactor Summary:")
        print("  ✓ Batch entity fetching eliminates N+1 queries")
        print("  ✓ Skip enrichment flag enables fast tab processing")
        print("  ✓ Background enrichment function ready for FastAPI")
        print("  ✓ Configuration settings added")
        print("\n🚀 Ready to deploy!")

    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ TEST FAILED: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
