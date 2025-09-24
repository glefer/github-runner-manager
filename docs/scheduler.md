# Scheduler – GitHub Runner Manager

Ce document explique la configuration et le fonctionnement du scheduler intégré à GitHub Runner Manager.

## Fonctionnement général

Le scheduler permet d'automatiser des actions (vérification, build, etc.) sur les runners selon une planification flexible définie dans le fichier de configuration (`runners_config.yaml`).

- **Intervalle** : Déclenchement périodique (secondes, minutes, heures)
- **Fenêtre horaire** : Plage d'heures autorisées pour l'exécution
- **Jours** : Jours de la semaine où le scheduler est actif
- **Actions** : Liste des actions à exécuter (ex : `check`, `build`, `deploy`)
- **Nombre maximal de tentatives** : Arrêt automatique après X échecs consécutifs

## Exemple de configuration (`runners_config.yaml`)

## Lancement et configuration du scheduler

Depuis la version avec Supervisor, le scheduler est automatiquement lancé dans le conteneur via supervisord. Il n'est plus nécessaire de configurer `scheduler.enabled` dans le fichier de configuration.

Le scheduler démarre automatiquement si le conteneur est lancé sans argument, grâce à l'entrypoint et à la configuration supervisord.

Exemple de lancement du scheduler via Docker :

```bash
docker run --rm -d \
   -v /var/run/docker.sock:/var/run/docker.sock \
   -v $(pwd)/runners_config.yaml:/app/runners_config.yaml \
   -v $(pwd)/config:/app/config:ro \
   a/github-runner-manager
```

## Exemple de configuration (`runners_config.yaml`)

```yaml
scheduler:
  check_interval: "30m"         # Intervalle entre deux exécutions (ex: 30s, 10m, 1h)
  time_window: "08:00-20:00"    # Plage horaire autorisée (HH:MM-HH:MM)
  days: [mon, tue, wed, thu, fri] # Jours autorisés (mon, tue, ...)
  actions: [check, build, deploy] # Actions à exécuter (deploy = auto start des runners après build)
  max_retries: 3                 # Nombre maximal de tentatives en cas d'échec
```

## Détail des paramètres

- **check_interval** : Format `<nombre><unité>` (ex: `30s`, `10m`, `1h`). Unité :
   - `s` : secondes
   - `m` : minutes
   - `h` : heures
- **time_window** : Plage horaire d'exécution autorisée (ex: `08:00-20:00`)
- **days** : Liste des jours autorisés (`mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`)
- **actions** :
   - `check` : Vérifie si une nouvelle version de l'image de base est disponible
   - `build` : Reconstruit les images runners si une mise à jour est détectée (et met à jour la config si update)
   - `deploy` : Si présent avec `build`, et au moins une image a été reconstruite, lance automatiquement les runners (start/restart) sans interaction.
- **max_retries** : Nombre maximal de tentatives consécutives avant arrêt automatique

## Fonctionnement détaillé

1. **Chargement de la configuration** :
   - Les paramètres sont validés (syntaxe, valeurs autorisées).
2. **Planification** :
   - Le scheduler utilise la librairie Python [`schedule`](https://schedule.readthedocs.io/) pour planifier les tâches.
   - L'intervalle (`check_interval`) et les jours (`days`) sont combinés pour définir la fréquence d'exécution.
   - La plage horaire (`time_window`) limite l'exécution aux heures autorisées.
3. **Exécution** :
   - À chaque déclenchement, le scheduler vérifie la fenêtre horaire et exécute les actions configurées.
   - En cas d'échec, le compteur de tentatives est incrémenté. Si le maximum est atteint, le scheduler s'arrête.

## Bonnes pratiques

- Utilisez des intervalles raisonnables pour éviter une charge excessive.
- Privilégiez des plages horaires adaptées à vos besoins (ex : heures ouvrées).
- Surveillez les logs pour détecter d'éventuels échecs répétés.

## Dépendances

- [schedule](https://pypi.org/project/schedule/) : Librairie de planification Python

---

Pour toute question ou suggestion, ouvrez une issue sur le dépôt GitHub du projet.
