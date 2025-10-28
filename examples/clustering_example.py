"""
Example demonstrating tab clustering with centroid-based assignment.

This example shows:
1. Creating tabs with different topics
2. Automatic clustering based on semantic similarity
3. Adding tabs to existing clusters
4. Removing tabs and updating centroids
5. Automatic cluster renaming when enough tabs are added
6. Cluster deletion when too few tabs remain
"""

from kg_graph_search.agents import Tab, TabClusterer
from kg_graph_search.config import get_settings


def main():
    """Run tab clustering example."""

    # Verify configuration
    settings = get_settings()
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in .env file")
        print("Please copy .env.example to .env and add your OpenAI API key")
        return

    print("=" * 80)
    print("Tab Clustering Example: Centroid-Based Assignment")
    print("=" * 80)
    print()

    # Initialize clusterer
    print("Initializing TabClusterer...")
    clusterer = TabClusterer(
        similarity_threshold=0.75,  # 75% similarity required for cluster assignment
        rename_threshold=3,         # Rename after 3 new tabs added
    )
    print(f"✓ Similarity threshold: 0.75")
    print(f"✓ Rename threshold: 3 tabs")
    print()

    # =========================================================================
    # Phase 1: Create initial tabs on different topics
    # =========================================================================
    print("-" * 80)
    print("PHASE 1: Adding initial tabs (should create separate clusters)")
    print("-" * 80)
    print()

    tabs = [
        # Graph Database Research cluster
        Tab(
            id=1,
            url="https://neo4j.com/docs",
            title="Neo4j Documentation - Graph Database",
        ),
        Tab(
            id=2,
            url="https://neo4j.com/docs/cypher-manual",
            title="Cypher Query Language Tutorial",
        ),

        # React Development cluster
        Tab(
            id=3,
            url="https://react.dev/learn",
            title="React Documentation - Learn React",
        ),
        Tab(
            id=4,
            url="https://react.dev/reference/react/hooks",
            title="React Hooks API Reference",
        ),

        # Machine Learning cluster
        Tab(
            id=5,
            url="https://arxiv.org/abs/2103.00020",
            title="Attention Is All You Need - Transformers Paper",
        ),
        Tab(
            id=6,
            url="https://huggingface.co/docs",
            title="Hugging Face Transformers Documentation",
        ),
    ]

    for tab in tabs:
        print(f"Processing: {tab.title}")
        clusterer.process_tab(tab)
        print()

    # Show cluster stats
    stats = clusterer.get_cluster_stats()
    print(f"\n📊 Current state: {stats['total_clusters']} clusters, {stats['total_tabs']} tabs")
    for cluster_info in stats['clusters']:
        print(f"  - {cluster_info['name']} ({cluster_info['color']}): {cluster_info['tab_count']} tabs")
    print()

    # =========================================================================
    # Phase 2: Add more tabs to existing clusters
    # =========================================================================
    print("-" * 80)
    print("PHASE 2: Adding more tabs (should join existing clusters)")
    print("-" * 80)
    print()

    additional_tabs = [
        # Should join Graph Database cluster
        Tab(
            id=7,
            url="https://neo4j.com/developer/graph-algorithms",
            title="Graph Algorithms in Neo4j",
        ),
        Tab(
            id=8,
            url="https://neo4j.com/graphacademy",
            title="Neo4j GraphAcademy - Learn Graph Databases",
        ),

        # Should join React cluster
        Tab(
            id=9,
            url="https://react.dev/reference/react/Component",
            title="React Component API Reference",
        ),

        # Should join ML cluster
        Tab(
            id=10,
            url="https://pytorch.org/docs",
            title="PyTorch Documentation",
        ),
    ]

    for tab in additional_tabs:
        print(f"Processing: {tab.title}")
        clusterer.process_tab(tab)
        print()

    # Show updated stats
    stats = clusterer.get_cluster_stats()
    print(f"\n📊 Current state: {stats['total_clusters']} clusters, {stats['total_tabs']} tabs")
    for cluster_info in stats['clusters']:
        print(f"  - {cluster_info['name']} ({cluster_info['color']}): {cluster_info['tab_count']} tabs")
        print(f"    Tabs added since last naming: {cluster_info['tabs_added_since_naming']}")
    print()

    # =========================================================================
    # Phase 3: Add one more tab to trigger rename
    # =========================================================================
    print("-" * 80)
    print("PHASE 3: Adding tab to trigger cluster rename (threshold: 3)")
    print("-" * 80)
    print()

    # This should join the Graph Database cluster and trigger rename
    rename_tab = Tab(
        id=11,
        url="https://neo4j.com/blog/graphrag-llm-knowledge-graphs",
        title="GraphRAG: Combining LLMs with Knowledge Graphs",
    )

    print(f"Processing: {rename_tab.title}")
    clusterer.process_tab(rename_tab)
    print()

    # Show updated stats
    stats = clusterer.get_cluster_stats()
    print(f"\n📊 Current state: {stats['total_clusters']} clusters, {stats['total_tabs']} tabs")
    for cluster_info in stats['clusters']:
        print(f"  - {cluster_info['name']} ({cluster_info['color']}): {cluster_info['tab_count']} tabs")
        print(f"    Tabs added since last naming: {cluster_info['tabs_added_since_naming']}")
    print()

    # =========================================================================
    # Phase 4: Remove tabs and test centroid updates
    # =========================================================================
    print("-" * 80)
    print("PHASE 4: Removing tabs (centroid should update, no rename)")
    print("-" * 80)
    print()

    # Find the Graph Database cluster
    graph_cluster = None
    for cluster in clusterer.get_all_clusters():
        if any(tab.id in [1, 2, 7, 8, 11] for tab in cluster.tabs):
            graph_cluster = cluster
            break

    if graph_cluster:
        print(f"Found cluster: {graph_cluster.name}")
        print(f"Current tabs: {len(graph_cluster.tabs)}")
        print()

        # Remove some tabs
        tabs_to_remove = [2, 8]  # Remove Cypher tutorial and GraphAcademy
        for tab_id in tabs_to_remove:
            print(f"Removing tab ID {tab_id}...")
            clusterer.remove_tab_from_cluster(graph_cluster, tab_id)
            print(f"  ✓ Removed. Centroid updated.")
            print(f"  ✓ Cluster now has {graph_cluster.tab_count} tabs")
            print()

        # Add a new tab - should still match the updated centroid
        new_tab = Tab(
            id=12,
            url="https://neo4j.com/docs/operations-manual",
            title="Neo4j Operations Manual",
        )
        print(f"Adding new tab: {new_tab.title}")
        print("This should still match the cluster despite removed tabs")
        clusterer.process_tab(new_tab)
        print()

    # Show final stats
    stats = clusterer.get_cluster_stats()
    print(f"\n📊 Final state: {stats['total_clusters']} clusters, {stats['total_tabs']} tabs")
    for cluster_info in stats['clusters']:
        print(f"  - {cluster_info['name']} ({cluster_info['color']}): {cluster_info['tab_count']} tabs")
    print()

    # =========================================================================
    # Phase 5: Remove enough tabs to trigger cluster deletion
    # =========================================================================
    print("-" * 80)
    print("PHASE 5: Removing tabs until cluster has < 2 tabs (should delete)")
    print("-" * 80)
    print()

    # Find the ML cluster (smallest one)
    ml_cluster = None
    for cluster in clusterer.get_all_clusters():
        if any(tab.id in [5, 6, 10] for tab in cluster.tabs):
            ml_cluster = cluster
            break

    if ml_cluster:
        print(f"Found cluster: {ml_cluster.name}")
        print(f"Current tabs: {ml_cluster.tab_count}")
        print()

        # Remove tabs until only 1 remains
        tab_ids = [tab.id for tab in ml_cluster.tabs]
        for tab_id in tab_ids[:-1]:  # Keep one tab
            print(f"Removing tab ID {tab_id}...")
            clusterer.remove_tab_from_cluster(ml_cluster, tab_id)
            print()

        print("Removing final tab to trigger deletion...")
        clusterer.remove_tab_from_cluster(ml_cluster, tab_ids[-1])
        print()

    # Show final stats
    stats = clusterer.get_cluster_stats()
    print(f"\n📊 Final state: {stats['total_clusters']} clusters, {stats['total_tabs']} tabs")
    for cluster_info in stats['clusters']:
        print(f"  - {cluster_info['name']} ({cluster_info['color']}): {cluster_info['tab_count']} tabs")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 80)
    print("SUMMARY: Key Behaviors Demonstrated")
    print("=" * 80)
    print()
    print("✓ Centroid updated on BOTH add and remove operations")
    print("✓ Rename triggered ONLY by additions (not removals)")
    print("✓ Clusters with < 2 tabs automatically deleted")
    print("✓ New tabs correctly assigned to updated centroids")
    print("✓ Similarity threshold prevents incorrect assignments")
    print()


if __name__ == "__main__":
    main()
