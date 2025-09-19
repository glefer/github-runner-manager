# Dockerfile pour GitHub Runner Manager
FROM python:3.13-slim

WORKDIR /app


# Installer les dépendances système nécessaires et le client Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de l'application
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY main.py ./
COPY README.md ./

# Installer Poetry et les dépendances Python
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Par défaut, lance l'aide CLI
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
