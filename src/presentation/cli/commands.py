"""CLI commands for GitHub Runner Manager."""

from __future__ import annotations

import typer
from rich.console import Console

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

webhook_app = typer.Typer(help="Commandes pour tester et déboguer les webhooks")
webhook_app = typer.Typer(help="Commandes pour tester et déboguer les webhooks")


@app.command()
def build_runners_images(quiet: bool = False, progress: bool = True) -> None:
    """Build custom Docker images for runners defined in the YAML config.

    --quiet: reduces build verbosity, showing only steps and errors.
    """
    result = docker_service.build_runner_images(quiet=quiet, use_progress=progress)
    result = docker_service.build_runner_images(quiet=quiet, use_progress=progress)

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

    notification_service.notify_from_docker_result("build", result)


@app.command()
def start_runners() -> None:
    """Start Docker runners according to the YAML configuration."""
    result = docker_service.start_runners()

    for started in result.get("started", []):
        console.print(
            f"[green][INFO] Runner {started['name']} démarré avec succès.[/green]"
        )
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

        notification_service.notify_runner_started(
            {
                "runner_name": restarted.get("name", ""),
                "labels": restarted.get("labels", ""),
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
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", error.get("id", "")),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def stop_runners() -> None:
    """Stop Docker runners according to the YAML configuration (without deregistration)."""
    result = docker_service.stop_runners()

    for stopped in result.get("stopped", []):
        console.print(
            f"[green][INFO] Runner {stopped['name']} arrêté avec succès.[/green]"
        )
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
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", ""),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def remove_runners() -> None:
    """Deregister and remove Docker runners according to the YAML configuration."""
    result = docker_service.remove_runners()
    for deleted in result.get("deleted", []):
        name = deleted.get("name") or deleted.get("id") or "?"
        console.print(f"[green][INFO] Runner {name} supprimé avec succès.[/green]")
        notification_service.notify_runner_removed(
            {"runner_id": deleted.get("id", name), "runner_name": name}
        )

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
        notification_service.notify_runner_error(
            {
                "runner_id": error.get("id", ""),
                "runner_name": error.get("name", ""),
                "error_message": error.get("reason", "Unknown error"),
            }
        )


@app.command()
def check_base_image_update() -> None:
    """Check if a new GitHub runner image is available
    and suggest updating base_image in runners_config.yaml."""
    result = docker_service.check_base_image_update()

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
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

    notification_service.notify_update_available(
        {
            "runner_type": "base",
            "image_name": result.get("image_name", "unknown"),
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

            notification_service.notify_update_error(
                {
                    "runner_type": "base",
                    "image_name": result.get("image_name", "unknown"),
                    "error_message": update_result.get("error", "Unknown error"),
                }
            )
        elif update_result.get("updated"):
            console.print(
                f"[green]base_image mis à jour vers {update_result['new_image']} dans runners_config.yaml[/green]"
            )

            notification_service.notify_image_updated(
                {
                    "runner_type": "base",
                    "from_version": result.get("current_version", "unknown"),
                    "to_version": result.get("latest_version", "unknown"),
                    "image_name": update_result.get("new_image", ""),
                }
            )

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

                notification_service.notify_from_docker_result("build", build_result)

                if build_result.get("built"):
                    if typer.confirm(
                        "Voulez-vous déployer (démarrer) les nouveaux containers avec ces images ?"
                    ):
                        start_result = docker_service.start_runners()
                        for started in start_result.get("started", []):
                            console.print(
                                f"[green][INFO] Runner {started['name']} démarré avec succès.[/green]"
                            )

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
    """List the runners defined in the config and their status."""
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
    """Start the scheduler for automated task execution according to the configuration."""
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
    Test sending a webhook notification with simulated data.

    If no event type is specified, an interactive menu will be displayed.
    If no provider is specified, all configured providers will be used.
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
    Test all configured webhook templates.

    Sends a notification for each configured event type,
    for the specified provider or for all providers.
    """
    debug_test_all_templates(config_service, provider, console=console)


# Ajouter le sous-groupe webhook
app.add_typer(
    webhook_app, name="webhook", help="Commandes pour tester et déboguer les webhooks"
)

if __name__ == "__main__":  # pragma: no cover
    app()
