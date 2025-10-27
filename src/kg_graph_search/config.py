"""
Configuration management for the application.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    openai_api_key: str
    you_api_key: str

    # Model Configuration
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"

    # Database Configuration
    db_path: Path = Path("./data/knowledge_graph.db")

    # Neo4j Configuration (optional)
    neo4j_uri: Optional[str] = "bolt://localhost:7687"
    neo4j_username: Optional[str] = "neo4j"
    neo4j_password: Optional[str] = None
    neo4j_database: Optional[str] = "neo4j"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings
