#!/usr/bin/env python3
"""GitHub Runner Manager CLI - Main entry point."""

import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

load_dotenv()
console = Console()


def main():
    """Main entry point for the CLI application."""
    try:
        welcome_text = Text("GitHub Runner Manager", style="bold blue")
        console.print(Panel(welcome_text, title="Welcome", border_style="blue"))
        from src.presentation.cli.commands import app

        app()
    except KeyboardInterrupt:
        console.print("\nGoodbye!", style="yellow")
        sys.exit(0)
    except Exception as e:
        console.print(f"An error occurred: {e}", style="bold red")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
