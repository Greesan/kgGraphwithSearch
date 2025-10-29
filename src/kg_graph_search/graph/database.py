"""
SQLite database handler for the knowledge graph.
"""

import sqlite3
import struct
import json
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
                web_description TEXT,
                related_concepts TEXT,
                source_url TEXT,
                is_enriched INTEGER DEFAULT 0,
                enriched_at TIMESTAMP,
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

        # Tabs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tabs (
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                favicon_url TEXT,
                embedding BLOB,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                window_id INTEGER,
                group_id INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Tab-Entity relationship table (temporal tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tab_entities (
                tab_id INTEGER NOT NULL,
                entity_id INTEGER NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tab_id, entity_id),
                FOREIGN KEY (tab_id) REFERENCES tabs(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_id) REFERENCES entities(id)
            )
        """)

        # Tab-Tab relationships (materialized connections)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tab_relationships (
                tab_id_1 INTEGER NOT NULL,
                tab_id_2 INTEGER NOT NULL,
                shared_entity_count INTEGER NOT NULL DEFAULT 0,
                shared_entities TEXT,
                relationship_strength REAL NOT NULL DEFAULT 0.0,
                first_connected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tab_id_1, tab_id_2),
                FOREIGN KEY (tab_id_1) REFERENCES tabs(id) ON DELETE CASCADE,
                FOREIGN KEY (tab_id_2) REFERENCES tabs(id) ON DELETE CASCADE,
                CHECK (tab_id_1 < tab_id_2)
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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tabs_url
            ON tabs(url)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tab_entities_tab
            ON tab_entities(tab_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tab_entities_entity
            ON tab_entities(entity_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tabs_opened_at
            ON tabs(opened_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tabs_is_active
            ON tabs(is_active)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tab_relationships_tab1
            ON tab_relationships(tab_id_1)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tab_relationships_tab2
            ON tab_relationships(tab_id_2)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tab_relationships_strength
            ON tab_relationships(relationship_strength)
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

        # Convert related_concepts list to JSON string
        related_concepts_json = json.dumps(entity.related_concepts) if entity.related_concepts else None

        # Try to insert, or get existing ID if already exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO entities (
                name, entity_type, description, created_at,
                web_description, related_concepts, source_url,
                is_enriched, enriched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entity.name,
                entity.entity_type,
                entity.description,
                entity.created_at,
                entity.web_description,
                related_concepts_json,
                entity.source_url,
                1 if entity.is_enriched else 0,
                entity.enriched_at,
            ),
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
            # Parse related_concepts JSON
            related_concepts = []
            if row["related_concepts"]:
                try:
                    related_concepts = json.loads(row["related_concepts"])
                except json.JSONDecodeError:
                    related_concepts = []

            return Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
                web_description=row["web_description"],
                related_concepts=related_concepts,
                source_url=row["source_url"],
                is_enriched=bool(row["is_enriched"]),
                enriched_at=datetime.fromisoformat(row["enriched_at"]) if row["enriched_at"] else None,
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
            # Parse related_concepts JSON
            related_concepts = []
            if row["related_concepts"]:
                try:
                    related_concepts = json.loads(row["related_concepts"])
                except json.JSONDecodeError:
                    related_concepts = []

            return Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
                web_description=row["web_description"],
                related_concepts=related_concepts,
                source_url=row["source_url"],
                is_enriched=bool(row["is_enriched"]),
                enriched_at=datetime.fromisoformat(row["enriched_at"]) if row["enriched_at"] else None,
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
        Add or update a tab in the database.

        Args:
            tab_id: Browser tab ID
            url: Tab URL
            title: Tab title
            favicon_url: URL to favicon
            embedding: Vector embedding (1536-dim list)
            window_id: Browser window ID
            group_id: Chrome Tab Group ID
            opened_at: When the tab was opened (defaults to now)

        Returns:
            The tab_id
        """
        cursor = self.conn.cursor()

        # Convert embedding to binary if provided
        embedding_blob = None
        if embedding:
            embedding_blob = struct.pack(f'{len(embedding)}f', *embedding)

        # Check if tab already exists
        existing = self.get_tab(tab_id)

        if existing:
            # Update existing tab (preserve opened_at)
            cursor.execute(
                """
                UPDATE tabs
                SET url = ?, title = ?, favicon_url = ?, embedding = ?,
                    window_id = ?, group_id = ?, last_accessed = CURRENT_TIMESTAMP,
                    is_active = 1, closed_at = NULL
                WHERE id = ?
            """,
                (url, title, favicon_url, embedding_blob, window_id, group_id, tab_id),
            )
        else:
            # Insert new tab
            opened_timestamp = opened_at.isoformat() if opened_at else None
            cursor.execute(
                """
                INSERT INTO tabs
                (id, url, title, favicon_url, embedding, window_id, group_id,
                 opened_at, last_accessed, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        COALESCE(?, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, 1)
            """,
                (tab_id, url, title, favicon_url, embedding_blob, window_id, group_id, opened_timestamp),
            )

        self.conn.commit()
        return tab_id

    def get_tab(self, tab_id: int) -> Optional[dict]:
        """
        Get a tab by ID.

        Args:
            tab_id: The tab ID

        Returns:
            Dictionary with tab data, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tabs WHERE id = ?", (tab_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Convert embedding blob back to list
        embedding = None
        if row["embedding"]:
            embedding_blob = row["embedding"]
            num_floats = len(embedding_blob) // 4
            embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

        return {
            "id": row["id"],
            "url": row["url"],
            "title": row["title"],
            "favicon_url": row["favicon_url"],
            "embedding": embedding,
            "opened_at": datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
            "closed_at": datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
            "created_at": datetime.fromisoformat(row["created_at"]),
            "last_accessed": datetime.fromisoformat(row["last_accessed"]),
            "window_id": row["window_id"],
            "group_id": row["group_id"],
            "is_active": bool(row["is_active"]),
        }

    def link_tab_to_entity(self, tab_id: int, entity_id: int) -> None:
        """
        Create or update a relationship between a tab and an entity.

        Updates last_seen if relationship already exists.

        Args:
            tab_id: The tab ID
            entity_id: The entity ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO tab_entities (tab_id, entity_id, first_seen, last_seen)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(tab_id, entity_id) DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP
        """,
            (tab_id, entity_id),
        )
        self.conn.commit()

    def close_tab(self, tab_id: int) -> bool:
        """
        Mark a tab as closed (sets closed_at and is_active=False).

        Args:
            tab_id: The tab ID to close

        Returns:
            True if tab was closed, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE tabs
            SET closed_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ? AND is_active = 1
        """,
            (tab_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_entities_for_tab(self, tab_id: int) -> list[Entity]:
        """
        Get all entities associated with a tab.

        Args:
            tab_id: The tab ID

        Returns:
            List of entities
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT e.* FROM entities e
            JOIN tab_entities te ON e.id = te.entity_id
            WHERE te.tab_id = ?
        """,
            (tab_id,),
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

    def get_tabs_for_entity(self, entity_id: int) -> list[dict]:
        """
        Get all tabs that mention a specific entity.

        Args:
            entity_id: The entity ID

        Returns:
            List of tab dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT t.* FROM tabs t
            JOIN tab_entities te ON t.id = te.tab_id
            WHERE te.entity_id = ?
        """,
            (entity_id,),
        )

        tabs = []
        for row in cursor.fetchall():
            # Convert embedding if present
            embedding = None
            if row["embedding"]:
                embedding_blob = row["embedding"]
                num_floats = len(embedding_blob) // 4
                embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

            tabs.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "favicon_url": row["favicon_url"],
                "embedding": embedding,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "last_accessed": datetime.fromisoformat(row["last_accessed"]),
                "window_id": row["window_id"],
                "group_id": row["group_id"],
            })

        return tabs

    def find_tabs_with_shared_entities(
        self, tab_id: int, min_shared: int = 1, limit: int = 50
    ) -> list[tuple[dict, int]]:
        """
        Find tabs that share entities with the given tab.

        Args:
            tab_id: The tab ID to find related tabs for
            min_shared: Minimum number of shared entities (default: 1)
            limit: Maximum number of results (default: 50)

        Returns:
            List of tuples: (tab_dict, shared_entity_count)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT t2.*, COUNT(DISTINCT te2.entity_id) as shared_count
            FROM tabs t1
            JOIN tab_entities te1 ON t1.id = te1.tab_id
            JOIN tab_entities te2 ON te1.entity_id = te2.entity_id
            JOIN tabs t2 ON te2.tab_id = t2.id
            WHERE t1.id = ? AND t2.id != ?
            GROUP BY t2.id
            HAVING shared_count >= ?
            ORDER BY shared_count DESC
            LIMIT ?
        """,
            (tab_id, tab_id, min_shared, limit),
        )

        results = []
        for row in cursor.fetchall():
            # Convert embedding if present
            embedding = None
            if row["embedding"]:
                embedding_blob = row["embedding"]
                num_floats = len(embedding_blob) // 4
                embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

            tab_dict = {
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "favicon_url": row["favicon_url"],
                "embedding": embedding,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "last_accessed": datetime.fromisoformat(row["last_accessed"]),
                "window_id": row["window_id"],
                "group_id": row["group_id"],
            }
            results.append((tab_dict, row["shared_count"]))

        return results

    def get_all_tabs(self) -> list[dict]:
        """
        Get all tabs from the database.

        Returns:
            List of tab dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tabs ORDER BY last_accessed DESC")

        tabs = []
        for row in cursor.fetchall():
            # Convert embedding if present
            embedding = None
            if row["embedding"]:
                embedding_blob = row["embedding"]
                num_floats = len(embedding_blob) // 4
                embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

            tabs.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "favicon_url": row["favicon_url"],
                "embedding": embedding,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "last_accessed": datetime.fromisoformat(row["last_accessed"]),
                "window_id": row["window_id"],
                "group_id": row["group_id"],
            })

        return tabs

    def remove_tab(self, tab_id: int) -> bool:
        """
        Remove a tab from the database.

        Note: This permanently deletes the tab. Consider using close_tab() instead
        to preserve temporal history.

        Args:
            tab_id: The tab ID to remove

        Returns:
            True if tab was removed, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tabs WHERE id = ?", (tab_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_active_tabs(self) -> list[dict]:
        """
        Get all currently active (open) tabs.

        Returns:
            List of active tab dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM tabs WHERE is_active = 1 ORDER BY last_accessed DESC"
        )

        tabs = []
        for row in cursor.fetchall():
            embedding = None
            if row["embedding"]:
                embedding_blob = row["embedding"]
                num_floats = len(embedding_blob) // 4
                embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

            tabs.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "favicon_url": row["favicon_url"],
                "embedding": embedding,
                "opened_at": datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
                "closed_at": datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "last_accessed": datetime.fromisoformat(row["last_accessed"]),
                "window_id": row["window_id"],
                "group_id": row["group_id"],
                "is_active": bool(row["is_active"]),
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
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM tabs
            WHERE opened_at <= ? AND (closed_at IS NULL OR closed_at >= ?)
            ORDER BY opened_at DESC
        """,
            (end_time.isoformat(), start_time.isoformat()),
        )

        tabs = []
        for row in cursor.fetchall():
            embedding = None
            if row["embedding"]:
                embedding_blob = row["embedding"]
                num_floats = len(embedding_blob) // 4
                embedding = list(struct.unpack(f'{num_floats}f', embedding_blob))

            tabs.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "favicon_url": row["favicon_url"],
                "embedding": embedding,
                "opened_at": datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
                "closed_at": datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "last_accessed": datetime.fromisoformat(row["last_accessed"]),
                "window_id": row["window_id"],
                "group_id": row["group_id"],
                "is_active": bool(row["is_active"]),
            })

        return tabs

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
        # Ensure tab_id_1 < tab_id_2 (undirected edge)
        if tab_id_1 > tab_id_2:
            tab_id_1, tab_id_2 = tab_id_2, tab_id_1

        cursor = self.conn.cursor()
        shared_entities_json = json.dumps(shared_entities)

        cursor.execute(
            """
            INSERT INTO tab_relationships
            (tab_id_1, tab_id_2, shared_entity_count, shared_entities,
             relationship_strength, first_connected, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(tab_id_1, tab_id_2) DO UPDATE SET
                shared_entity_count = ?,
                shared_entities = ?,
                relationship_strength = ?,
                last_updated = CURRENT_TIMESTAMP
        """,
            (
                tab_id_1,
                tab_id_2,
                len(shared_entities),
                shared_entities_json,
                relationship_strength,
                len(shared_entities),
                shared_entities_json,
                relationship_strength,
            ),
        )
        self.conn.commit()

    def get_tab_relationships(
        self, tab_id: int, min_strength: float = 0.0, limit: int = 50
    ) -> list[dict]:
        """
        Get all relationships for a specific tab.

        Args:
            tab_id: The tab ID
            min_strength: Minimum relationship strength (default: 0.0)
            limit: Maximum number of results (default: 50)

        Returns:
            List of relationship dictionaries with related tab info
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                CASE WHEN tr.tab_id_1 = ? THEN tr.tab_id_2 ELSE tr.tab_id_1 END as related_tab_id,
                tr.shared_entity_count,
                tr.shared_entities,
                tr.relationship_strength,
                tr.first_connected,
                tr.last_updated,
                t.title as related_tab_title,
                t.url as related_tab_url
            FROM tab_relationships tr
            JOIN tabs t ON (
                CASE WHEN tr.tab_id_1 = ? THEN tr.tab_id_2 ELSE tr.tab_id_1 END = t.id
            )
            WHERE (tr.tab_id_1 = ? OR tr.tab_id_2 = ?)
              AND tr.relationship_strength >= ?
            ORDER BY tr.relationship_strength DESC
            LIMIT ?
        """,
            (tab_id, tab_id, tab_id, tab_id, min_strength, limit),
        )

        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                "related_tab_id": row["related_tab_id"],
                "related_tab_title": row["related_tab_title"],
                "related_tab_url": row["related_tab_url"],
                "shared_entity_count": row["shared_entity_count"],
                "shared_entities": json.loads(row["shared_entities"])
                if row["shared_entities"]
                else [],
                "relationship_strength": row["relationship_strength"],
                "first_connected": datetime.fromisoformat(row["first_connected"]),
                "last_updated": datetime.fromisoformat(row["last_updated"]),
            })

        return relationships

    def get_all_tab_relationships(
        self, min_strength: float = 0.0
    ) -> list[dict]:
        """
        Get all tab relationships (for graph visualization).

        Args:
            min_strength: Minimum relationship strength (default: 0.0)

        Returns:
            List of all relationships
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM tab_relationships
            WHERE relationship_strength >= ?
            ORDER BY relationship_strength DESC
        """,
            (min_strength,),
        )

        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                "tab_id_1": row["tab_id_1"],
                "tab_id_2": row["tab_id_2"],
                "shared_entity_count": row["shared_entity_count"],
                "shared_entities": json.loads(row["shared_entities"])
                if row["shared_entities"]
                else [],
                "relationship_strength": row["relationship_strength"],
                "first_connected": datetime.fromisoformat(row["first_connected"]),
                "last_updated": datetime.fromisoformat(row["last_updated"]),
            })

        return relationships

    def compute_and_store_tab_relationships(
        self, tab_id: int, min_shared: int = 1
    ) -> int:
        """
        Compute relationships between a tab and all other tabs, and store them.

        This method:
        1. Finds all tabs sharing entities with the given tab
        2. Calculates relationship strength (Jaccard similarity)
        3. Stores/updates the relationships

        Args:
            tab_id: The tab ID to compute relationships for
            min_shared: Minimum shared entities required (default: 1)

        Returns:
            Number of relationships created/updated
        """
        # Get entities for this tab
        tab_entities = self.get_entities_for_tab(tab_id)
        if not tab_entities:
            return 0

        tab_entity_names = {e.name for e in tab_entities}

        # Find all other tabs with shared entities
        related_tabs = self.find_tabs_with_shared_entities(tab_id, min_shared)

        count = 0
        for related_tab, shared_count in related_tabs:
            related_tab_id = related_tab["id"]

            # Get entities for related tab
            related_entities = self.get_entities_for_tab(related_tab_id)
            related_entity_names = {e.name for e in related_entities}

            # Calculate shared entities
            shared_entity_names = tab_entity_names & related_entity_names
            shared_entities_list = sorted(list(shared_entity_names))

            # Calculate Jaccard similarity
            union_size = len(tab_entity_names | related_entity_names)
            relationship_strength = len(shared_entity_names) / union_size if union_size > 0 else 0.0

            # Store relationship
            self.update_tab_relationship(
                tab_id,
                related_tab_id,
                shared_entities_list,
                relationship_strength,
            )
            count += 1

        return count

    def rebuild_all_tab_relationships(self, min_shared: int = 1) -> int:
        """
        Rebuild all tab relationships from scratch.

        Warning: This can be expensive for large numbers of tabs.

        Args:
            min_shared: Minimum shared entities required (default: 1)

        Returns:
            Total number of relationships created
        """
        # Clear existing relationships
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tab_relationships")
        self.conn.commit()

        # Get all active tabs
        tabs = self.get_active_tabs()

        total_count = 0
        for tab in tabs:
            count = self.compute_and_store_tab_relationships(tab["id"], min_shared)
            total_count += count

        return total_count

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
        cursor = self.conn.cursor()

        # Convert related_concepts to JSON
        related_concepts_json = json.dumps(related_concepts)

        cursor.execute(
            """
            UPDATE entities
            SET web_description = ?,
                entity_type = ?,
                related_concepts = ?,
                source_url = ?,
                is_enriched = 1,
                enriched_at = ?
            WHERE id = ?
        """,
            (
                web_description,
                entity_type,
                related_concepts_json,
                source_url,
                datetime.now(),
                entity_id,
            ),
        )

        self.conn.commit()
        return cursor.rowcount > 0

    def needs_enrichment(self, entity_id: int, cache_ttl_days: int = 7) -> bool:
        """
        Check if an entity needs enrichment or re-enrichment.

        Args:
            entity_id: Entity ID to check
            cache_ttl_days: Cache TTL in days (default: 7)

        Returns:
            True if entity needs enrichment
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT is_enriched, enriched_at
            FROM entities
            WHERE id = ?
        """,
            (entity_id,),
        )
        row = cursor.fetchone()

        if not row:
            return False

        # Not enriched yet
        if not row["is_enriched"]:
            return True

        # Check if cache has expired
        if row["enriched_at"]:
            enriched_at = datetime.fromisoformat(row["enriched_at"])
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
        cursor = self.conn.cursor()

        # Calculate cache expiry timestamp
        from datetime import timedelta

        cache_expiry = datetime.now() - timedelta(days=cache_ttl_days)

        cursor.execute(
            """
            SELECT * FROM entities
            WHERE is_enriched = 0
               OR enriched_at IS NULL
               OR enriched_at < ?
            LIMIT ?
        """,
            (cache_expiry, limit),
        )

        entities = []
        for row in cursor.fetchall():
            # Parse related_concepts JSON
            related_concepts = []
            if row["related_concepts"]:
                try:
                    related_concepts = json.loads(row["related_concepts"])
                except json.JSONDecodeError:
                    related_concepts = []

            entities.append(
                Entity(
                    id=row["id"],
                    name=row["name"],
                    entity_type=row["entity_type"],
                    description=row["description"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    web_description=row["web_description"],
                    related_concepts=related_concepts,
                    source_url=row["source_url"],
                    is_enriched=bool(row["is_enriched"]),
                    enriched_at=datetime.fromisoformat(row["enriched_at"])
                    if row["enriched_at"]
                    else None,
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
