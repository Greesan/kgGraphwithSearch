"""
TabGraph Backend Server Entry Point

Starts the FastAPI server for the TabGraph backend.

Usage:
    uv run python examples/start_server.py
"""

import sys
from pathlib import Path

# Add src to path so we can import kg_graph_search
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kg_graph_search.config import get_settings

def main():
    """Start the FastAPI server."""

    print("=" * 80)
    print("TabGraph Backend Server")
    print("=" * 80)
    print()

    # Verify configuration
    try:
        settings = get_settings()
        print("✓ Configuration loaded")
        print(f"  - OpenAI Model: {settings.openai_llm_model}")
        print(f"  - Embedding Model: {settings.openai_embedding_model}")
        print(f"  - Database: {settings.db_path}")
        print()
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        print()
        print("Please ensure you have a .env file with required API keys:")
        print("  - OPENAI_API_KEY")
        print("  - YOU_API_KEY")
        print()
        print("Copy .env.example to .env and add your keys.")
        sys.exit(1)

    # Start server
    print("Starting FastAPI server...")
    print(f"Server will be available at: http://localhost:8000")
    print(f"API documentation: http://localhost:8000/docs")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print()

    import uvicorn
    from kg_graph_search.server.app import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,  # Set to True for development
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n✗ Server error: {e}")
        sys.exit(1)
