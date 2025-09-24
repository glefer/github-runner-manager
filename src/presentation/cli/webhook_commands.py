"""Commande de débogage et test des webhooks."""

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
    """Types d'événements pour les simulations de tests webhook."""

    RUNNER_STARTED = "runner_started"
    RUNNER_STOPPED = "runner_stopped"
    RUNNER_ERROR = "runner_error"
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    UPDATE_AVAILABLE = "update_available"
    UPDATE_APPLIED = "update_applied"


# Données de simulation pour chaque type d'événement
MOCK_DATA = {
    MockEvent.RUNNER_STARTED: {
        "runner_id": "php83-1",
        "runner_name": "itroom-runner-php83-1",
        "labels": "itroom-runner-set-php83, php8.3",
        "techno": "php",
        "techno_version": "8.3",
    },
    MockEvent.RUNNER_STOPPED: {
        "runner_id": "php83-1",
        "runner_name": "itroom-runner-php83-1",
        "uptime": "3h 24m 12s",
    },
    MockEvent.RUNNER_ERROR: {
        "runner_id": "php83-1",
        "runner_name": "itroom-runner-php83-1",
        "error_message": "Le runner n'a pas pu s'enregistrer auprès de GitHub: token invalide.",
    },
    MockEvent.BUILD_STARTED: {
        "image_name": "itroom-runner-php83",
        "base_image": "ghcr.io/actions/actions-runner:2.328.0",
        "techno": "php",
        "techno_version": "8.3",
    },
    MockEvent.BUILD_COMPLETED: {
        "image_name": "itroom-runner-php83",
        "duration": "45",
        "image_size": "1.2GB",
    },
    MockEvent.BUILD_FAILED: {
        "image_name": "itroom-runner-php83",
        "error_message": "Erreur lors de l'étape 3/8: npm install a échoué avec le code 1",
    },
    MockEvent.UPDATE_AVAILABLE: {
        "image_name": "actions-runner",
        "current_version": "2.328.0",
        "new_version": "2.329.0",
        "auto_update": "Activé",
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
    Teste l'envoi de webhooks avec des données simulées.

    Args:
        config_service: Service de configuration
        event_type: Type d'événement à simuler (si None, un menu sera affiché)
        provider: Fournisseur de webhook spécifique à utiliser
                (Si None, tous les fournisseurs configurés seront utilisés)
        interactive: Mode interactif avec confirmation et affichage détaillé
        console: Console Rich pour l'affichage

    Returns:
        Résultat de l'opération avec statuts pour chaque provider
    """
    console = console or Console()
    config = config_service.load_config()

    if not hasattr(config, "webhooks") or not config.webhooks:
        console.print(
            "[red]Aucune configuration webhook trouvée dans runners_config.yaml[/red]"
        )
        return {"error": "Aucune configuration webhook trouvée"}

    # Initialiser le service webhook
    webhook_service = WebhookService(config.webhooks.dict(), console)

    # Si aucun provider n'est initialisé
    if not webhook_service.providers:
        console.print(
            "[red]Aucun provider webhook n'est activé dans la configuration[/red]"
        )
        return {"error": "Aucun provider activé"}

    # Liste des providers disponibles
    available_providers = list(webhook_service.providers.keys())

    # Afficher les providers disponibles
    if interactive:
        console.print("[green]Providers webhook disponibles:[/green]")
        for provider_name in available_providers:
            console.print(f"  - {provider_name}")

    # Si aucun event_type n'est fourni, afficher un menu interactif
    if not event_type and interactive:
        event_choices = [e.value for e in MockEvent]
        event_type = Prompt.ask(
            "Choisissez un type d'événement à simuler",
            choices=event_choices,
            default=MockEvent.RUNNER_STARTED,
        )
    elif not event_type:
        event_type = MockEvent.RUNNER_STARTED

    # Vérifier si l'event_type est valide
    if event_type not in [e.value for e in MockEvent]:
        console.print(f"[red]Type d'événement '{event_type}' non valide[/red]")
        return {"error": f"Type d'événement '{event_type}' non valide"}

    # Si aucun provider n'est fourni et qu'on est en mode interactif, demander
    if not provider and interactive and len(available_providers) > 1:
        provider = Prompt.ask(
            "Choisissez un provider spécifique (laisser vide pour tous)",
            choices=available_providers + [""],
            default="",
        )

    # Récupérer les données simulées pour cet événement
    mock_data = MOCK_DATA.get(event_type, {}).copy()

    # Ajouter un timestamp
    mock_data["timestamp"] = datetime.datetime.now().isoformat()

    # Afficher un aperçu des données
    if interactive:
        console.print("\n[yellow]Données de simulation qui seront envoyées:[/yellow]")
        console.print(Panel(json.dumps(mock_data, indent=2), title="Données"))

        # Demander confirmation
        if not typer.confirm("Envoyer cette notification webhook?"):
            console.print("[yellow]Envoi annulé[/yellow]")
            return {"cancelled": True}

    # Envoyer la notification
    results = webhook_service.notify(
        event_type, mock_data, provider if provider else None
    )

    # Afficher les résultats
    if interactive:
        console.print("\n[bold]Résultats de l'envoi:[/bold]")
        for provider_name, success in results.items():
            if success:
                console.print(
                    f"[green]✅ {provider_name}: Notification envoyée avec succès[/green]"
                )
            else:
                console.print(f"[red]❌ {provider_name}: Échec de l'envoi[/red]")

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
    Teste tous les templates configurés pour un provider ou tous les providers.

    Args:
        config_service: Service de configuration
        provider: Provider spécifique à tester (si None, tous les providers seront testés)
        console: Console Rich pour l'affichage

    Returns:
        Résultats des tests pour chaque template
    """
    console = console or Console()
    config = config_service.load_config()

    if not hasattr(config, "webhooks") or not config.webhooks:
        console.print(
            "[red]Aucune configuration webhook trouvée dans runners_config.yaml[/red]"
        )
        return {"error": "Aucune configuration webhook trouvée"}

    # Initialiser le service webhook
    webhook_service = WebhookService(config.webhooks.dict(), console)

    # Si aucun provider n'est initialisé
    if not webhook_service.providers:
        console.print(
            "[red]Aucun provider webhook n'est activé dans la configuration[/red]"
        )
        return {"error": "Aucun provider activé"}

    # Liste des providers à tester
    providers_to_test = (
        [provider] if provider else list(webhook_service.providers.keys())
    )

    results = {}

    # Pour chaque provider
    for provider_name in providers_to_test:
        if provider_name not in webhook_service.providers:
            console.print(
                f"[yellow]Provider '{provider_name}' non configuré, ignoré[/yellow]"
            )
            continue

        provider_config = webhook_service.providers[provider_name]
        provider_events = provider_config.get("events", [])

        console.print(
            f"\n[bold blue]Test des templates pour {provider_name}:[/bold blue]"
        )

        provider_results = {}

        # Pour chaque type d'événement disponible
        for event_type in [e.value for e in MockEvent]:
            # Si cet événement est configuré pour ce provider
            if event_type in provider_events:
                console.print(f"\n[yellow]Test du template '{event_type}':[/yellow]")

                # Récupérer les données simulées
                mock_data = MOCK_DATA.get(event_type, {}).copy()
                mock_data["timestamp"] = datetime.datetime.now().isoformat()

                # Envoyer la notification
                success = webhook_service._send_notification(
                    provider_name, event_type, mock_data, provider_config
                )

                provider_results[event_type] = success

                if success:
                    console.print(
                        f"[green]✅ {event_type}: Notification envoyée avec succès[/green]"
                    )
                else:
                    console.print(f"[red]❌ {event_type}: Échec de l'envoi[/red]")
            else:
                console.print(
                    f"[dim]Template '{event_type}' non configuré pour {provider_name}, ignoré[/dim]"
                )

        results[provider_name] = provider_results

    return results
