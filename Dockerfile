# Dockerfile for GitHub Runner Manager
FROM python:3.13-slim

WORKDIR /app


# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    ca-certificates \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY main.py ./
COPY README.md ./
COPY infra/docker/supervisord.conf ./

# Install Poetry and Python dependencies
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY infra/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
