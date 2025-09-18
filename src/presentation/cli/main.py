"""Main CLI application entry point."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
app = typer.Typer(
    name="github-runner-manager",
    help="GitHub Runner Manager CLI with hexagonal architecture",
    rich_markup_mode="rich",
)


@app.command()
def hello(
    name: str = typer.Option("World", help="Name to greet"),
) -> None:
    """Say hello with Rich formatting."""
    greeting = Text(f"Hello, {name}!", style="bold green")
    panel = Panel(
        greeting, title="GitHub Runner Manager", border_style="blue", padding=(1, 2)
    )
    console.print(panel)


@app.command()
def status() -> None:
    """Show the status of GitHub runners."""
    console.print("[blue]Checking GitHub runners status...[/blue]")
    console.print("[green]✓ All runners are healthy[/green]")


@app.command()
def list() -> None:
    """List available GitHub runners."""
    console.print("[blue]Listing GitHub runners...[/blue]")
    console.print("[yellow]No runners configured yet[/yellow]")


if __name__ == "__main__":  # pragma: no cover
    app()
