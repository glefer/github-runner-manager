"""CLI commands for GitHub Runner Manager."""

from __future__ import annotations

import typer
from rich.console import Console

from src.services import ConfigService, DockerService

config_service = ConfigService()
docker_service = DockerService(config_service)

app = typer.Typer(
    help="GitHub Runner Manager - Gérez vos GitHub Actions runners Docker"
)
console = Console()


@app.command()
def build_runners_images(quiet: bool = False, progress: bool = True) -> None:
    """Build les images Docker custom des runners définis dans la config YAML.

    --quiet : réduit la verbosité du build en affichant uniquement les étapes et erreurs.
    """
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


@app.command()
def start_runners() -> None:
    """Lance les runners Docker selon la configuration YAML."""
    result = docker_service.start_runners()

    for started in result.get("started", []):
        console.print(
            f"[green][INFO] Runner {started['name']} démarré avec succès.[/green]"
        )

    for restarted in result.get("restarted", []):
        console.print(
            f"[yellow][INFO] Runner {restarted['name']} existant mais stoppé. Redémarrage...[/yellow]"
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


@app.command()
def stop_runners() -> None:
    """Stoppe les runners Docker selon la configuration YAML (sans désenregistrement)."""
    result = docker_service.stop_runners()

    for stopped in result.get("stopped", []):
        console.print(
            f"[green][INFO] Runner {stopped['name']} arrêté avec succès.[/green]"
        )

    for skipped in result.get("skipped", []):
        console.print(
            f"[yellow][INFO] {skipped['name']} n'est pas en cours d'exécution.[/yellow]"
        )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['name']}: {error['reason']}[/red]")


@app.command()
def remove_runners() -> None:
    """Désenregistre les runners (config.sh remove) et supprime le container et le dossier runner."""
    result = docker_service.remove_runners()

    for removed in result.get("removed", []):
        if "container" in removed:
            console.print(
                f"[green][INFO] Container {removed['container']} supprimé avec succès.[/green]"
            )

    for skipped in result.get("skipped", []):
        console.print(
            f"[yellow][INFO] {skipped['name']} : {skipped['reason']}.[/yellow]"
        )

    for error in result.get("errors", []):
        console.print(f"[red][ERREUR] {error['name']}: {error['reason']}[/red]")


@app.command()
def check_base_image_update() -> None:
    """Vérifie si une nouvelle image runner GitHub est disponible
    et propose la mise à jour du base_image dans runners_config.yaml."""
    result = docker_service.check_base_image_update()

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
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

    if typer.confirm(
        f"Mettre à jour base_image vers la version {result['latest_version']} dans runners_config.yaml ?"
    ):
        update_result = docker_service.check_base_image_update(auto_update=True)

        if update_result.get("error"):
            console.print(
                f"[red]Erreur lors de la mise à jour: {update_result['error']}[/red]"
            )
        elif update_result.get("updated"):
            console.print(
                f"[green]base_image mis à jour vers {update_result['new_image']} dans runners_config.yaml[/green]"
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


if __name__ == "__main__":  # pragma: no cover
    app()
