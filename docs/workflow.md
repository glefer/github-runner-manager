# Documentation du fonctionnement de l'application GitHub Runner Manager

## Présentation générale

L'application permet de gérer dynamiquement des runners GitHub auto-hébergés via une interface en ligne de commande (CLI). Elle facilite le déploiement, la gestion, la configuration et la supervision de runners dans des environnements Docker, avec prise en charge de différents langages et versions (Node, PHP, etc.).

## Fonctionnalités principales

- **Déploiement de runners** : Création et démarrage de nouveaux runners selon la configuration YAML.
- **Arrêt et suppression** : Arrêt, suppression ou nettoyage des runners existants.
- **Mise à jour des images** : Vérification et mise à jour des images Docker de base utilisées par les runners.
- **Liste et statut** : Affichage de la liste des runners, de leur état et de leurs informations détaillées.
- **Support multi-langages** : Gestion de runners pour différents environnements (Node, PHP, etc.) via des Dockerfiles dédiés.
- **Configuration centralisée** : Utilisation d'un fichier `runners_config.yaml` pour décrire les runners à gérer.

## États possibles d'un runner
$	$
Un runner peut se trouver dans l'un des états suivants :

- **créé** : Le runner est configuré mais pas encore démarré.
- **démarré** : Le runner est actif et prêt à exécuter des jobs GitHub Actions.
- **en cours d'exécution** : Le runner exécute actuellement un job.
- **arrêté** : Le runner est stoppé (container Docker arrêté).
- **supprimé** : Le runner et son container ont été supprimés.
- **en erreur** : Une erreur est survenue lors d'une opération (démarrage, arrêt, suppression, etc.).

## Workflows typiques


### 1. Déploiement d'un nouveau runner

```ascii
  +---------------------+
  | runners_config.yaml |
  +----------+----------+
          |
          v
  +---------------------+
  |  Commande CLI       |
  |  (deploy/start)     |
  +----------+----------+
          |
          v
  +---------------------+
  |  Runner "créé"      |
  +----------+----------+
          |
          v
  +---------------------+
  |  Runner "démarré"   |
  +---------------------+
```

### 2. Arrêt d'un runner

```ascii
  +---------------------+
  | Runner "démarré"    |
  +----------+----------+
          |
          v
  +---------------------+
  | Commande CLI stop   |
  +----------+----------+
          |
          v
  +---------------------+
  | Runner "arrêté"     |
  +---------------------+
```

### 3. Suppression d'un runner

```ascii
  +---------------------+
  | Runner "arrêté"     |
  +----------+----------+
          |
          v
  +---------------------+
  | Commande CLI remove |
  +----------+----------+
          |
          v
  +---------------------+
  | Runner "supprimé"   |
  +---------------------+
```

### 4. Mise à jour d'une image de base

```ascii
  +-----------------------------+
  | Commande CLI check/update   |
  +-------------+---------------+
            |
            v
  +-----------------------------+
  | Nouvelle image disponible ? |
  +-------------+---------------+
           Oui / Non
           /       \
          v         v
  [Mise à jour]  [Aucune action]
      |
      v
  +-----------------------------+
  | Redéploiement runners liés  |
  +-----------------------------+
```

## Exemples de commandes CLI

- `python main.py list` : Liste tous les runners et leur état.
- `python main.py start <runner>` : Démarre un runner spécifique.
- `python main.py stop <runner>` : Arrête un runner spécifique.
- `python main.py remove <runner>` : Supprime un runner spécifique.
- `python main.py check-base-image-update` : Vérifie les mises à jour des images Docker de base.

## Architecture technique

- **Fichier de configuration** : `runners_config.yaml` décrit les runners à gérer.
- **Services** :
  - `config_service.py` : Gestion de la configuration.
  - `docker_service.py` : Gestion des containers Docker.
- **CLI** : Interface utilisateur pour piloter l'application.


---

Pour plus de détails, consulter le reste de la documentation ou le code source.
