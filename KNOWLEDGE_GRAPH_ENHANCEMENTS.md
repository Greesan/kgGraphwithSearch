# Knowledge Graph Enhancement Roadmap

This document outlines future enhancements for the TabGraph knowledge graph system to add richer entity and tab relationships using external knowledge bases.

## Current State

### What Works Now
- **Tab → Entity relationships**: Tabs are linked to extracted entities (topics, concepts, tools)
- **Entity extraction**: LLM extracts 3-8 key entities from tab titles and URLs
- **Entity enrichment**: Each entity gets type, description, and related concepts from You.com
- **Tab clustering**: Tabs grouped by shared entities
- **Tab → Tab relationships**: Computed via shared entity overlap (Jaccard similarity)

### Current Limitations
- **Generic entity relationships**: Enrichment returns "related concepts" but no semantic predicates
- **No structured entity-entity triplets**: Relationships lack meaningful types (e.g., "React uses JavaScript" vs "React related to JavaScript")
- **Limited tab-tab enrichment**: Only uses shared entity names, not deeper semantic connections

## Proposed Enhancements

### Phase 1: Entity-Entity Relationships via Knowledge Bases

Add **authoritative, structured relationships** between entities using Wikidata and DBpedia.

#### Approach

1. **Entity Mapping**
   - Map extracted entity names to knowledge base identifiers
   - Example: "React" → Wikidata Q19399674 or DBpedia "React_(JavaScript_library)"
   - Handle disambiguation (e.g., "Java" language vs "Java" island)

2. **Relationship Query**
   - Use SPARQL to query relationships between entity pairs
   - Example query (Wikidata):
     ```sparql
     SELECT ?predicate ?predicateLabel WHERE {
       wd:Q19399674 ?predicate wd:Q2407 .  # React to JavaScript
       SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
     }
     ```

3. **Triplet Storage**
   - Store results in `triplets` table with:
     - Subject: Entity 1 (e.g., "React")
     - Predicate: Relationship type (e.g., "written in", "uses", "extends")
     - Object: Entity 2 (e.g., "JavaScript")
     - Source: "wikidata" or "dbpedia"
     - Confidence: Based on knowledge base authority

4. **Visualization**
   - Display entity-entity edges in graph view
   - Edge labels show relationship type
   - Hover shows source and confidence

#### Implementation

```python
# New service: src/kg_graph_search/enrichment/knowledge_base_client.py

class KnowledgeBaseClient:
    """Query Wikidata and DBpedia for entity relationships."""

    def find_entity_id(self, entity_name: str, entity_type: str) -> Optional[str]:
        """
        Map entity name to Wikidata/DBpedia identifier.

        Args:
            entity_name: Human-readable name (e.g., "React")
            entity_type: Entity type for disambiguation (e.g., "tool")

        Returns:
            Wikidata QID (e.g., "Q19399674") or DBpedia URI
        """
        # Use Wikidata search API or DBpedia Lookup
        pass

    def get_relationships(
        self,
        entity1_id: str,
        entity2_id: str,
        source: str = "wikidata"
    ) -> list[dict]:
        """
        Query relationships between two entities via SPARQL.

        Returns:
            [
                {"predicate": "written in", "confidence": 1.0},
                {"predicate": "uses", "confidence": 0.9}
            ]
        """
        if source == "wikidata":
            return self._query_wikidata(entity1_id, entity2_id)
        else:
            return self._query_dbpedia(entity1_id, entity2_id)

    def _query_wikidata(self, entity1_id: str, entity2_id: str) -> list[dict]:
        """Execute SPARQL query against Wikidata endpoint."""
        endpoint = "https://query.wikidata.org/sparql"
        query = f"""
        SELECT ?predicate ?predicateLabel WHERE {{
          wd:{entity1_id} ?predicate wd:{entity2_id} .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        # Execute and parse results
        pass
```

#### Integration Points

1. **Background enrichment** (app.py:106-217)
   - After entity enrichment, query knowledge bases for pairwise relationships
   - Store discovered relationships as triplets

2. **Graph visualization** (app.py:706-738)
   - Already queries `get_all_triplets()` (now implemented)
   - Will automatically display entity-entity edges once triplets exist

#### Benefits
- ✅ Authoritative data from curated knowledge graphs
- ✅ Rich semantic relationships (not generic "related to")
- ✅ No LLM hallucination risk
- ✅ Enhances graph visualization with meaningful connections

#### Challenges
- ⚠️ Entity disambiguation (ambiguous names)
- ⚠️ Coverage gaps (newer technologies, niche topics)
- ⚠️ Rate limits on SPARQL endpoints
- ⚠️ API latency (adds to enrichment time)

#### Mitigation Strategies
- Cache knowledge base queries (TTL: 30 days for stable facts)
- Batch entity lookups where possible
- Use Wikidata first (better tech coverage), fallback to DBpedia
- Async processing to avoid blocking tab ingestion

---

### Phase 2: Enhanced Tab-Tab Relationships

Enrich tab-tab relationships beyond simple entity overlap using multiple signals.

#### Approach 1: URL Structure Analysis

**Data Sources:**
- Same domain detection
- URL path similarity
- Citation links (for Wikipedia, academic papers)

**Example:**
```python
Tab A: https://react.dev/learn/hooks
Tab B: https://react.dev/reference/react/useState

Enrichment:
  - same_domain: True
  - url_similarity: 0.7 (path overlap)
  - domain_category: "documentation"

Enhanced relationship:
  (Tab A, "documentation_sibling", Tab B)
```

**Implementation:**
```python
def analyze_url_relationship(url1: str, url2: str) -> dict:
    """Compute URL-based relationship signals."""
    from urllib.parse import urlparse

    parsed1 = urlparse(url1)
    parsed2 = urlparse(url2)

    return {
        "same_domain": parsed1.netloc == parsed2.netloc,
        "path_similarity": compute_path_similarity(parsed1.path, parsed2.path),
        "domain_type": classify_domain(parsed1.netloc)  # docs, blog, academic, etc.
    }
```

#### Approach 2: Semantic Embedding Similarity

**Already have:** Tab embeddings stored in database (OpenAI text-embedding-3-small)

**Enhancement:**
```python
def compute_semantic_similarity(tab1_embedding, tab2_embedding) -> float:
    """Compute cosine similarity between tab embeddings."""
    from numpy import dot
    from numpy.linalg import norm

    return dot(tab1_embedding, tab2_embedding) / (norm(tab1_embedding) * norm(tab2_embedding))

# Usage in tab relationship computation
if similarity > 0.85:  # Very high semantic similarity
    relationship_type = "semantically_equivalent"
elif similarity > 0.70:
    relationship_type = "highly_related"
```

**Benefits:**
- Detects conceptual similarity beyond keyword matching
- Finds paraphrases and related topics
- Already computed (no additional API calls)

#### Approach 3: Topic Hierarchy Mapping

**Data Sources:**
- Wikipedia categories
- Wikidata topic hierarchies
- Library of Congress subject headings

**Example:**
```python
Tab A: "React Hooks Tutorial"
  → Wikidata topics: [Q19399674 (React), Q2407 (JavaScript), Q80993 (Software)]

Tab B: "Vue Composition API"
  → Wikidata topics: [Q19841877 (Vue.js), Q2407 (JavaScript), Q80993 (Software)]

Enrichment:
  - shared_topics: [Q2407 (JavaScript), Q80993 (Software)]
  - topic_distance: 2 (both under "JavaScript frameworks")

Enhanced relationship:
  (Tab A, "shares_topic_hierarchy", Tab B, shared_topics=["JavaScript", "Software"])
```

**Implementation:**
```python
def get_topic_hierarchy(entity_id: str) -> list[str]:
    """Query Wikidata for topic hierarchy (instance of, subclass of)."""
    query = f"""
    SELECT ?topic ?topicLabel WHERE {{
      wd:{entity_id} wdt:P31*/wdt:P279* ?topic .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 10
    """
    # Returns topics like: [JavaScript framework, Software, Programming language]
```

#### Approach 4: Temporal Co-occurrence Patterns

**Idea:** Detect browsing workflow patterns and enrich with knowledge base context

**Data:**
- Tab open/close timestamps
- Tab sequence patterns
- Common navigation paths

**Example:**
```python
Pattern detected:
  User often: React docs → TypeScript docs → Testing Library docs (within 1 hour)

Query knowledge bases:
  - What is the relationship between React, TypeScript, Testing Library?

Discovered:
  - TypeScript is commonly used with React
  - Testing Library is designed for React testing

Enrichment:
  (Tab React, "workflow_leads_to", Tab TypeScript, confidence=0.8)
  (Tab TypeScript, "workflow_leads_to", Tab Testing Library, confidence=0.7)
```

---

## Implementation Priority

### Immediate (Phase 1A)
1. ✅ **Fix `get_all_triplets()` method** - COMPLETED
2. **Basic Wikidata integration** - Query relationships for top entity pairs

### Short Term (Phase 1B)
3. **Entity disambiguation** - Map entity names to Wikidata IDs
4. **Triplet storage pipeline** - Store discovered relationships in database
5. **Graph visualization enhancement** - Display entity-entity edges with predicates

### Medium Term (Phase 2A)
6. **URL structure analysis** - Enhance tab-tab relationships
7. **Embedding similarity** - Use existing embeddings for semantic relatedness

### Long Term (Phase 2B)
8. **Topic hierarchy mapping** - Wikidata category enrichment
9. **Temporal pattern detection** - Workflow-based relationships
10. **DBpedia integration** - Fallback for entities not in Wikidata

---

## Example SPARQL Queries

### Wikidata: Find Relationships Between Entities

```sparql
# Find all properties connecting React (Q19399674) to JavaScript (Q2407)
SELECT ?property ?propertyLabel WHERE {
  wd:Q19399674 ?property wd:Q2407 .
  ?prop wikibase:directClaim ?property .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

### Wikidata: Search Entity by Name

```sparql
# Find entity ID for "React" (JavaScript library)
SELECT ?item ?itemLabel ?itemDescription WHERE {
  ?item rdfs:label "React"@en .
  ?item wdt:P31/wdt:P279* wd:Q7397 .  # Instance of software
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 5
```

### DBpedia: Find Relationships

```sparql
# Find relationships from DBpedia resource
SELECT ?property ?value WHERE {
  dbr:React_(JavaScript_library) ?property ?value .
  FILTER(isURI(?value))
}
LIMIT 20
```

---

## API Rate Limits & Best Practices

### Wikidata Query Service
- **No official rate limit** but requests should be throttled
- **Best practice:** Max 1 query per second
- **Timeout:** 60 seconds per query
- **User-Agent required:** Include contact info in headers

### DBpedia SPARQL Endpoint
- **Rate limit:** ~100 requests/minute
- **Pagination:** Use LIMIT and OFFSET for large results
- **Best practice:** Cache results aggressively

### Caching Strategy
```python
# Cache entity mappings for 30 days (stable)
entity_id_cache = {
    "React": ("Q19399674", expires=datetime.now() + timedelta(days=30))
}

# Cache relationships for 14 days
relationship_cache = {
    ("Q19399674", "Q2407"): [
        {"predicate": "written in", "confidence": 1.0}
    ]
}
```

---

## References

- [Wikidata SPARQL Tutorial](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial)
- [Wikidata Query Service](https://query.wikidata.org/)
- [DBpedia SPARQL Endpoint](http://dbpedia.org/sparql)
- [DBpedia Ontology-Driven API](https://github.com/dbpedia/ontology-driven-api)
- [Wikidata REST API](https://www.wikidata.org/wiki/Wikidata:REST_API)

---

## Decision Points for Future Implementation

Before implementing these enhancements, consider:

1. **Knowledge Base Choice**
   - Wikidata: Better for technology, broad coverage, structured data
   - DBpedia: Better for Wikipedia-referenced topics, simpler queries
   - Both: Use Wikidata as primary, DBpedia as fallback

2. **Enrichment Timing**
   - Real-time: Enrich during tab ingestion (adds latency)
   - Background: Queue enrichment tasks (better UX, eventual consistency)
   - Batch: Periodic enrichment jobs (efficient, but delayed)

3. **Storage Strategy**
   - Store all discovered triplets (comprehensive but storage-heavy)
   - Store only high-confidence triplets (selective, may miss connections)
   - Store with TTL (refresh periodically for updated facts)

4. **Visualization Trade-offs**
   - Show all entity-entity edges (rich but potentially cluttered)
   - Show only high-confidence edges (cleaner but may hide connections)
   - User-configurable filters (best of both worlds, more complex)
