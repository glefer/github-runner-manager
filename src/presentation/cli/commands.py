"""CLI commands for GitHub Runner Manager."""

from __future__ import annotations

import typer
from rich.console import Console

# Importer les commandes webhook
from src.presentation.cli.webhook_commands import (
    debug_test_all_templates,
    test_webhooks,
)
from src.services import ConfigService, DockerService
from src.services.notification_service import NotificationService
from src.services.scheduler_service import SchedulerService

config_service = ConfigService()
docker_service = DockerService(config_service)
console = Console()
scheduler_service = SchedulerService(config_service, docker_service, console)
notification_service = NotificationService(config_service, console)

app = typer.Typer(
    help="GitHub Runner Manager - Gérez vos GitHub Actions runners Docker"
)
console = Console()

# Sous-commande pour les webhooks
webhook_app = typer.Typer(help="Commandes pour tester et déboguer les webhooks")


@app.command()
def build_runners_images(quiet: bool = False, progress: bool = True) -> None:
    """Build les images Docker custom des runners définis dans la config YAML.

    --quiet : réduit la verbosité du build en affichant uniquement les étapes et erreurs.
    """
    # (Notification de début de build supprimée)

    # Exécuter le build
    result = docker_service.build_runner_images(quiet=quiet, use_progress=progress)

    # Afficher les résultats
    for built in result.get("built", []):
        console.print(
            f"[green][SUCCESS] Image {built['image']} buildée depuis {built['dockerfile']}[/green]"
        )

    for skipped in result.get("skipped", []):
        console.print(
            f"[yellow][INFO] Pas d'image à builder pour {skipped['id']} ({skipped['reason']})[/yellow]"
        )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['id']}: {error['reason']}[/red]")

    # Envoyer les notifications du résultat
    notification_service.notify_from_docker_result("build", result)


@app.command()
def start_runners() -> None:
    """Lance les runners Docker selon la configuration YAML."""
    result = docker_service.start_runners()

    for started in result.get("started", []):
        console.print(
            f"[green][INFO] Runner {started['name']} démarré avec succès.[/green]"
        )

        # Notification de démarrage d'un runner
        notification_service.notify_runner_started(
            {
                "runner_id": started.get("id", ""),
                "runner_name": started.get("name", ""),
                "labels": started.get("labels", ""),
                "techno": started.get("techno", ""),
                "techno_version": started.get("techno_version", ""),
            }
        )

    for restarted in result.get("restarted", []):
        console.print(
            f"[yellow][INFO] Runner {restarted['name']} existant mais stoppé. Redémarrage...[/yellow]"
        )

        # Notification de redémarrage d'un runner
        notification_service.notify_runner_started(
            {
                "runner_id": restarted.get("id", ""),
                "runner_name": restarted.get("name", ""),
                "labels": restarted.get("labels", ""),
                "techno": restarted.get("techno", ""),
                "techno_version": restarted.get("techno_version", ""),
                "restarted": True,
            }
        )

    for running in result.get("running", []):
        console.print(
            f"[yellow][INFO] Runner {running['name']} déjà démarré. Rien à faire.[/yellow]"
        )

    for removed in result.get("removed", []):
        console.print(
            f"[yellow][INFO] Container {removed['name']} n'est plus requis et a été supprimé.[/yellow]"
        )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['id']}: {error['reason']}[/red]")

        # Notification d'erreur de démarrage d'un runner
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", error.get("id", "")),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def stop_runners() -> None:
    """Stoppe les runners Docker selon la configuration YAML (sans désenregistrement)."""
    result = docker_service.stop_runners()

    for stopped in result.get("stopped", []):
        console.print(
            f"[green][INFO] Runner {stopped['name']} arrêté avec succès.[/green]"
        )

        # Notification d'arrêt de runner
        notification_service.notify_runner_stopped(
            {
                "runner_id": stopped.get("id", ""),
                "runner_name": stopped.get("name", ""),
                "uptime": stopped.get("uptime", "unknown"),
            }
        )

    for skipped in result.get("skipped", []):
        console.print(
            f"[yellow][INFO] {skipped['name']} n'est pas en cours d'exécution.[/yellow]"
        )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['name']}: {error['reason']}[/red]")

        # Notification d'erreur d'arrêt de runner
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", ""),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def remove_runners() -> None:
    """Désenregistre et supprime les runners Docker selon la configuration YAML."""
    result = docker_service.remove_runners()
    # Ancienne clé 'deleted'
    for deleted in result.get("deleted", []):
        name = deleted.get("name") or deleted.get("id") or "?"
        console.print(f"[green][INFO] Runner {name} supprimé avec succès.[/green]")
        notification_service.notify_runner_removed(
            {"runner_id": deleted.get("id", name), "runner_name": name}
        )

    # Nouvelle clé 'removed' mais respecter les tests: n'afficher le succès
    # que si l'entrée possède 'container'. Les entrées avec uniquement 'name'
    # ne doivent pas produire le message (test attendu).
    for removed in result.get("removed", []):
        if "container" in removed:
            name = removed.get("container")
            console.print(f"[green][INFO] Runner {name} supprimé avec succès.[/green]")
            notification_service.notify_runner_removed(
                {"runner_id": removed.get("id", name), "runner_name": name}
            )

    for skipped in result.get("skipped", []):
        reason = skipped.get("reason")
        name = skipped.get("name", "?")
        if reason:
            console.print(f"[yellow][INFO] {name} {reason}.[/yellow]")
        else:
            console.print(
                f"[yellow][INFO] {name} n'est pas disponible à la suppression.[/yellow]"
            )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['name']}: {error['reason']}[/red]")

        # Notification d'erreur de suppression de runner
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", ""),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def check_base_image_update() -> None:
    """Vérifie si une nouvelle image runner GitHub est disponible
    et propose la mise à jour du base_image dans runners_config.yaml."""
    result = docker_service.check_base_image_update()

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")

        # Notification d'erreur de vérification
        notification_service.notify_update_error(
            {
                "runner_type": "base",
                "error_message": result.get("error", "Unknown error"),
            }
        )
        return

    if not result.get("update_available"):
        console.print(
            f"[green]L'image runner est déjà à jour : v{result['current_version']}[/green]"
        )
        return

    console.print(
        f"[yellow]Nouvelle version disponible : {result['latest_version']} "
        f"(actuelle : {result['current_version']})[/yellow]"
    )

    # Notification de mise à jour disponible
    notification_service.notify_update_available(
        {
            "runner_type": "base",
            "current_version": result.get("current_version", "unknown"),
            "available_version": result.get("latest_version", "unknown"),
        }
    )

    if typer.confirm(
        f"Mettre à jour base_image vers la version {result['latest_version']} dans runners_config.yaml ?"
    ):
        update_result = docker_service.check_base_image_update(auto_update=True)

        if update_result.get("error"):
            console.print(
                f"[red]Erreur lors de la mise à jour: {update_result['error']}[/red]"
            )

            # Notification d'erreur de mise à jour
            notification_service.notify_update_error(
                {
                    "runner_type": "base",
                    "error_message": update_result.get("error", "Unknown error"),
                }
            )
        elif update_result.get("updated"):
            console.print(
                f"[green]base_image mis à jour vers {update_result['new_image']} dans runners_config.yaml[/green]"
            )

            # Notification de mise à jour d'image
            notification_service.notify_image_updated(
                {
                    "runner_type": "base",
                    "from_version": result.get("current_version", "unknown"),
                    "to_version": result.get("latest_version", "unknown"),
                    "image_name": update_result.get("new_image", ""),
                }
            )

            # Proposer de builder les images avec cette nouvelle base
            if typer.confirm(
                f"Voulez-vous builder les images des runners avec la nouvelle image {update_result.get('new_image')} ?"
            ):
                # use progress bar for interactive post-update builds
                build_result = docker_service.build_runner_images(
                    quiet=False, use_progress=True
                )

                for built in build_result.get("built", []):
                    console.print(
                        f"[green][SUCCESS] Image {built['image']} buildée depuis {built['dockerfile']}[/green]"
                    )

                for skipped in build_result.get("skipped", []):
                    console.print(
                        f"[yellow][INFO] Pas d'image à builder pour {skipped['id']} ({skipped['reason']})[/yellow]"
                    )

                for error in build_result.get("errors", []):
                    console.print(
                        f"[red][ERREUR] {error['id']}: {error['reason']}[/red]"
                    )

                # Notification des résultats du build
                notification_service.notify_from_docker_result("build", build_result)

                # Proposer de déployer les nouveaux containers si des images ont été buildées
                if build_result.get("built"):
                    if typer.confirm(
                        "Voulez-vous déployer (démarrer) les nouveaux containers avec ces images ?"
                    ):
                        start_result = docker_service.start_runners()
                        for started in start_result.get("started", []):
                            console.print(
                                f"[green][INFO] Runner {started['name']} démarré avec succès.[/green]"
                            )

                            # Notification de démarrage d'un runner
                            notification_service.notify_runner_started(
                                {
                                    "runner_id": started.get("id", ""),
                                    "runner_name": started.get("name", ""),
                                    "labels": started.get("labels", ""),
                                    "techno": started.get("techno", ""),
                                    "techno_version": started.get("techno_version", ""),
                                }
                            )

                        for restarted in start_result.get("restarted", []):
                            console.print(
                                f"[yellow][INFO] Runner {restarted['name']} existant mais stoppé."
                                f" Redémarrage...[/yellow]"
                            )

                            # Notification de redémarrage d'un runner
                            notification_service.notify_runner_started(
                                {
                                    "runner_id": restarted.get("id", ""),
                                    "runner_name": restarted.get("name", ""),
                                    "labels": restarted.get("labels", ""),
                                    "techno": restarted.get("techno", ""),
                                    "techno_version": restarted.get(
                                        "techno_version", ""
                                    ),
                                    "restarted": True,
                                }
                            )

                        for running in start_result.get("running", []):
                            console.print(
                                f"[yellow][INFO] Runner {running['name']} déjà démarré. Rien à faire.[/yellow]"
                            )

                        for removed in start_result.get("removed", []):
                            console.print(
                                f"[yellow][INFO] Container {removed['name']} n'est plus requis "
                                f"et a été supprimé.[/yellow]"
                            )

                        for error in start_result.get("errors", []):
                            console.print(
                                f"[red][ERREUR] {error['id']}: {error['reason']}[/red]"
                            )

                            # Notification d'erreur de démarrage d'un runner
                            notification_service.notify_runner_error(
                                {
                                    "runner_id": error.get("id", ""),
                                    "runner_name": error.get(
                                        "name", error.get("id", "")
                                    ),
                                    "error_message": error.get(
                                        "reason", "Unknown error"
                                    ),
                                }
                            )
    else:
        console.print("[yellow]Mise à jour annulée.[/yellow]")


@app.command()
def list_runners() -> None:
    """Liste les runners définis dans la config et leur état"""
    from rich import box
    from rich.table import Table

    result = docker_service.list_runners()

    table = Table(title="Runners configurés", box=box.SIMPLE_HEAVY)
    table.add_column("Groupe", style="cyan", no_wrap=True)
    table.add_column("Actifs (total)", style="bold green", justify="center")
    table.add_column("Numéro", style="white", justify="right")
    table.add_column("Container", style="magenta")
    table.add_column("Etat", style="green")
    table.add_column("Labels", style="yellow")

    groups = result.get("groups", [])
    total_count = result.get("total", {}).get("count", 0)
    total_running = result.get("total", {}).get("running", 0)

    for group in groups:
        group_id = group["id"]
        nb = group["total"]
        running = group["running"]

        for runner in group["runners"]:
            i = runner["id"]
            runner_name = runner["name"]

            if runner["status"] == "running":
                etat = "✅ running"
            elif runner["status"] == "stopped":
                etat = "🟡 stopped"
            else:
                etat = "❌ absent"

            table.add_row(
                group_id if i == 1 else "",
                f"{running}/{nb}" if i == 1 else "",
                str(i),
                runner_name,
                etat,
                (
                    ", ".join(runner["labels"])
                    if isinstance(runner["labels"], list)
                    else str(runner["labels"])
                ),
            )

        for extra in group["extra_runners"]:
            idx = extra["id"]
            name = extra["name"]

            if group["runners"]:
                is_first_extra = idx == group["runners"][-1]["id"] + 1
            else:
                is_first_extra = True
            table.add_row(
                group_id if is_first_extra else "",
                "-",
                str(idx),
                name,
                "[red]⚠ sera supprimé[/red]",
                "",
            )

        if group != groups[-1]:
            table.add_row("", "", "", "", "", "")

    table.caption = (
        f"[bold blue]Total runners actifs : {total_running} / {total_count}[/bold blue]"
    )
    console.print(table)


@app.command()
def scheduler() -> None:
    """Démarre le scheduler pour l'exécution automatisée des tâches selon la configuration."""
    try:
        # Utilisation du service externe pour gérer le scheduler
        scheduler_service.start()
    except KeyboardInterrupt:
        console.print("[yellow]Scheduler arrêté manuellement.[/yellow]")
        scheduler_service.stop()
    except Exception as e:
        console.print(f"[red]Erreur dans le scheduler: {str(e)}[/red]")


@webhook_app.command("test")
def webhook_test(
    event_type: str = typer.Option(
        None, "--event", "-e", help="Type d'événement à simuler"
    ),
    provider: str = typer.Option(
        None, "--provider", "-p", help="Provider webhook spécifique à utiliser"
    ),
) -> None:
    """
    Teste l'envoi d'une notification webhook avec des données simulées.

    Si aucun type d'événement n'est spécifié, un menu interactif sera affiché.
    Si aucun provider n'est spécifié, tous les providers configurés seront utilisés.
    """
    test_webhooks(
        config_service, event_type, provider, interactive=True, console=console
    )


@webhook_app.command("test-all")
def webhook_test_all(
    provider: str = typer.Option(
        None, "--provider", "-p", help="Provider webhook spécifique à tester"
    )
) -> None:
    """
    Teste tous les templates webhook configurés.

    Envoie une notification pour chaque type d'événement configuré,
    pour le provider spécifié ou pour tous les providers.
    """
    debug_test_all_templates(config_service, provider, console=console)


# Ajouter le sous-groupe webhook
app.add_typer(
    webhook_app, name="webhook", help="Commandes pour tester et déboguer les webhooks"
)

if __name__ == "__main__":  # pragma: no cover
    app()
