# Dockerfile pour GitHub Runner Manager
FROM python:3.13-slim

WORKDIR /app


# Installer les dépendances système nécessaires et le client Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    ca-certificates \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de l'application
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY main.py ./
COPY README.md ./
COPY infra/docker/supervisord.conf ./

# Installer Poetry et les dépendances Python
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY infra/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
