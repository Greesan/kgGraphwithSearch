"""
Neo4j graph database handler for the knowledge graph with temporal support.
"""

from datetime import datetime
from typing import Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    raise ImportError(
        "Neo4j driver not installed. Install with: uv sync --extra neo4j"
    )

from .base import GraphStore
from .models import Entity, TemporalValidityRange, Triplet


class Neo4jGraphStore(GraphStore):
    """Neo4j graph database handler for storing and querying the knowledge graph."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ):
        """
        Initialize the Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., 'bolt://localhost:7687')
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: 'neo4j')
        """
        self.driver: Driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self._initialize_schema()

    def _initialize_schema(self):
        """Create indexes and constraints for the graph."""
        with self.driver.session(database=self.database) as session:
            # Constraint: unique entity name + type combination
            session.run(
                """
                CREATE CONSTRAINT entity_unique IF NOT EXISTS
                FOR (e:Entity)
                REQUIRE (e.name, e.type) IS UNIQUE
                """
            )

            # Constraint: unique tab ID
            session.run(
                """
                CREATE CONSTRAINT tab_unique IF NOT EXISTS
                FOR (t:Tab)
                REQUIRE t.id IS UNIQUE
                """
            )

            # Index on entity name for faster lookups
            session.run(
                """
                CREATE INDEX entity_name_idx IF NOT EXISTS
                FOR (e:Entity) ON (e.name)
                """
            )

            # Index on entity type
            session.run(
                """
                CREATE INDEX entity_type_idx IF NOT EXISTS
                FOR (e:Entity) ON (e.type)
                """
            )

            # Index on tab URL
            session.run(
                """
                CREATE INDEX tab_url_idx IF NOT EXISTS
                FOR (t:Tab) ON (t.url)
                """
            )

            # Index on tab opened_at for temporal queries
            session.run(
                """
                CREATE INDEX tab_opened_at_idx IF NOT EXISTS
                FOR (t:Tab) ON (t.opened_at)
                """
            )

            # Index on tab is_active
            session.run(
                """
                CREATE INDEX tab_is_active_idx IF NOT EXISTS
                FOR (t:Tab) ON (t.is_active)
                """
            )

    def add_entity(self, entity: Entity) -> int:
        """
        Add an entity to the graph.

        Args:
            entity: Entity to add

        Returns:
            ID of the inserted or existing entity
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MERGE (e:Entity {name: $name, type: $type})
                ON CREATE SET
                    e.description = $description,
                    e.created_at = datetime($created_at),
                    e.web_description = $web_description,
                    e.related_concepts = $related_concepts,
                    e.source_url = $source_url,
                    e.is_enriched = $is_enriched,
                    e.enriched_at = $enriched_at
                RETURN id(e) as entity_id
                """,
                name=entity.name,
                type=entity.entity_type,
                description=entity.description,
                created_at=entity.created_at.isoformat(),
                web_description=entity.web_description,
                related_concepts=entity.related_concepts,
                source_url=entity.source_url,
                is_enriched=entity.is_enriched,
                enriched_at=entity.enriched_at.isoformat() if entity.enriched_at else None,
            )
            record = result.single()
            return record["entity_id"]

    def get_entity(self, entity_id: int) -> Optional[Entity]:
        """Get an entity by ID."""
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE id(e) = $entity_id
                RETURN e.name as name,
                       e.type as type,
                       e.description as description,
                       e.created_at as created_at,
                       e.web_description as web_description,
                       e.related_concepts as related_concepts,
                       e.source_url as source_url,
                       e.is_enriched as is_enriched,
                       e.enriched_at as enriched_at,
                       id(e) as id
                """,
                entity_id=entity_id,
            )
            record = result.single()

            if record:
                return Entity(
                    id=record["id"],
                    name=record["name"],
                    entity_type=record["type"],
                    description=record["description"],
                    created_at=datetime.fromisoformat(record["created_at"]),
                    web_description=record["web_description"],
                    related_concepts=record["related_concepts"] or [],
                    source_url=record["source_url"],
                    is_enriched=bool(record["is_enriched"]) if record["is_enriched"] is not None else False,
                    enriched_at=datetime.fromisoformat(record["enriched_at"]) if record["enriched_at"] else None,
                )
            return None

    def find_entity_by_name(
        self, name: str, entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """Find an entity by name and optionally type."""
        with self.driver.session(database=self.database) as session:
            if entity_type:
                result = session.run(
                    """
                    MATCH (e:Entity {name: $name, type: $type})
                    RETURN e.name as name,
                           e.type as type,
                           e.description as description,
                           e.created_at as created_at,
                           e.web_description as web_description,
                           e.related_concepts as related_concepts,
                           e.source_url as source_url,
                           e.is_enriched as is_enriched,
                           e.enriched_at as enriched_at,
                           id(e) as id
                    """,
                    name=name,
                    type=entity_type,
                )
            else:
                result = session.run(
                    """
                    MATCH (e:Entity {name: $name})
                    RETURN e.name as name,
                           e.type as type,
                           e.description as description,
                           e.created_at as created_at,
                           e.web_description as web_description,
                           e.related_concepts as related_concepts,
                           e.source_url as source_url,
                           e.is_enriched as is_enriched,
                           e.enriched_at as enriched_at,
                           id(e) as id
                    LIMIT 1
                    """,
                    name=name,
                )

            record = result.single()
            if record:
                return Entity(
                    id=record["id"],
                    name=record["name"],
                    entity_type=record["type"],
                    description=record["description"],
                    created_at=datetime.fromisoformat(record["created_at"]),
                    web_description=record["web_description"],
                    related_concepts=record["related_concepts"] or [],
                    source_url=record["source_url"],
                    is_enriched=bool(record["is_enriched"]) if record["is_enriched"] is not None else False,
                    enriched_at=datetime.fromisoformat(record["enriched_at"]) if record["enriched_at"] else None,
                )
            return None

    def add_triplet(self, triplet: Triplet) -> int:
        """
        Add a triplet (relationship) to the graph with temporal validity.

        Args:
            triplet: Triplet to add

        Returns:
            ID of the inserted relationship
        """
        with self.driver.session(database=self.database) as session:
            temporal = triplet.temporal_validity

            result = session.run(
                """
                MATCH (subject:Entity), (object:Entity)
                WHERE id(subject) = $subject_id AND id(object) = $object_id
                CREATE (subject)-[r:RELATES {
                    predicate: $predicate,
                    start_time: datetime($start_time),
                    end_time: datetime($end_time),
                    is_current: $is_current,
                    confidence: $confidence,
                    source: $source,
                    created_at: datetime($created_at)
                }]->(object)
                RETURN id(r) as relationship_id
                """,
                subject_id=triplet.subject_id,
                object_id=triplet.object_id,
                predicate=triplet.predicate,
                start_time=temporal.start_time.isoformat() if temporal and temporal.start_time else None,
                end_time=temporal.end_time.isoformat() if temporal and temporal.end_time else None,
                is_current=temporal.is_current if temporal else True,
                confidence=triplet.confidence,
                source=triplet.source,
                created_at=triplet.created_at.isoformat(),
            )
            record = result.single()
            return record["relationship_id"]

    def get_triplets_for_entity(
        self, entity_id: int, as_subject: bool = True
    ) -> list[Triplet]:
        """
        Get all triplets where the entity is either the subject or object.

        Args:
            entity_id: ID of the entity
            as_subject: If True, get triplets where entity is subject, else object

        Returns:
            List of triplets
        """
        with self.driver.session(database=self.database) as session:
            if as_subject:
                query = """
                    MATCH (subject:Entity)-[r:RELATES]->(object:Entity)
                    WHERE id(subject) = $entity_id
                    RETURN id(r) as id,
                           id(subject) as subject_id,
                           subject.name as subject_name,
                           r.predicate as predicate,
                           id(object) as object_id,
                           object.name as object_name,
                           r.start_time as start_time,
                           r.end_time as end_time,
                           r.is_current as is_current,
                           r.confidence as confidence,
                           r.source as source,
                           r.created_at as created_at
                """
            else:
                query = """
                    MATCH (subject:Entity)-[r:RELATES]->(object:Entity)
                    WHERE id(object) = $entity_id
                    RETURN id(r) as id,
                           id(subject) as subject_id,
                           subject.name as subject_name,
                           r.predicate as predicate,
                           id(object) as object_id,
                           object.name as object_name,
                           r.start_time as start_time,
                           r.end_time as end_time,
                           r.is_current as is_current,
                           r.confidence as confidence,
                           r.source as source,
                           r.created_at as created_at
                """

            result = session.run(query, entity_id=entity_id)

            triplets = []
            for record in result:
                temporal = TemporalValidityRange(
                    start_time=datetime.fromisoformat(record["start_time"])
                    if record["start_time"]
                    else None,
                    end_time=datetime.fromisoformat(record["end_time"])
                    if record["end_time"]
                    else None,
                    is_current=record["is_current"],
                )

                triplets.append(
                    Triplet(
                        id=record["id"],
                        subject_id=record["subject_id"],
                        subject_name=record["subject_name"],
                        predicate=record["predicate"],
                        object_id=record["object_id"],
                        object_name=record["object_name"],
                        temporal_validity=temporal,
                        confidence=record["confidence"],
                        source=record["source"],
                        created_at=datetime.fromisoformat(record["created_at"]),
                    )
                )

            return triplets

    def search_entities(self, query: str, limit: int = 10) -> list[Entity]:
        """
        Search for entities by name (fuzzy matching).

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching entities
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query
                RETURN e.name as name,
                       e.type as type,
                       e.description as description,
                       e.created_at as created_at,
                       id(e) as id
                ORDER BY e.name
                LIMIT $limit
                """,
                query=query,
                limit=limit,
            )

            entities = []
            for record in result:
                entities.append(
                    Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["type"],
                        description=record["description"],
                        created_at=datetime.fromisoformat(record["created_at"]),
                    )
                )

            return entities

    def get_temporal_snapshot(
        self, entity_id: int, at_time: datetime
    ) -> list[Triplet]:
        """
        Get all relationships valid at a specific point in time.

        Args:
            entity_id: ID of the entity
            at_time: Point in time to query

        Returns:
            List of triplets valid at the specified time
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (subject:Entity)-[r:RELATES]->(object:Entity)
                WHERE id(subject) = $entity_id
                  AND (r.start_time IS NULL OR datetime(r.start_time) <= datetime($at_time))
                  AND (r.end_time IS NULL OR datetime(r.end_time) >= datetime($at_time))
                RETURN id(r) as id,
                       id(subject) as subject_id,
                       subject.name as subject_name,
                       r.predicate as predicate,
                       id(object) as object_id,
                       object.name as object_name,
                       r.start_time as start_time,
                       r.end_time as end_time,
                       r.is_current as is_current,
                       r.confidence as confidence,
                       r.source as source,
                       r.created_at as created_at
                """,
                entity_id=entity_id,
                at_time=at_time.isoformat(),
            )

            triplets = []
            for record in result:
                temporal = TemporalValidityRange(
                    start_time=datetime.fromisoformat(record["start_time"])
                    if record["start_time"]
                    else None,
                    end_time=datetime.fromisoformat(record["end_time"])
                    if record["end_time"]
                    else None,
                    is_current=record["is_current"],
                )

                triplets.append(
                    Triplet(
                        id=record["id"],
                        subject_id=record["subject_id"],
                        subject_name=record["subject_name"],
                        predicate=record["predicate"],
                        object_id=record["object_id"],
                        object_name=record["object_name"],
                        temporal_validity=temporal,
                        confidence=record["confidence"],
                        source=record["source"],
                        created_at=datetime.fromisoformat(record["created_at"]),
                    )
                )

            return triplets

    def add_tab(
        self,
        tab_id: int,
        url: str,
        title: str,
        favicon_url: Optional[str] = None,
        embedding: Optional[list[float]] = None,
        window_id: Optional[int] = None,
        group_id: Optional[int] = None,
        opened_at: Optional[datetime] = None,
    ) -> int:
        """
        Add or update a tab in the graph.

        Args:
            tab_id: Browser tab ID
            url: Tab URL
            title: Tab title
            favicon_url: URL to favicon
            embedding: Vector embedding (stored as list property)
            window_id: Browser window ID
            group_id: Chrome Tab Group ID
            opened_at: When the tab was opened

        Returns:
            The tab_id
        """
        with self.driver.session(database=self.database) as session:
            opened_timestamp = opened_at.isoformat() if opened_at else datetime.utcnow().isoformat()

            session.run(
                """
                MERGE (t:Tab {id: $tab_id})
                SET t.url = $url,
                    t.title = $title,
                    t.favicon_url = $favicon_url,
                    t.embedding = $embedding,
                    t.window_id = $window_id,
                    t.group_id = $group_id,
                    t.last_accessed = datetime(),
                    t.is_active = true,
                    t.closed_at = null
                ON CREATE SET
                    t.opened_at = datetime($opened_at),
                    t.created_at = datetime()
                """,
                tab_id=tab_id,
                url=url,
                title=title,
                favicon_url=favicon_url,
                embedding=embedding,
                window_id=window_id,
                group_id=group_id,
                opened_at=opened_timestamp,
            )

            return tab_id

    def get_tab(self, tab_id: int) -> Optional[dict]:
        """
        Get a tab by ID.

        Args:
            tab_id: The tab ID

        Returns:
            Dictionary with tab data, or None if not found
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab {id: $tab_id})
                RETURN t.id as id,
                       t.url as url,
                       t.title as title,
                       t.favicon_url as favicon_url,
                       t.embedding as embedding,
                       t.opened_at as opened_at,
                       t.closed_at as closed_at,
                       t.created_at as created_at,
                       t.last_accessed as last_accessed,
                       t.window_id as window_id,
                       t.group_id as group_id,
                       t.is_active as is_active
                """,
                tab_id=tab_id,
            )
            record = result.single()

            if not record:
                return None

            return {
                "id": record["id"],
                "url": record["url"],
                "title": record["title"],
                "favicon_url": record["favicon_url"],
                "embedding": record["embedding"],
                "opened_at": datetime.fromisoformat(record["opened_at"]) if record["opened_at"] else None,
                "closed_at": datetime.fromisoformat(record["closed_at"]) if record["closed_at"] else None,
                "created_at": datetime.fromisoformat(record["created_at"]),
                "last_accessed": datetime.fromisoformat(record["last_accessed"]),
                "window_id": record["window_id"],
                "group_id": record["group_id"],
                "is_active": record["is_active"],
            }

    def link_tab_to_entity(self, tab_id: int, entity_id: int) -> None:
        """
        Create or update a relationship between a tab and an entity.

        Args:
            tab_id: The tab ID
            entity_id: The entity ID
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MATCH (t:Tab {id: $tab_id}), (e:Entity)
                WHERE id(e) = $entity_id
                MERGE (t)-[r:MENTIONS]->(e)
                ON CREATE SET
                    r.first_seen = datetime(),
                    r.last_seen = datetime()
                ON MATCH SET
                    r.last_seen = datetime()
                """,
                tab_id=tab_id,
                entity_id=entity_id,
            )

    def close_tab(self, tab_id: int) -> bool:
        """
        Mark a tab as closed.

        Args:
            tab_id: The tab ID to close

        Returns:
            True if tab was closed, False if not found
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab {id: $tab_id, is_active: true})
                SET t.closed_at = datetime(),
                    t.is_active = false
                RETURN t.id as id
                """,
                tab_id=tab_id,
            )
            return result.single() is not None

    def get_entities_for_tab(self, tab_id: int) -> list[Entity]:
        """
        Get all entities associated with a tab.

        Args:
            tab_id: The tab ID

        Returns:
            List of entities
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab {id: $tab_id})-[:MENTIONS]->(e:Entity)
                RETURN e.name as name,
                       e.type as type,
                       e.description as description,
                       e.created_at as created_at,
                       id(e) as id
                """,
                tab_id=tab_id,
            )

            entities = []
            for record in result:
                entities.append(
                    Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["type"],
                        description=record["description"],
                        created_at=datetime.fromisoformat(record["created_at"]),
                    )
                )

            return entities

    def get_tabs_for_entity(self, entity_id: int) -> list[dict]:
        """
        Get all tabs that mention a specific entity.

        Args:
            entity_id: The entity ID

        Returns:
            List of tab dictionaries
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab)-[:MENTIONS]->(e:Entity)
                WHERE id(e) = $entity_id
                RETURN t.id as id,
                       t.url as url,
                       t.title as title,
                       t.favicon_url as favicon_url,
                       t.embedding as embedding,
                       t.opened_at as opened_at,
                       t.closed_at as closed_at,
                       t.created_at as created_at,
                       t.last_accessed as last_accessed,
                       t.window_id as window_id,
                       t.group_id as group_id,
                       t.is_active as is_active
                """,
                entity_id=entity_id,
            )

            tabs = []
            for record in result:
                tabs.append({
                    "id": record["id"],
                    "url": record["url"],
                    "title": record["title"],
                    "favicon_url": record["favicon_url"],
                    "embedding": record["embedding"],
                    "opened_at": datetime.fromisoformat(record["opened_at"]) if record["opened_at"] else None,
                    "closed_at": datetime.fromisoformat(record["closed_at"]) if record["closed_at"] else None,
                    "created_at": datetime.fromisoformat(record["created_at"]),
                    "last_accessed": datetime.fromisoformat(record["last_accessed"]),
                    "window_id": record["window_id"],
                    "group_id": record["group_id"],
                    "is_active": record["is_active"],
                })

            return tabs

    def find_tabs_with_shared_entities(
        self, tab_id: int, min_shared: int = 1, limit: int = 50
    ) -> list[tuple[dict, int]]:
        """
        Find tabs that share entities with the given tab.

        Args:
            tab_id: The tab ID to find related tabs for
            min_shared: Minimum number of shared entities
            limit: Maximum number of results

        Returns:
            List of tuples: (tab_dict, shared_entity_count)
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t1:Tab {id: $tab_id})-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(t2:Tab)
                WHERE t1 <> t2
                WITH t2, COUNT(DISTINCT e) as shared_count
                WHERE shared_count >= $min_shared
                RETURN t2.id as id,
                       t2.url as url,
                       t2.title as title,
                       t2.favicon_url as favicon_url,
                       t2.embedding as embedding,
                       t2.opened_at as opened_at,
                       t2.closed_at as closed_at,
                       t2.created_at as created_at,
                       t2.last_accessed as last_accessed,
                       t2.window_id as window_id,
                       t2.group_id as group_id,
                       t2.is_active as is_active,
                       shared_count
                ORDER BY shared_count DESC
                LIMIT $limit
                """,
                tab_id=tab_id,
                min_shared=min_shared,
                limit=limit,
            )

            results = []
            for record in result:
                tab_dict = {
                    "id": record["id"],
                    "url": record["url"],
                    "title": record["title"],
                    "favicon_url": record["favicon_url"],
                    "embedding": record["embedding"],
                    "opened_at": datetime.fromisoformat(record["opened_at"]) if record["opened_at"] else None,
                    "closed_at": datetime.fromisoformat(record["closed_at"]) if record["closed_at"] else None,
                    "created_at": datetime.fromisoformat(record["created_at"]),
                    "last_accessed": datetime.fromisoformat(record["last_accessed"]),
                    "window_id": record["window_id"],
                    "group_id": record["group_id"],
                    "is_active": record["is_active"],
                }
                results.append((tab_dict, record["shared_count"]))

            return results

    def update_tab_relationship(
        self,
        tab_id_1: int,
        tab_id_2: int,
        shared_entities: list[str],
        relationship_strength: float,
    ) -> None:
        """
        Create or update a relationship between two tabs.

        Args:
            tab_id_1: First tab ID
            tab_id_2: Second tab ID
            shared_entities: List of entity names shared between tabs
            relationship_strength: Strength score (0-1)
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MATCH (t1:Tab {id: $tab_id_1}), (t2:Tab {id: $tab_id_2})
                MERGE (t1)-[r:RELATED_TO]-(t2)
                SET r.shared_entities = $shared_entities,
                    r.shared_entity_count = size($shared_entities),
                    r.relationship_strength = $relationship_strength,
                    r.last_updated = datetime()
                ON CREATE SET
                    r.first_connected = datetime()
                """,
                tab_id_1=tab_id_1,
                tab_id_2=tab_id_2,
                shared_entities=shared_entities,
                relationship_strength=relationship_strength,
            )

    def get_active_tabs(self) -> list[dict]:
        """
        Get all currently active (open) tabs.

        Returns:
            List of active tab dictionaries
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab {is_active: true})
                RETURN t.id as id,
                       t.url as url,
                       t.title as title,
                       t.favicon_url as favicon_url,
                       t.embedding as embedding,
                       t.opened_at as opened_at,
                       t.closed_at as closed_at,
                       t.created_at as created_at,
                       t.last_accessed as last_accessed,
                       t.window_id as window_id,
                       t.group_id as group_id,
                       t.is_active as is_active
                ORDER BY t.last_accessed DESC
                """
            )

            tabs = []
            for record in result:
                tabs.append({
                    "id": record["id"],
                    "url": record["url"],
                    "title": record["title"],
                    "favicon_url": record["favicon_url"],
                    "embedding": record["embedding"],
                    "opened_at": datetime.fromisoformat(record["opened_at"]) if record["opened_at"] else None,
                    "closed_at": datetime.fromisoformat(record["closed_at"]) if record["closed_at"] else None,
                    "created_at": datetime.fromisoformat(record["created_at"]),
                    "last_accessed": datetime.fromisoformat(record["last_accessed"]),
                    "window_id": record["window_id"],
                    "group_id": record["group_id"],
                    "is_active": record["is_active"],
                })

            return tabs

    def get_tabs_in_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> list[dict]:
        """
        Get tabs that were active during a specific time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of tab dictionaries
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tab)
                WHERE datetime(t.opened_at) <= datetime($end_time)
                  AND (t.closed_at IS NULL OR datetime(t.closed_at) >= datetime($start_time))
                RETURN t.id as id,
                       t.url as url,
                       t.title as title,
                       t.favicon_url as favicon_url,
                       t.embedding as embedding,
                       t.opened_at as opened_at,
                       t.closed_at as closed_at,
                       t.created_at as created_at,
                       t.last_accessed as last_accessed,
                       t.window_id as window_id,
                       t.group_id as group_id,
                       t.is_active as is_active
                ORDER BY t.opened_at DESC
                """,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )

            tabs = []
            for record in result:
                tabs.append({
                    "id": record["id"],
                    "url": record["url"],
                    "title": record["title"],
                    "favicon_url": record["favicon_url"],
                    "embedding": record["embedding"],
                    "opened_at": datetime.fromisoformat(record["opened_at"]) if record["opened_at"] else None,
                    "closed_at": datetime.fromisoformat(record["closed_at"]) if record["closed_at"] else None,
                    "created_at": datetime.fromisoformat(record["created_at"]),
                    "last_accessed": datetime.fromisoformat(record["last_accessed"]),
                    "window_id": record["window_id"],
                    "group_id": record["group_id"],
                    "is_active": record["is_active"],
                })

            return tabs

    def update_entity_enrichment(
        self,
        entity_id: int,
        web_description: str,
        entity_type: str,
        related_concepts: list[str],
        source_url: str,
    ) -> bool:
        """
        Update an entity with enrichment data from You.com.

        Args:
            entity_id: Entity ID to update
            web_description: Description from web search
            entity_type: Classified entity type
            related_concepts: List of related concept names
            source_url: Source URL for the enrichment

        Returns:
            True if updated successfully
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE id(e) = $entity_id
                SET e.web_description = $web_description,
                    e.type = $entity_type,
                    e.related_concepts = $related_concepts,
                    e.source_url = $source_url,
                    e.is_enriched = true,
                    e.enriched_at = datetime($enriched_at)
                RETURN count(e) as updated_count
                """,
                entity_id=entity_id,
                web_description=web_description,
                entity_type=entity_type,
                related_concepts=related_concepts,
                source_url=source_url,
                enriched_at=datetime.now().isoformat(),
            )
            record = result.single()
            return record["updated_count"] > 0

    def needs_enrichment(self, entity_id: int, cache_ttl_days: int = 7) -> bool:
        """
        Check if an entity needs enrichment or re-enrichment.

        Args:
            entity_id: Entity ID to check
            cache_ttl_days: Cache TTL in days (default: 7)

        Returns:
            True if entity needs enrichment
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE id(e) = $entity_id
                RETURN e.is_enriched as is_enriched,
                       e.enriched_at as enriched_at
                """,
                entity_id=entity_id,
            )
            record = result.single()

            if not record:
                return False

            # Not enriched yet
            if not record["is_enriched"]:
                return True

            # Check if cache has expired
            if record["enriched_at"]:
                enriched_at = datetime.fromisoformat(record["enriched_at"])
                from datetime import timedelta

                cache_expiry = enriched_at + timedelta(days=cache_ttl_days)
                if datetime.now() > cache_expiry:
                    return True

            return False

    def get_entities_needing_enrichment(
        self, limit: int = 10, cache_ttl_days: int = 7
    ) -> list[Entity]:
        """
        Get entities that need enrichment.

        Args:
            limit: Maximum number of entities to return
            cache_ttl_days: Cache TTL in days

        Returns:
            List of entities needing enrichment
        """
        with self.driver.session(database=self.database) as session:
            # Calculate cache expiry timestamp
            from datetime import timedelta

            cache_expiry = datetime.now() - timedelta(days=cache_ttl_days)

            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.is_enriched IS NULL
                   OR e.is_enriched = false
                   OR e.enriched_at IS NULL
                   OR datetime(e.enriched_at) < datetime($cache_expiry)
                RETURN e.name as name,
                       e.type as type,
                       e.description as description,
                       e.created_at as created_at,
                       e.web_description as web_description,
                       e.related_concepts as related_concepts,
                       e.source_url as source_url,
                       e.is_enriched as is_enriched,
                       e.enriched_at as enriched_at,
                       id(e) as id
                LIMIT $limit
                """,
                cache_expiry=cache_expiry.isoformat(),
                limit=limit,
            )

            entities = []
            for record in result:
                entities.append(
                    Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["type"],
                        description=record["description"],
                        created_at=datetime.fromisoformat(record["created_at"]),
                        web_description=record["web_description"],
                        related_concepts=record["related_concepts"] or [],
                        source_url=record["source_url"],
                        is_enriched=bool(record["is_enriched"])
                        if record["is_enriched"] is not None
                        else False,
                        enriched_at=datetime.fromisoformat(record["enriched_at"])
                        if record["enriched_at"]
                        else None,
                    )
                )

            return entities

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()
