"""
Webhook-related CLI commands for testing and debugging.
"""

import datetime
import json
from enum import Enum
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.services import ConfigService
from src.services.webhook_service import WebhookService


class MockEvent(str, Enum):
    """Events types for webhook test simulations."""

    RUNNER_STARTED = "runner_started"
    RUNNER_STOPPED = "runner_stopped"
    RUNNER_ERROR = "runner_error"
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    UPDATE_AVAILABLE = "update_available"
    UPDATE_APPLIED = "update_applied"


MOCK_DATA = {
    MockEvent.RUNNER_STARTED: {
        "runner_id": "php83-1",
        "runner_name": "my-runner-php83-1",
        "labels": "my-runner-set-php83, php8.3",
        "techno": "php",
        "techno_version": "8.3",
    },
    MockEvent.RUNNER_STOPPED: {
        "runner_id": "php83-1",
        "runner_name": "my-runner-php83-1",
        "uptime": "3h 24m 12s",
    },
    MockEvent.RUNNER_ERROR: {
        "runner_id": "php83-1",
        "runner_name": "my-runner-php83-1",
        "error_message": "The runner could not register with GitHub: invalid token.",
    },
    MockEvent.BUILD_STARTED: {
        "image_name": "my-runner-php83",
        "base_image": "ghcr.io/actions/actions-runner:2.328.0",
        "techno": "php",
        "techno_version": "8.3",
    },
    MockEvent.BUILD_COMPLETED: {
        "image_name": "my-runner-php83",
        "duration": "45",
        "image_size": "1.2GB",
    },
    MockEvent.BUILD_FAILED: {
        "image_name": "my-runner-php83",
        "error_message": "Error during step 3/8: npm install failed with code 1",
    },
    MockEvent.UPDATE_AVAILABLE: {
        "image_name": "actions-runner",
        "current_version": "2.328.0",
        "new_version": "2.329.0",
        "auto_update": "Enabled",
    },
    MockEvent.UPDATE_APPLIED: {
        "image_name": "actions-runner",
        "old_version": "2.328.0",
        "new_version": "2.329.0",
        "affected_runners": "php83-1, node20-1",
    },
}


def test_webhooks(
    config_service: ConfigService,
    event_type: Optional[str] = None,
    provider: Optional[str] = None,
    interactive: bool = True,
    console: Optional[Console] = None,
) -> Dict[str, Any]:
    """
    Test sending webhooks with simulated data.

    Args:
        config_service: Configuration service
        event_type: Event type to simulate (if None, a menu will be displayed)
        provider: Specific webhook provider to use
                (If None, all configured providers will be used)
        interactive: Interactive mode with confirmation and detailed display
        console: Rich Console for display

    Returns:
        Result of the operation with statuses for each provider
    """
    console = console or Console()
    config = config_service.load_config()

    if not hasattr(config, "webhooks") or not config.webhooks:
        console.print(
            "[red]No webhook configuration found in runners_config.yaml[/red]"
        )
        return {"error": "No webhook configuration found"}

    webhook_service = WebhookService(config.webhooks.dict(), console)

    if not webhook_service.providers:
        console.print("[red]No webhook provider is enabled in the configuration[/red]")
        return {"error": "No provider enabled"}

    available_providers = list(webhook_service.providers.keys())

    if interactive:
        console.print("[green]Available webhook providers:[/green]")
        for provider_name in available_providers:
            console.print(f"  - {provider_name}")

    if not event_type and interactive:
        event_choices = [e.value for e in MockEvent]
        event_type = Prompt.ask(
            "Choose an event type to simulate",
            choices=event_choices,
            default=MockEvent.RUNNER_STARTED,
        )
    elif not event_type:
        event_type = MockEvent.RUNNER_STARTED

    if event_type not in [e.value for e in MockEvent]:
        console.print(f"[red]Invalid event type '{event_type}'[/red]")
        return {"error": f"Invalid event type '{event_type}'"}

    if not provider and interactive and len(available_providers) > 1:
        provider = Prompt.ask(
            "Choose a specific provider (leave blank for all)",
            choices=available_providers + [""],
            default="",
        )

    mock_data = MOCK_DATA.get(event_type, {}).copy()

    mock_data["timestamp"] = datetime.datetime.now().isoformat()

    if interactive:
        console.print("\n[yellow]Simulation data to be sent:[/yellow]")
        console.print(Panel(json.dumps(mock_data, indent=2), title="Data"))

        # Ask for confirmation
        if not typer.confirm("Send this webhook notification?"):
            console.print("[yellow]Sending cancelled[/yellow]")
            return {"cancelled": True}

    results = webhook_service.notify(
        event_type, mock_data, provider if provider else None
    )

    if interactive:
        console.print("\n[bold]Results of the sending:[/bold]")
        for provider_name, success in results.items():
            if success:
                console.print(
                    f"[green]✅ {provider_name}: Notification sent successfully[/green]"
                )
            else:
                console.print(f"[red]❌ {provider_name}: Sending failed[/red]")

    return {
        "event_type": event_type,
        "provider": provider if provider else "all",
        "data": mock_data,
        "results": results,
    }


def debug_test_all_templates(
    config_service: ConfigService,
    provider: Optional[str] = None,
    console: Optional[Console] = None,
) -> Dict[str, Any]:
    """
    Test all templates configured for a provider or all providers.

    Args:
        config_service: Configuration service
        provider: Specific provider to test (if None, all providers will be tested)
        console: Rich Console for display

    Returns:
        Test results for each template
    """
    console = console or Console()
    config = config_service.load_config()

    if not hasattr(config, "webhooks") or not config.webhooks:
        console.print(
            "[red]No webhook configuration found in runners_config.yaml[/red]"
        )
        return {"error": "No webhook configuration found"}

    webhook_service = WebhookService(config.webhooks.dict(), console)

    if not webhook_service.providers:
        console.print("[red]No webhook provider is enabled in the configuration[/red]")
        return {"error": "No provider enabled"}

    providers_to_test = (
        [provider] if provider else list(webhook_service.providers.keys())
    )

    results = {}

    for provider_name in providers_to_test:
        if provider_name not in webhook_service.providers:
            console.print(
                f"[yellow]Provider '{provider_name}' not configured, skipping[/yellow]"
            )
            continue

        provider_config = webhook_service.providers[provider_name]
        provider_events = provider_config.get("events", [])

        console.print(
            f"\n[bold blue]Testing templates for {provider_name}:[/bold blue]"
        )

        provider_results = {}

        for event_type in [e.value for e in MockEvent]:
            if event_type in provider_events:
                console.print(f"\n[yellow]Testing template '{event_type}':[/yellow]")

                mock_data = MOCK_DATA.get(event_type, {}).copy()
                mock_data["timestamp"] = datetime.datetime.now().isoformat()

                success = webhook_service._send_notification(
                    provider_name, event_type, mock_data, provider_config
                )

                provider_results[event_type] = success

                if success:
                    console.print(
                        f"[green]✅ {event_type}: Notification sent successfully[/green]"
                    )
                else:
                    console.print(f"[red]❌ {event_type}: Sending failed[/red]")
            else:
                console.print(
                    f"[dim]Template '{event_type}' not configured for {provider_name}, skipping[/dim]"
                )

        results[provider_name] = provider_results

    return results
