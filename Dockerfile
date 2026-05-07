# ── build stage ──────────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv, no project itself yet
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the source
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# ── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

WORKDIR /app

# Copy the virtualenv and source from the build stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

# Make sure the venv's Python/scripts are used
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Environment variables (override at runtime via --env-file or -e flags)
ENV MAX_BASE_URL=https://platform-api.max.ru
# MAX_TOKEN=f9LHodD0cOL1jvkMIHw-v20p-whY9dnQNZnM1Ce32Lc5LSi4RlNw7gBcDSojWlPejz3tWxobDY5j4VMMDccH
ENV BASE_URL=https://platform-api.max.ru
ENV TG_TOKEN=6982276565:AAFT49C0GSYy4JFV9fXoSGMKO4cxSYxa6NI
ENV TG_CHANNEL_ID=421349553
ENV ACCEPTED_MAX_CHANNEL=-74482790928409

# MAX_TOKEN, TG_TOKEN, TG_CHANNEL_ID, ACCEPTED_MAX_CHANNEL — set at runtime

CMD ["python", "main.py"]
