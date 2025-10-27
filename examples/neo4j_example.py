"""
Example demonstrating Neo4j knowledge graph with temporal support.

Prerequisites:
1. Install Neo4j: uv sync --extra neo4j
2. Run Neo4j locally (Docker recommended):
   docker run -p 7687:7687 -p 7474:7474 \
     -e NEO4J_AUTH=neo4j/your_password \
     neo4j:latest
3. Add NEO4J_PASSWORD to your .env file
"""

from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kg_graph_search.config import get_settings
from kg_graph_search.graph.neo4j_store import Neo4jGraphStore
from kg_graph_search.graph.models import Entity, Triplet, TemporalValidityRange


def main():
    """Run Neo4j example with temporal queries."""
    print("=== Neo4j Knowledge Graph with Temporal Support ===\n")

    # Load settings
    settings = get_settings()

    if not settings.neo4j_password:
        print("❌ Error: NEO4J_PASSWORD not set in .env file")
        print("\nSet it with:")
        print("  NEO4J_PASSWORD=your_password")
        sys.exit(1)

    print("✓ Configuration loaded")
    print(f"  Connecting to: {settings.neo4j_uri}\n")

    # Initialize Neo4j
    try:
        with Neo4jGraphStore(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        ) as db:
            print("✓ Connected to Neo4j\n")

            # Create entities
            print("1. Creating entities...")
            alice = Entity(
                name="Alice",
                entity_type="Person",
                description="Software engineer",
            )
            bob = Entity(
                name="Bob",
                entity_type="Person",
                description="Product manager",
            )
            techcorp = Entity(
                name="TechCorp",
                entity_type="Organization",
                description="Technology company",
            )
            startup = Entity(
                name="StartupCo",
                entity_type="Organization",
                description="Startup company",
            )

            alice_id = db.add_entity(alice)
            bob_id = db.add_entity(bob)
            techcorp_id = db.add_entity(techcorp)
            startup_id = db.add_entity(startup)

            print(f"   Created: Alice (ID: {alice_id})")
            print(f"   Created: Bob (ID: {bob_id})")
            print(f"   Created: TechCorp (ID: {techcorp_id})")
            print(f"   Created: StartupCo (ID: {startup_id})\n")

            # Create temporal relationships
            print("2. Creating temporal relationships...")

            # Alice worked at StartupCo from 2020-2022
            past_job = Triplet(
                subject_id=alice_id,
                subject_name="Alice",
                predicate="works_at",
                object_id=startup_id,
                object_name="StartupCo",
                temporal_validity=TemporalValidityRange(
                    start_time=datetime(2020, 1, 1),
                    end_time=datetime(2022, 12, 31),
                    is_current=False,
                ),
                confidence=1.0,
                source="example",
            )

            # Alice currently works at TechCorp (since 2023)
            current_job = Triplet(
                subject_id=alice_id,
                subject_name="Alice",
                predicate="works_at",
                object_id=techcorp_id,
                object_name="TechCorp",
                temporal_validity=TemporalValidityRange(
                    start_time=datetime(2023, 1, 1),
                    is_current=True,
                ),
                confidence=1.0,
                source="example",
            )

            # Bob works at TechCorp
            bob_job = Triplet(
                subject_id=bob_id,
                subject_name="Bob",
                predicate="works_at",
                object_id=techcorp_id,
                object_name="TechCorp",
                temporal_validity=TemporalValidityRange(
                    start_time=datetime(2022, 6, 1),
                    is_current=True,
                ),
                confidence=1.0,
                source="example",
            )

            # Alice collaborates with Bob
            collaboration = Triplet(
                subject_id=alice_id,
                subject_name="Alice",
                predicate="collaborates_with",
                object_id=bob_id,
                object_name="Bob",
                confidence=0.9,
                source="example",
            )

            db.add_triplet(past_job)
            db.add_triplet(current_job)
            db.add_triplet(bob_job)
            db.add_triplet(collaboration)

            print("   ✓ Added temporal relationships\n")

            # Query current relationships
            print("3. Querying Alice's current relationships:")
            current_rels = db.get_triplets_for_entity(alice_id, as_subject=True)

            for rel in current_rels:
                print(f"   {rel.subject_name} --[{rel.predicate}]--> {rel.object_name}")
                if rel.temporal_validity:
                    if rel.temporal_validity.start_time:
                        print(f"      Since: {rel.temporal_validity.start_time.date()}")
                    if rel.temporal_validity.end_time:
                        print(f"      Until: {rel.temporal_validity.end_time.date()}")
                    print(f"      Current: {rel.temporal_validity.is_current}")
                print(f"      Confidence: {rel.confidence}\n")

            # Temporal snapshot query (what was true in 2021?)
            print("4. Time travel: What was Alice's job in 2021?")
            past_snapshot = db.get_temporal_snapshot(
                alice_id, datetime(2021, 6, 1)
            )

            for rel in past_snapshot:
                if rel.predicate == "works_at":
                    print(f"   In 2021, {rel.subject_name} worked at {rel.object_name}")
                    print(f"      Valid from: {rel.temporal_validity.start_time.date()}")
                    if rel.temporal_validity.end_time:
                        print(f"      Until: {rel.temporal_validity.end_time.date()}\n")

            # Search entities
            print("5. Searching for entities containing 'Tech':")
            search_results = db.search_entities("Tech")
            for entity in search_results:
                print(f"   {entity.name} ({entity.entity_type}): {entity.description}")

            print("\n✓ Example completed successfully!")
            print("\n💡 View your graph in Neo4j Browser:")
            print("   http://localhost:7474")
            print("\n   Run this Cypher query:")
            print("   MATCH (n)-[r]->(m) RETURN n, r, m")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Neo4j is running (try: docker run -p 7687:7687 -p 7474:7474 neo4j)")
        print("  2. NEO4J_PASSWORD is set in your .env file")
        print("  3. You've installed neo4j extras: uv sync --extra neo4j")
        sys.exit(1)


if __name__ == "__main__":
    main()
