# ==============================================================================
# Personal Agentic Fleet — Production Multi-Arch Container Image
# Rootless, Zero-Token Microkernel Architecture
# ==============================================================================

FROM python:3.12-slim-bookworm AS runner

# Security: Install minimal OS security updates and curl for healthcheck
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Security: Create non-root system group and user
RUN groupadd -g 10001 fleet && \
    useradd -u 10001 -g fleet -s /sbin/nologin -d /app -M fleet

WORKDIR /app

# Copy application files
COPY --chown=fleet:fleet fleet/ ./fleet/
COPY --chown=fleet:fleet docs/ ./docs/
COPY --chown=fleet:fleet pyproject.toml ./pyproject.toml
COPY --chown=fleet:fleet README.md ./README.md
COPY --chown=fleet:fleet LICENSE ./LICENSE
COPY --chown=fleet:fleet CHANGELOG.md ./CHANGELOG.md
COPY --chown=fleet:fleet schedules.yaml.example ./schedules.yaml.example
COPY --chown=fleet:fleet fleet.yaml.example ./fleet.yaml.example

# Create isolated data directories with strict non-root ownership
RUN mkdir -p /app/fleet/data/user /app/fleet/data/notes /app/fleet/data/uploads && \
    chown -R fleet:fleet /app/fleet/data && \
    chmod 700 /app/fleet/data/user

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLEET_HOST=0.0.0.0 \
    FLEET_PORT=7890 \
    PYTHONPATH=/app

# Expose Web Dashboard & REST API
EXPOSE 7890

# Security: Switch to unprivileged user
USER fleet:fleet

# Local deterministic health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7890/api/health', timeout=4)" || exit 1

# Launch microkernel and background daemon
CMD ["python", "-m", "fleet.app"]

