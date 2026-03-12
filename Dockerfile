FROM python:3.11-slim

WORKDIR /app


RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"


COPY pyproject.toml uv.lock ./


RUN uv sync --frozen --no-dev


COPY app.py .
COPY config.py .
COPY models.py .
COPY prompts.py .
COPY git_service.py .
COPY ssh_keys.py .
COPY email_service.py .
COPY templates/ templates/


RUN mkdir -p /data /data/ssh_keys


ENV PORT=5000
ENV DATABASE_PATH=/data/prompts.db
ENV SSH_KEYS_DIR=/data/ssh_keys
ENV AUTH_USERNAME=admin
ENV AUTH_PASSWORD=changeme
ENV SECRET_KEY=please-change-this-secret

EXPOSE 5000

CMD ["uv", "run", "python", "app.py"]
