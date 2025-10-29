"""
Test the graph visualization endpoint with sample data.

This script:
1. Creates sample tabs with entities
2. Processes them through the clusterer
3. Tests the /api/graph/visualization endpoint
4. Prints the response in a readable format

Usage:
    uv run python examples/test_graph_endpoint.py
"""

import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, UTC
from kg_graph_search.agents.models import Tab
from kg_graph_search.agents.tab_clusterer import TabClusterer
from kg_graph_search.graph.database import KnowledgeGraphDB


def create_sample_tabs():
    """Create sample tabs for testing."""
    return [
        # Graph Database cluster
        Tab(
            id=1,
            url="https://neo4j.com/docs",
            title="Neo4j Documentation",
            entities=["Neo4j", "Cypher", "Graph Database"],
            created_at=datetime.now(UTC),
        ),
        Tab(
            id=2,
            url="https://neo4j.com/cypher-manual",
            title="Cypher Query Language Manual",
            entities=["Cypher", "Neo4j", "Query Language"],
            created_at=datetime.now(UTC),
        ),
        Tab(
            id=3,
            url="https://graphdatabase.org/intro",
            title="Introduction to Graph Databases",
            entities=["Graph Database", "Neo4j", "Data Modeling"],
            created_at=datetime.now(UTC),
        ),
        # React Development cluster
        Tab(
            id=4,
            url="https://react.dev",
            title="React Documentation",
            entities=["React", "JavaScript", "Frontend"],
            created_at=datetime.now(UTC),
        ),
        Tab(
            id=5,
            url="https://react.dev/learn/hooks",
            title="React Hooks Tutorial",
            entities=["React", "Hooks", "JavaScript"],
            created_at=datetime.now(UTC),
        ),
        Tab(
            id=6,
            url="https://nextjs.org",
            title="Next.js Framework",
            entities=["Next.js", "React", "SSR"],
            created_at=datetime.now(UTC),
        ),
        # Machine Learning cluster
        Tab(
            id=7,
            url="https://pytorch.org",
            title="PyTorch Documentation",
            entities=["PyTorch", "Machine Learning", "Deep Learning"],
            created_at=datetime.now(UTC),
        ),
        Tab(
            id=8,
            url="https://huggingface.co/transformers",
            title="Transformers Library",
            entities=["Transformers", "Machine Learning", "NLP"],
            created_at=datetime.now(UTC),
        ),
    ]


def test_graph_endpoint():
    """Test the graph visualization endpoint."""
    print("=" * 80)
    print("Testing Graph Visualization Endpoint")
    print("=" * 80)
    print()

    # Initialize with knowledge graph
    db_path = Path("./data/test_kg.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing test DB
    if db_path.exists():
        db_path.unlink()

    graph_db = KnowledgeGraphDB(db_path)

    print("✓ Initialized knowledge graph database")
    print()

    # Initialize clusterer with graph DB
    # Lower threshold for better grouping (0.50 works well with hybrid scoring)
    clusterer = TabClusterer(
        similarity_threshold=0.50,
        rename_threshold=3,
        graph_db=graph_db,
        entity_weight=0.6,  # 60% entities, 40% embeddings
    )

    print("✓ Initialized TabClusterer with hybrid scoring")
    print(f"  - Similarity threshold: 0.50")
    print(f"  - Entity weight: 0.6 (60% entities, 40% embeddings)")
    print()

    # Create and process sample tabs
    tabs = create_sample_tabs()

    print(f"Processing {len(tabs)} sample tabs...")
    print()

    # Process tabs in batch (this will generate embeddings)
    print("Generating embeddings for all tabs...")
    result = clusterer.process_tabs_batch(tabs)
    print("✓ Embeddings generated")

    print(f"✓ Processed {result.total_tabs_processed} tabs")
    print(f"  - Created {len(result.clusters)} clusters")
    print()

    # Print cluster summary
    print("Cluster Summary:")
    print("-" * 80)
    for cluster in result.clusters:
        if cluster.tab_count >= 2:
            print(f"\n{cluster.name} ({cluster.color.value}, {cluster.tab_count} tabs)")
            print(f"  Shared entities: {', '.join(cluster.shared_entities[:5])}")
            for tab in cluster.tabs:
                print(f"  - {tab.title}")
    print()

    # Simulate the endpoint logic
    print("=" * 80)
    print("Simulating /api/graph/visualization endpoint")
    print("=" * 80)
    print()

    clusters = clusterer.get_all_clusters()
    clusters = [c for c in clusters if c.tab_count >= 2]

    nodes = []
    edges = []

    # Create cluster nodes and tab nodes
    for cluster in clusters:
        # Add cluster node
        cluster_node = {
            "data": {
                "id": f"cluster_{cluster.id}",
                "type": "cluster",
                "label": cluster.name,
                "color": cluster.color.value,
                "tab_count": cluster.tab_count,
                "shared_entities": cluster.shared_entities[:5],
            }
        }
        nodes.append(cluster_node)

        # Add tab nodes
        for tab in cluster.tabs:
            tab_node = {
                "data": {
                    "id": f"tab_{tab.id}",
                    "type": "tab",
                    "label": tab.title[:50],
                    "parent": f"cluster_{cluster.id}",
                    "url": tab.url,
                    "important": False,
                    "entities": tab.entities,
                    "opened_at": tab.created_at.isoformat() if tab.created_at else None,
                }
            }
            nodes.append(tab_node)

            # Add edge
            edge = {
                "data": {
                    "id": f"edge_tab{tab.id}_cluster{cluster.id}",
                    "source": f"tab_{tab.id}",
                    "target": f"cluster_{cluster.id}",
                    "type": "contains",
                }
            }
            edges.append(edge)

    response = {
        "nodes": nodes,
        "edges": edges,
        "timestamp": datetime.now(UTC).isoformat(),
        "metadata": {
            "cluster_count": len(clusters),
            "tab_count": sum(c.tab_count for c in clusters),
            "time_range_hours": None,
            "include_singletons": False,
            "min_cluster_size": 2,
        }
    }

    # Print response in readable format
    print("Response JSON:")
    print("-" * 80)
    print(json.dumps(response, indent=2))
    print()

    # Print summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✓ Total nodes: {len(nodes)}")
    print(f"  - Cluster nodes: {len([n for n in nodes if n['data']['type'] == 'cluster'])}")
    print(f"  - Tab nodes: {len([n for n in nodes if n['data']['type'] == 'tab'])}")
    print(f"✓ Total edges: {len(edges)}")
    print(f"✓ Ready for Cytoscape.js rendering!")
    print()

    # Test query from graph database
    print("=" * 80)
    print("Testing Knowledge Graph Queries")
    print("=" * 80)
    print()

    # Get all active tabs
    active_tabs = graph_db.get_active_tabs()
    print(f"✓ Active tabs in graph: {len(active_tabs)}")

    # Get tab relationships
    if active_tabs:
        first_tab = active_tabs[0]
        relationships = graph_db.get_tab_relationships(first_tab["id"])
        print(f"✓ Tab '{first_tab['title']}' has {len(relationships)} relationships")
        for rel in relationships[:3]:
            print(f"  - {rel['related_tab_title']} (strength: {rel['relationship_strength']:.2f})")
    print()

    # Cleanup
    graph_db.close()

    print("✓ Test complete!")
    print()


if __name__ == "__main__":
    try:
        test_graph_endpoint()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
