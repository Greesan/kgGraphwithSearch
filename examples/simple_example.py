"""
Simple example demonstrating the knowledge graph with You.com search integration.
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kg_graph_search.config import get_settings
from kg_graph_search.graph.database import KnowledgeGraphDB
from kg_graph_search.graph.models import Entity, Triplet, TemporalValidityRange
from kg_graph_search.search.you_client import YouAPIClient
from datetime import datetime


def main():
    """Run a simple example."""
    print("=== Knowledge Graph with You.com Search Example ===\n")

    # Load settings
    settings = get_settings()
    print("✓ Configuration loaded\n")

    # 1. You.com Search Example
    print("1. Searching You.com for 'knowledge graphs'...")
    with YouAPIClient(api_key=settings.you_api_key) as you_client:
        results = you_client.search("knowledge graphs", num_results=3)

        print(f"\nFound {results.hits_count} results:\n")
        for i, result in enumerate(results.results, 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   {result.snippet[:100]}...\n")

    # 2. Knowledge Graph Example
    print("\n2. Building a knowledge graph...")
    with KnowledgeGraphDB(settings.db_path) as db:
        # Create entities
        alice = Entity(
            name="Alice",
            entity_type="Person",
            description="Software engineer specializing in knowledge graphs",
        )
        bob = Entity(
            name="Bob", entity_type="Person", description="Data scientist"
        )
        company = Entity(
            name="TechCorp",
            entity_type="Organization",
            description="Technology company",
        )

        # Add to database
        alice_id = db.add_entity(alice)
        bob_id = db.add_entity(bob)
        company_id = db.add_entity(company)

        print(f"✓ Created entities: Alice, Bob, TechCorp\n")

        # Create relationships
        triplet1 = Triplet(
            subject_id=alice_id,
            subject_name="Alice",
            predicate="works_at",
            object_id=company_id,
            object_name="TechCorp",
            temporal_validity=TemporalValidityRange(
                start_time=datetime(2023, 1, 1), is_current=True
            ),
            confidence=1.0,
            source="example",
        )

        triplet2 = Triplet(
            subject_id=alice_id,
            subject_name="Alice",
            predicate="collaborates_with",
            object_id=bob_id,
            object_name="Bob",
            confidence=0.9,
            source="example",
        )

        db.add_triplet(triplet1)
        db.add_triplet(triplet2)

        print("✓ Created relationships\n")

        # Query the graph
        print("3. Querying Alice's relationships:")
        relationships = db.get_triplets_for_entity(alice_id, as_subject=True)

        for rel in relationships:
            print(f"   {rel.subject_name} --[{rel.predicate}]--> {rel.object_name}")
            if rel.temporal_validity and rel.temporal_validity.start_time:
                print(f"      Since: {rel.temporal_validity.start_time.date()}")
            print(f"      Confidence: {rel.confidence}")

    print("\n✓ Example completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure you have:")
        print("  1. Created a .env file with your API keys")
        print("  2. Run 'uv sync' to install dependencies")
        sys.exit(1)
