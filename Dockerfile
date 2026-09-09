# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /app

# Install git with apt cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends git curl

# Sync dependencies using uv cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# Copy project files and install project package
COPY meta_agent/ meta_agent/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Place virtual environment executables in PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_NO_SYNC=1

# Default configuration pointing to host Ollama
ENV OLLAMA_HOST=http://host.docker.internal:11434
