FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY config.py .
COPY models.py .
COPY prompts.py .
COPY templates/ templates/

# Create data directory
RUN mkdir -p /data

# Environment variables with defaults
ENV PORT=5000
ENV DATABASE_PATH=/data/prompts.db
ENV AUTH_USERNAME=admin
ENV AUTH_PASSWORD=changeme
ENV SECRET_KEY=please-change-this-secret

EXPOSE 5000

CMD ["python", "app.py"]
