# Github Runner Manager

![Banner](./docs/assets/logo.webp)

[![Workflow State](https://github.com/glefer/github-runner-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/glefer/github-runner-manager/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/glefer/github-runner-manager/branch/main/graph/badge.svg?token=JRjmc0emjT)](https://codecov.io/gh/glefer/github-runner-manager)
![Python](https://img.shields.io/badge/python-3.13-blue)
[![Docker](https://img.shields.io/docker/pulls/glefer/github-runner-manager)](https://hub.docker.com/r/glefer/github-runner-manager)


Une application Python permettant de gérer facilement vos runners github depuis n'importe quel serveur ou en local.
![Output](./docs/assets/output.webp)

## 🚀 Démarrage

### Prérequis

* Python 3.13+
* Poetry

### Installation

1. Cloner :
```bash
git clone https://github.com/glefer/github-runner-manager
cd github-runner-manager
cp runners_config.yaml.dist runners_config.yaml
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



## ⏰ Scheduler

Le scheduler permet d'automatiser des actions sur les runners (vérification, build, etc.) selon une planification flexible définie dans le fichier de configuration (`runners_config.yaml`).

Le scheduler est lancé automatiquement dans le conteneur via Supervisor. Il n'est plus nécessaire d'activer ou désactiver le scheduler manuellement.

Pour plus de détails sur la configuration et le fonctionnement du scheduler, consultez la documentation dédiée : [docs/scheduler.md](./docs/scheduler.md)

---

## Configuration (.env et runners_config.yaml)

Bonne pratique : ne stockez jamais de secrets en clair dans `runners_config.yaml`.
Préférez :


Exemple minimal `.env` :
```dotenv
GITHUB_TOKEN=ghp_................................
```

### Webhooks (notifications)

GitHub Runner Manager supporte l'envoi de notifications via webhooks pour vous tenir informé des événements importants comme le démarrage/arrêt des runners, la construction d'images, ou les mises à jour disponibles.

Pour configurer les webhooks, ajoutez une section `webhooks` dans votre `runners_config.yaml` :

```yaml
webhooks:
  enabled: true
  timeout: 10
  retry_count: 3
  retry_delay: 5
  
  # Configuration pour Slack
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
    username: "GitHub Runner Bot"
    events:
      - runner_started
      - runner_error
      - build_completed
      - update_available
```

Les événements supportés incluent :
- `runner_started` : Quand un runner est démarré
- `runner_stopped` : Quand un runner est arrêté
- `runner_removed` : Quand un runner est supprimé
- `runner_error` : En cas d'erreur avec un runner
- `runner_skipped` : Quand une action sur un runner est ignorée (ex: arrêt d'un runner qui n'est pas démarré)
- `build_started` : Quand la construction d'une image démarre
- `build_completed` : Quand la construction d'une image est terminée
- `build_failed` : Quand la construction d'une image échoue
- `image_updated` : Quand une image est mise à jour
- `update_available` : Quand une mise à jour est disponible
- `update_applied` : Quand une mise à jour est appliquée
- `update_error` : En cas d'erreur lors d'une mise à jour

Plusieurs providers de webhooks sont supportés :
- Slack
- Discord
- Microsoft Teams
- Webhooks génériques

Pour des exemples de configuration complets, consultez :
```bash
cp runners_config.yaml.webhook-example runners_config.yaml
```

#### Tester les webhooks

Pour tester vos webhooks sans déclencher d'actions réelles :

```bash
# Tester un événement spécifique
python main.py webhook test --event runner_started --provider slack

# Tester tous les événements configurés
python main.py webhook test-all --provider slack
```
Un fichier d'exemple `runners_config.yaml.dist` est fourni à la racine du projet. Copiez-le pour créer votre propre configuration :

```bash
cp runners_config.yaml.dist runners_config.yaml
```

Exemple avancé de configuration de runner (`runners_config.yaml`) :
```yaml
runners:
    - id: php83
      name_prefix: my-runner-php83
      labels: [my-runner-set-php83, php8.3]
      nb: 2
      build_image: ./config/Dockerfile.php83
      techno: php
      techno_version: 8.3
```

Pour plus de détails sur la configuration du scheduler, consultez la documentation dédiée : [docs/scheduler.md](./docs/scheduler.md)
de définitions. Chaque définition inclut au minimum `name` et `image`.

Exemple simplifié (runners_config.yaml) :

```yaml
runners:
    - name: runner-1
      image: ghcr.io/actions/runner:latest
      labels: [linux, docker]
```

Le projet inclut un schéma de configuration (`src/services/config_schema.py`) qui
valide et normalise la configuration via Pydantic. Les tests utilisent ce schéma
pour s'assurer que les configurations d'exemple restent valides.


## Commandes CLI

L'outil expose une interface en ligne de commande (Typer) documentée via l'aide :

poetry run python main.py --help

Commandes courantes :

- list-runners            : lister les runners définis
- start-runners           : démarrer des runners
- stop-runners            : arrêter des runners
- remove-runners          : supprimer des runners (optionnel : en conservant les conteneurs)
- check-base-image-update : vérifier si les images de base ont des mises à jour disponibles




## Utilisation dans un container Docker

Un `Dockerfile` est fourni afin de pouvoir construire votre propre image si vous avez des besoins plus spécifiques.

### Entrypoint du conteneur

Le comportement du conteneur dépend du paramètre passé à l'entrée :

- `server` : lance le scheduler via Supervisor (`supervisord`).
- `<commande CLI>` : exécute la commande CLI Python (voir plus haut pour la liste des commandes).
- Aucun paramètre : affiche l'aide/usage et quitte.

### Exemple de build et run

```bash
# Build de l'image
docker build -t github-runner-manager .

# Lancer le scheduler (mode "serveur")
docker run --rm -it \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/runners_config.yaml:/app/runners_config.yaml \
    -v $(pwd)/config:/app/config:ro \
    github-runner-manager server

# Lancer une commande CLI (exemple : lister les runners)
docker run --rm -it \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/runners_config.yaml:/app/runners_config.yaml \
    -v $(pwd)/config:/app/config:ro \
    github-runner-manager list-runners
```

> ⚠️ Le montage du dossier `./config` est nécessaire pour les builds d'image runners personnalisés (Dockerfile custom).

Vous pouvez remplacer `list-runners` par n'importe quelle commande CLI du projet.

**Attention :**
- Le montage du socket Docker donne un accès complet à Docker sur l'hôte. À utiliser uniquement dans un contexte de confiance.
## Authentification et configuration du token

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
poetry run pre-commit
```


## Développement et tests

### 🛠️ Stack
Python 3.13, Poetry, Typer, Rich, pytest, Black, isort, mypy, Docker, YAML.

### Généralité
Le projet utilise `pytest` pour les tests unitaires. Les fixtures ont été
centralisées pour réduire la duplication et améliorer l'isolation des tests.

Exécuter la suite de tests :

poetry run pytest -q


## Sécurité et bonnes pratiques

- Ne commitez jamais de secrets (`GITHUB_TOKEN`, credentials Docker) dans le
    dépôt.
- Utilisez des variables d'environnement, des `.env` locaux (ignorés par Git), ou
    un gestionnaire de secrets (Vault, AWS Secrets Manager, etc.).
- Attention aux images de runners publiques — préférez des images officielles ou
    construites et auditées par vos équipes.



## 📝 Contribution
1. Respecter la séparation des responsabilités entre services
2. Ajouter des tests pour toute nouvelle fonctionnalité
3. Documenter les APIs des services modifiés/ajoutés
4. Assurer une bonne gestion des erreurs et des cas limites

## 📄 Licence
This project is licensed under the MIT license — see the LICENSE file.
