"""
Test entity enrichment with You.com integration.

This script tests the complete Phase 2 implementation:
1. Entity extraction from tabs
2. Entity enrichment using You.com Search API
3. Storage of enriched data in knowledge graph
"""

import os
from pathlib import Path
from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB


def test_entity_enrichment():
    """Test entity enrichment end-to-end."""

    print("🧪 Testing Entity Enrichment with You.com")
    print("=" * 60)

    # Check for You.com API key
    you_api_key = os.getenv("YOU_API_KEY")
    if not you_api_key:
        print("❌ YOU_API_KEY not found in environment")
        print("   Set it with: export YOU_API_KEY='your-key-here'")
        return

    print(f"✅ You.com API key found: {you_api_key[:8]}...")

    # Initialize knowledge graph
    db_path = Path("./data/test_enrichment.db")
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️  Removed old test database")

    graph_db = KnowledgeGraphDB(db_path)
    print(f"✅ Initialized knowledge graph: {db_path}")

    # Initialize clusterer with enrichment
    clusterer = TabClusterer(
        similarity_threshold=0.50,
        rename_threshold=3,
        graph_db=graph_db,
        entity_weight=0.5,
    )
    print(f"✅ Initialized TabClusterer")
    print(f"   - Entity enricher available: {clusterer.entity_enricher is not None}")

    # Create test tabs with interesting entities
    test_tabs = [
        Tab(
            id=1,
            url="https://react.dev/learn",
            title="Learn React - A JavaScript library for building user interfaces",
            favicon_url="https://react.dev/favicon.ico",
        ),
        Tab(
            id=2,
            url="https://neo4j.com/docs",
            title="Neo4j Graph Database Documentation",
            favicon_url="https://neo4j.com/favicon.ico",
        ),
        Tab(
            id=3,
            url="https://pytorch.org/tutorials",
            title="PyTorch Tutorials - Deep Learning Framework",
            favicon_url="https://pytorch.org/favicon.ico",
        ),
    ]

    print(f"\n📋 Processing {len(test_tabs)} test tabs:")
    for tab in test_tabs:
        print(f"   - {tab.title[:50]}...")

    # Process tabs (this will extract and enrich entities)
    print(f"\n🔄 Processing tabs (extracting & enriching entities)...")
    clusters = []
    for tab in test_tabs:
        cluster = clusterer.process_tab(tab)
        clusters.append(cluster)
        print(f"   ✓ Processed tab {tab.id}: {len(tab.entities)} entities extracted")
        print(f"     Entities: {', '.join(tab.entities)}")

    # Wait a moment for enrichment to complete
    print(f"\n⏳ Waiting for entity enrichment to complete...")
    import time
    time.sleep(3)  # Give enrichment some time

    # Check enriched entities
    print(f"\n📊 Checking entity enrichment status:")
    print("-" * 60)

    all_entities = set()
    for tab in test_tabs:
        all_entities.update(tab.entities)

    enriched_count = 0
    failed_count = 0

    for entity_name in sorted(all_entities):
        entity = graph_db.find_entity_by_name(entity_name)
        if entity:
            if entity.is_enriched:
                enriched_count += 1
                print(f"\n✅ {entity.name}")
                print(f"   Type: {entity.entity_type}")
                print(f"   Description: {entity.web_description[:100] if entity.web_description else 'N/A'}...")
                print(f"   Related: {', '.join(entity.related_concepts[:3])}")
                print(f"   Source: {entity.source_url}")
            else:
                failed_count += 1
                print(f"\n⚠️  {entity.name} - Not enriched")
        else:
            failed_count += 1
            print(f"\n❌ {entity_name} - Not found in database")

    # Summary
    print(f"\n" + "=" * 60)
    print(f"📈 Enrichment Summary:")
    print(f"   Total entities: {len(all_entities)}")
    print(f"   Enriched: {enriched_count}")
    print(f"   Failed/Pending: {failed_count}")
    print(f"   Success rate: {enriched_count / len(all_entities) * 100:.1f}%")

    # Test entity queries
    print(f"\n🔍 Testing enriched entity queries:")
    entities_needing_enrichment = graph_db.get_entities_needing_enrichment(limit=5)
    print(f"   Entities needing enrichment: {len(entities_needing_enrichment)}")

    # Cleanup
    graph_db.close()
    print(f"\n✅ Test complete!")


if __name__ == "__main__":
    test_entity_enrichment()
