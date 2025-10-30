# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Copy dependency files first
COPY pyproject.toml ./
COPY .python-version ./

# Copy application code (needed for editable install)
COPY src/ ./src/

# Install dependencies and package in editable mode
RUN uv pip install --system -e .

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Run the application
CMD ["uvicorn", "kg_graph_search.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
