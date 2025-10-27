"""
Abstract base class for graph storage backends.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .models import Entity, Triplet


class GraphStore(ABC):
    """Abstract interface for knowledge graph storage backends."""

    @abstractmethod
    def add_entity(self, entity: Entity) -> int:
        """
        Add an entity to the graph.

        Args:
            entity: Entity to add

        Returns:
            ID of the inserted or existing entity
        """
        pass

    @abstractmethod
    def get_entity(self, entity_id: int) -> Optional[Entity]:
        """
        Get an entity by ID.

        Args:
            entity_id: ID of the entity

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def find_entity_by_name(
        self, name: str, entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """
        Find an entity by name and optionally type.

        Args:
            name: Entity name
            entity_type: Optional entity type filter

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def add_triplet(self, triplet: Triplet) -> int:
        """
        Add a triplet (relationship) to the graph.

        Args:
            triplet: Triplet to add

        Returns:
            ID of the inserted triplet
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def search_entities(self, query: str, limit: int = 10) -> list[Entity]:
        """
        Search for entities by name.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching entities
        """
        pass

    @abstractmethod
    def close(self):
        """Close the database connection."""
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
