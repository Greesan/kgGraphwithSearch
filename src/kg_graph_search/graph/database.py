"""
SQLite database handler for the knowledge graph.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import GraphStore
from .models import Entity, TemporalValidityRange, Triplet


class KnowledgeGraphDB(GraphStore):
    """SQLite database handler for storing and querying the knowledge graph."""

    def __init__(self, db_path: Path):
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self):
        """Create the database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, entity_type)
            )
        """)

        # Triplets table (relationships)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triplets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                predicate TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                is_current INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES entities(id),
                FOREIGN KEY (object_id) REFERENCES entities(id)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_name
            ON entities(name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_type
            ON entities(entity_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_triplets_subject
            ON triplets(subject_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_triplets_object
            ON triplets(object_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_triplets_predicate
            ON triplets(predicate)
        """)

        self.conn.commit()

    def add_entity(self, entity: Entity) -> int:
        """
        Add an entity to the database.

        Args:
            entity: Entity to add

        Returns:
            ID of the inserted or existing entity
        """
        cursor = self.conn.cursor()

        # Try to insert, or get existing ID if already exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO entities (name, entity_type, description, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (entity.name, entity.entity_type, entity.description, entity.created_at),
        )

        if cursor.lastrowid:
            self.conn.commit()
            return cursor.lastrowid

        # If no insert happened, get the existing ID
        cursor.execute(
            """
            SELECT id FROM entities
            WHERE name = ? AND entity_type = ?
        """,
            (entity.name, entity.entity_type),
        )
        row = cursor.fetchone()
        return row["id"] if row else 0

    def get_entity(self, entity_id: int) -> Optional[Entity]:
        """Get an entity by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()

        if row:
            return Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def find_entity_by_name(self, name: str, entity_type: Optional[str] = None) -> Optional[Entity]:
        """Find an entity by name and optionally type."""
        cursor = self.conn.cursor()

        if entity_type:
            cursor.execute(
                "SELECT * FROM entities WHERE name = ? AND entity_type = ?",
                (name, entity_type),
            )
        else:
            cursor.execute("SELECT * FROM entities WHERE name = ?", (name,))

        row = cursor.fetchone()
        if row:
            return Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def add_triplet(self, triplet: Triplet) -> int:
        """
        Add a triplet (relationship) to the database.

        Args:
            triplet: Triplet to add

        Returns:
            ID of the inserted triplet
        """
        cursor = self.conn.cursor()

        temporal = triplet.temporal_validity
        cursor.execute(
            """
            INSERT INTO triplets
            (subject_id, predicate, object_id, start_time, end_time,
             is_current, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                triplet.subject_id,
                triplet.predicate,
                triplet.object_id,
                temporal.start_time if temporal else None,
                temporal.end_time if temporal else None,
                temporal.is_current if temporal else True,
                triplet.confidence,
                triplet.source,
                triplet.created_at,
            ),
        )

        self.conn.commit()
        return cursor.lastrowid

    def get_triplets_for_entity(self, entity_id: int, as_subject: bool = True) -> list[Triplet]:
        """
        Get all triplets where the entity is either the subject or object.

        Args:
            entity_id: ID of the entity
            as_subject: If True, get triplets where entity is subject, else where it's object

        Returns:
            List of triplets
        """
        cursor = self.conn.cursor()

        if as_subject:
            query = """
                SELECT t.*,
                       e1.name as subject_name,
                       e2.name as object_name
                FROM triplets t
                JOIN entities e1 ON t.subject_id = e1.id
                JOIN entities e2 ON t.object_id = e2.id
                WHERE t.subject_id = ?
            """
        else:
            query = """
                SELECT t.*,
                       e1.name as subject_name,
                       e2.name as object_name
                FROM triplets t
                JOIN entities e1 ON t.subject_id = e1.id
                JOIN entities e2 ON t.object_id = e2.id
                WHERE t.object_id = ?
            """

        cursor.execute(query, (entity_id,))
        rows = cursor.fetchall()

        triplets = []
        for row in rows:
            temporal = TemporalValidityRange(
                start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
                end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                is_current=bool(row["is_current"]),
            )

            triplets.append(
                Triplet(
                    id=row["id"],
                    subject_id=row["subject_id"],
                    subject_name=row["subject_name"],
                    predicate=row["predicate"],
                    object_id=row["object_id"],
                    object_name=row["object_name"],
                    temporal_validity=temporal,
                    confidence=row["confidence"],
                    source=row["source"],
                    created_at=datetime.fromisoformat(row["created_at"]),
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
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM entities
            WHERE name LIKE ?
            ORDER BY name
            LIMIT ?
        """,
            (f"%{query}%", limit),
        )

        entities = []
        for row in cursor.fetchall():
            entities.append(
                Entity(
                    id=row["id"],
                    name=row["name"],
                    entity_type=row["entity_type"],
                    description=row["description"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )

        return entities

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
