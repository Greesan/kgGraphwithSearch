"""
Pydantic models for knowledge graph entities based on temporal agents cookbook.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Represents an entity in the knowledge graph."""

    id: Optional[int] = None
    name: str
    entity_type: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    # Enrichment fields (from You.com API)
    web_description: Optional[str] = None  # Legacy: single global description
    tab_contexts: dict[int, str] = Field(default_factory=dict)  # Per-tab contextual descriptions
    related_concepts: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    is_enriched: bool = False
    enriched_at: Optional[datetime] = None

    # Semantic embedding of entity name (for clustering)
    embedding: Optional[list[float]] = None


class TemporalValidityRange(BaseModel):
    """Represents the temporal validity of a relationship or fact."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_current: bool = True


class Triplet(BaseModel):
    """Represents a subject-predicate-object relationship in the knowledge graph."""

    id: Optional[int] = None
    subject_id: int
    subject_name: str
    predicate: str
    object_id: int
    object_name: str
    temporal_validity: Optional[TemporalValidityRange] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class TemporalEvent(BaseModel):
    """Represents a temporal event extracted from text."""

    event_type: str
    entities: list[str]
    timestamp: Optional[datetime] = None
    description: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RawStatement(BaseModel):
    """Raw statement extracted from text before processing."""

    text: str
    source: str
    timestamp: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class Chunk(BaseModel):
    """Text chunk for processing."""

    id: str
    text: str
    embedding: Optional[list[float]] = None
    metadata: dict = Field(default_factory=dict)


class QueryResult(BaseModel):
    """Result from a knowledge graph query."""

    entities: list[Entity]
    triplets: list[Triplet]
    confidence: float
    explanation: Optional[str] = None
