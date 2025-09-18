# Github Runner Manager

![Banner](./docs/assets/logo.webp)

[![Workflow State](https://github.com/glefer/github-runner-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/glefer/github-runner-manager/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/glefer/github-runner-manager/branch/main/graph/badge.svg?token=JRjmc0emjT)](https://codecov.io/gh/glefer/github-runner-manager)
![Python](https://img.shields.io/badge/python-3.13-blue)
[![Docker](https://img.shields.io/docker/pulls/glefer/github-runner-manager)](https://hub.docker.com/r/glefer/github-runner-manager)

## � Utilisation dans un container Docker

Un `Dockerfile` est fourni pour exécuter l'application dans un container. Pour permettre à l'application de piloter Docker (création/suppression de containers runners), il faut monter le socket Docker de l'hôte dans le container.

### Exemple de build et run


```bash
# Build de l'image
docker build -t github-runner-manager .

# Lancement avec accès au Docker de l'hôte et aux Dockerfile custom
docker run --rm -it \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/runners_config.yaml:/app/runners_config.yaml \
    -v $(pwd)/config:/app/config:ro \
    github-runner-manager list-runners

> ℹ️ Depuis la version docker-py, le binaire `docker` n'est plus requis dans le container. Seul le montage du socket `/var/run/docker.sock` est nécessaire pour piloter Docker via l'API Python.
```

> ⚠️ Le montage du dossier `./config` est nécessaire pour les builds d'image runners personnalisés (Dockerfile custom).

Vous pouvez remplacer `list-runners` par n'importe quelle commande CLI du projet.

**Attention :**
- Le montage du socket Docker donne un accès complet à Docker sur l'hôte. À utiliser uniquement dans un contexte de confiance.
## �🔑 Authentification et configuration du token

Depuis septembre 2025, la gestion des runners GitHub utilise un token personnel GitHub (scopes : `admin:org`, `repo`) pour générer dynamiquement un registration token à chaque création ou suppression de runner.

**Exemple de configuration dans `runners_config.yaml` :**

```yaml
runners_defaults:
    base_image: ghcr.io/actions/actions-runner:2.328.0  # Image de base commune
    org_url: https://github.com/it-room
    github_personal_token: <VOTRE_TOKEN_PERSONNEL_GITHUB>  # scopes: admin:org, repo
```

Le registration token n'est plus stocké en dur : il est généré à la volée via l'API GitHub et injecté dans la variable d'environnement `RUNNER_TOKEN` du container. Cette variable est utilisée pour l'enregistrement et la suppression du runner (`config.sh remove`).

**Sécurité :**
- Ne partagez jamais votre token personnel.
- Privilégiez un token restreint à l'organisation ou au repo cible.

# GitHub Runner Manager

CLI de gestion des runners GitHub Actions avec Docker. Ce projet utilise une architecture en services simplifiée et adaptée à ses besoins.

## 🏗️ Architecture

Architecture simplifiée orientée services :

```
               +--------------------+
               |   Presentation     |
               |  (CLI Typer)       |
               +----------+---------+
                          |
                          v
               +-----------------------+
               |       Services        |
               |                       |
               | +-------------------+ |
               | |  DockerService    | |
               | +-------------------+ |
               |          |            |
               | +-------------------+ |
               | |  ConfigService    | |
               | +-------------------+ |
               +-----------------------+
```


## 🚀 Démarrage

### Prérequis

* Python 3.13+
* Poetry

### Installation

1. Cloner :
```bash
git clone <repository-url>
cd github-runner-manager
```
2. Installer :
```bash
poetry install
```
3. Aide :
```bash
poetry run python main.py --help
```

## 📋 Commandes

```
python main.py build-runners-images    # Construire les images Docker
python main.py start-runners           # Démarrer les runners Docker
python main.py stop-runners            # Arrêter les runners Docker
python main.py remove-runners          # Supprimer les runners Docker
python main.py check-base-image-update # Vérifier les mises à jour d'images
python main.py list-runners            # Lister les runners Docker
```

### Utilisation avec Make

```bash
make help              # Afficher l'aide
make install           # Installer les dépendances
make build-images      # Construire les images
make start-runners     # Démarrer les runners
make list-runners      # Lister les runners
```

### Exemples avec Poetry

```bash
poetry run python main.py build-runners-images
poetry run python main.py list-runners
```

## 🧪 Development

### Tests
```bash
poetry run pytest
```

### Qualité
```bash
poetry run black src tests
poetry run isort src tests
poetry run mypy src
```

### Pre-commit
```bash
poetry run pre-commit install
```

## 🛠️ Stack
Python 3.13, Poetry, Typer, Rich, pytest, Black, isort, mypy, Docker, YAML.

## 📝 Contribution
1. Respecter la séparation des responsabilités entre services
2. Ajouter des tests pour toute nouvelle fonctionnalité
3. Documenter les APIs des services modifiés/ajoutés
4. Assurer une bonne gestion des erreurs et des cas limites

## 📄 Licence
This project is licensed under the MIT license — see the LICENSE file.
