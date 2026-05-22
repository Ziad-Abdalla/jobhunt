# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build deps ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv (the project's preferred installer) into the builder image.
RUN pip install uv

# Copy only what's needed to resolve and install the project.
COPY pyproject.toml README.md ./
COPY src ./src

# Install the project itself (no dev/optional groups) into the system site-packages
# so we can copy them into the runtime stage cleanly.
RUN uv pip install --system -e .


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    JOBHUNT_HOST=0.0.0.0 \
    JOBHUNT_PORT=8765

# curl is needed for HEALTHCHECK. Keep the runtime layer thin otherwise.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user.
RUN useradd -m -u 1001 jobhunt

WORKDIR /app

# Copy installed Python packages and console scripts from the builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source so the editable install resolves to a real path inside
# the runtime image.
COPY --chown=jobhunt:jobhunt pyproject.toml README.md ./
COPY --chown=jobhunt:jobhunt src ./src

# Pre-create the data directory and hand it to the non-root user. When the
# host mounts ./data into /app/data this is the mount target.
RUN mkdir -p /app/data && chown -R jobhunt:jobhunt /app

USER jobhunt

EXPOSE 8765

# The app doesn't yet have a /api/healthz route, so probe the index instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8765/ || exit 1

CMD ["jobhunt", "serve"]
