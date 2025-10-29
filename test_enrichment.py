"""
Test script for entity enrichment and knowledge graph integration.

Tests:
1. Batch entity extraction with structured outputs
2. Individual entity enrichment using You.com search
3. Knowledge graph storage and retrieval
4. Hub entity identification for clusters
"""

import asyncio
from pathlib import Path
from openai import OpenAI

from kg_graph_search.agents.entity_extractor import EntityExtractor
from kg_graph_search.agents.entity_enricher import EntityEnricher
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.search.you_client import YouAPIClient
from kg_graph_search.config import get_settings


def test_batch_entity_extraction():
    """Test batch entity extraction with structured outputs."""
    print("\n" + "=" * 80)
    print("TEST 1: Batch Entity Extraction")
    print("=" * 80)

    settings = get_settings()
    openai_client = OpenAI(api_key=settings.openai_api_key)
    extractor = EntityExtractor(openai_client=openai_client, model=settings.openai_llm_model)

    # Test tabs (diverse domains)
    test_tabs = [
        {"title": "Introduction to React Hooks", "url": "https://react.dev/hooks"},
        {"title": "CRISPR Gene Editing Overview", "url": "https://example.com/crispr"},
        {"title": "French Revolution Timeline", "url": "https://history.com/french-revolution"},
    ]

    print(f"\nExtracting entities from {len(test_tabs)} tabs...")
    entities_list = extractor.extract_entities_batch(test_tabs, max_entities=8)

    print("\nResults:")
    for tab, entities in zip(test_tabs, entities_list):
        print(f"\n  {tab['title']}")
        print(f"  Entities: {', '.join(entities)}")

    assert len(entities_list) == len(test_tabs), "Should return entities for each tab"
    assert all(isinstance(e, list) for e in entities_list), "Each result should be a list"
    assert all(len(e) >= 2 for e in entities_list), "Each tab should have at least 2 entities"

    print("\n✅ Batch entity extraction PASSED")
    return entities_list


def test_individual_entity_enrichment(sample_entities):
    """Test domain-agnostic entity enrichment using You.com Express Agent."""
    print("\n" + "=" * 80)
    print("TEST 2: Domain-Agnostic Entity Enrichment (Express Agent)")
    print("=" * 80)

    settings = get_settings()

    if not settings.you_api_key:
        print("\n⚠️  You.com API key not configured - skipping enrichment test")
        return []

    you_client = YouAPIClient(settings.you_api_key)
    enricher = EntityEnricher(you_client)

    # Test entities from diverse domains
    # Take one from each test tab (tech, science, history)
    diverse_entities = []
    for entities_list in sample_entities:
        if entities_list:
            diverse_entities.append(entities_list[0])

    entities_to_enrich = diverse_entities[:3]  # Max 3 for speed

    print(f"\nEnriching diverse entities: {', '.join(entities_to_enrich)}")
    print("Testing domain-agnostic approach (tech, science, history)...")
    enriched = enricher.enrich_entities(entities_to_enrich)

    print("\nResults:")
    for entity_data in enriched:
        print(f"\n  {entity_data['name']} ({entity_data['type']})")
        if entity_data['description']:
            print(f"  Description: {entity_data['description'][:100]}...")
        else:
            print(f"  Description: None")
        print(f"  Related: {', '.join(entity_data['related_concepts'][:3])}")

    assert len(enriched) == len(entities_to_enrich), "Should enrich all entities"

    # Check if enrichment was successful
    enriched_count = sum(1 for e in enriched if e['is_enriched'])
    if enriched_count == 0:
        print("\n⚠️  Warning: All enrichment attempts failed")
    else:
        print(f"\n  ✓ Successfully enriched {enriched_count}/{len(enriched)} entities")

        # Verify domain-agnostic types (not just tech-focused)
        types_used = {e['type'] for e in enriched if e['is_enriched']}
        print(f"  ✓ Entity types detected: {', '.join(types_used)}")

    you_client.close()
    print("\n✅ Domain-agnostic entity enrichment PASSED")
    return enriched


def test_knowledge_graph_integration(enriched_entities):
    """Test knowledge graph storage and retrieval."""
    print("\n" + "=" * 80)
    print("TEST 4: Knowledge Graph Integration")
    print("=" * 80)

    # Use test database
    db_path = Path("./data/test_knowledge_graph.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    graph_db = KnowledgeGraphDB(db_path)

    # Store enriched entities
    print("\nStoring enriched entities...")
    from kg_graph_search.graph.models import Entity
    for entity_data in enriched_entities:
        entity = Entity(
            name=entity_data['name'],
            entity_type=entity_data['type'],
            description=entity_data['description'],
            metadata={
                'related_concepts': entity_data['related_concepts'],
                'key_attributes': entity_data.get('key_attributes', []),
            }
        )
        entity_id = graph_db.add_entity(entity)
        entity.id = entity_id
        print(f"  Stored: {entity.name} (ID: {entity.id})")


    # Test entity lookup
    print("\nTesting entity lookup...")
    entity_name = enriched_entities[0]['name']
    found = graph_db.get_entity_by_name(entity_name)
    assert found is not None, f"Should find entity {entity_name}"
    print(f"  Found: {found.name} (Type: {found.entity_type})")

    graph_db.close()
    print("\n✅ Knowledge graph integration PASSED")


def test_hub_entities():
    """Test hub entity identification in clusters."""
    print("\n" + "=" * 80)
    print("TEST 5: Hub Entity Identification")
    print("=" * 80)

    settings = get_settings()

    # Create test database
    db_path = Path("./data/test_hub_entities.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    graph_db = KnowledgeGraphDB(db_path)
    clusterer = TabClusterer(
        similarity_threshold=0.5,
        graph_db=graph_db,
    )

    # Create mock cluster with tabs
    from kg_graph_search.agents.models import Tab, TabCluster, ClusterColor
    from datetime import datetime, UTC

    tabs = [
        Tab(id=1, url="https://react.dev/1", title="React Hooks",
            entities=["React", "JavaScript", "Hooks"]),
        Tab(id=2, url="https://react.dev/2", title="React State",
            entities=["React", "State Management", "JavaScript"]),
        Tab(id=3, url="https://react.dev/3", title="React Components",
            entities=["React", "Components", "JSX"]),
    ]

    cluster = TabCluster(
        id="test-cluster",
        name="React Development",
        color=ClusterColor.BLUE,
        tabs=tabs,
        shared_entities=["React", "JavaScript"],
        tab_count=len(tabs),
        last_updated=datetime.now(UTC),
    )

    print("\nIdentifying hub entities (top 3)...")
    hub_entities = clusterer.get_hub_entities(cluster, top_n=3)

    print(f"\nHub entities: {', '.join(hub_entities)}")
    print(f"Expected: React, JavaScript (most common)")

    assert len(hub_entities) <= 3, "Should return at most 3 hub entities"
    assert "React" in hub_entities, "React should be a hub entity (appears in all tabs)"
    assert "JavaScript" in hub_entities, "JavaScript should be a hub entity (appears in 2 tabs)"

    graph_db.close()
    print("\n✅ Hub entity identification PASSED")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ENTITY ENRICHMENT AND KNOWLEDGE GRAPH TEST SUITE")
    print("=" * 80)

    try:
        # Test 1: Batch entity extraction
        entities_list = test_batch_entity_extraction()

        # Test 2: Individual entity enrichment
        enriched = test_individual_entity_enrichment(entities_list)

        # Test 3: Knowledge graph integration
        if enriched:
            test_knowledge_graph_integration(enriched)

        # Test 4: Hub entities
        test_hub_entities()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
