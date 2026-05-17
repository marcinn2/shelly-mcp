# ---- build stage ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first — cached as long as lockfile doesn't change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY shelly_mcp/ ./shelly_mcp/
RUN uv sync --frozen --no-dev


# ---- runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Non-root user
RUN useradd -r -u 1001 -s /bin/false shelly

# Copy venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/shelly_mcp /app/shelly_mcp

ENV PATH="/app/.venv/bin:$PATH"

# config.json is mounted at runtime — see docker-compose.yml
EXPOSE 8000

USER shelly

# Default: run both SSE and Streamable HTTP.
# Override with -e or command arguments:
#   docker run ... shelly-mcp --sse --port 9000
CMD ["python", "-m", "shelly_mcp", "--server", "--host", "0.0.0.0", "--port", "8000"]
