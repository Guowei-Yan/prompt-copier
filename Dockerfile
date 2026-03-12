FROM python:3.11-slim

WORKDIR /app

# Install git (for git operations), openssh-client (for SSH keys), and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen from lockfile)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app.py .
COPY config.py .
COPY models.py .
COPY prompts.py .
COPY git_service.py .
COPY ssh_keys.py .
COPY email_service.py .
COPY templates/ templates/

# Create data directory (for DB and SSH keys)
RUN mkdir -p /data /data/ssh_keys

# Environment variables with defaults
ENV PORT=5000
ENV DATABASE_PATH=/data/prompts.db
ENV SSH_KEYS_DIR=/data/ssh_keys
ENV AUTH_USERNAME=admin
ENV AUTH_PASSWORD=changeme
ENV SECRET_KEY=please-change-this-secret

EXPOSE 5000

CMD ["uv", "run", "python", "app.py"]
