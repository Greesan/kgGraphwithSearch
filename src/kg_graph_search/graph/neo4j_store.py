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
                    e.created_at = datetime($created_at)
                RETURN id(e) as entity_id
                """,
                name=entity.name,
                type=entity.entity_type,
                description=entity.description,
                created_at=entity.created_at.isoformat(),
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

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()
