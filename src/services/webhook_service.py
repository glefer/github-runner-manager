"""
Service de gestion des webhooks pour GitHub Runner Manager.
Ce service fournit une interface unifiée pour envoyer des notifications vers différents
services comme Slack, Discord, Microsoft Teams, etc.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import requests
from rich.console import Console

logger = logging.getLogger(__name__)


class WebhookProvider(Enum):
    """Types de fournisseurs de webhook supportés"""

    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    GENERIC = "generic"

    def __str__(self) -> str:
        return self.value


class WebhookService:
    """Service unifié pour la gestion des webhooks sortants."""

    def __init__(self, config: Dict[str, Any], console: Optional[Console] = None):
        """
        Initialise le service de webhooks.

        Args:
            config: Configuration des webhooks (section 'webhooks' du fichier de config)
            console: Console Rich pour l'affichage (optionnel)
        """
        self.config = config or {}
        self.console = console or Console()
        self.enabled = self.config.get("enabled", False)
        self.timeout = self.config.get("timeout", 10)
        self.retry_count = self.config.get("retry_count", 3)
        self.retry_delay = self.config.get("retry_delay", 5)

        # Initialisation des providers
        self.providers = {}

        # Si le service est activé, initialiser les providers configurés
        if self.enabled:
            self._init_providers()

    def _init_providers(self):
        """Initialise les providers de webhook configurés."""
        # Parcourir les fournisseurs connus
        for provider_name in WebhookProvider:
            provider_config = self.config.get(provider_name.value)

            # Si le fournisseur est configuré et activé
            if provider_config and provider_config.get("enabled", False):
                self.console.print(
                    f"[green]Initialisation du provider webhook [bold]{provider_name.value}[/bold][/green]"
                )

                # Stocker la configuration du provider
                self.providers[provider_name.value] = provider_config

    def notify(
        self, event_type: str, data: Dict[str, Any], provider: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Envoie une notification à tous les providers configurés pour cet événement.

        Args:
            event_type: Type d'événement à notifier (runner_started, build_failed, etc.)
            data: Données à inclure dans la notification
            provider: Provider spécifique à utiliser (optionnel)

        Returns:
            Dictionnaire avec les providers comme clés et les statuts comme valeurs
        """
        if not self.enabled:
            logger.info("Service webhook désactivé, notification ignorée")
            return {}

        results = {}

        # Filtrer les providers à utiliser
        providers_to_use = {}
        if provider:
            if provider in self.providers:
                providers_to_use = {provider: self.providers[provider]}
            else:
                self.console.print(
                    f"[yellow]Provider webhook [bold]{provider}[/bold] non configuré[/yellow]"
                )
                return {}
        else:
            providers_to_use = self.providers

        # Pour chaque provider configuré
        for provider_name, provider_config in providers_to_use.items():
            # Vérifier si cet événement est configuré pour ce provider
            if event_type in provider_config.get("events", []):
                # Envoyer la notification
                success = self._send_notification(
                    provider_name, event_type, data, provider_config
                )
                results[provider_name] = success

                if success:
                    self.console.print(
                        f"[green]Notification [bold]{event_type}[/bold] "
                        f"envoyée via [bold]{provider_name}[/bold][/green]"
                    )
                else:
                    self.console.print(
                        f"[red]Échec de l'envoi de la notification [bold]"
                        f"{event_type}[/bold] via [bold]{provider_name}[/bold][/red]"
                    )

        return results

    def _send_notification(
        self,
        provider: str,
        event_type: str,
        data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> bool:
        """
        Envoie une notification à un provider spécifique.

        Args:
            provider: Nom du provider (slack, discord, teams, etc.)
            event_type: Type d'événement à notifier
            data: Données à inclure dans la notification
            config: Configuration du provider

        Returns:
            True si l'envoi a réussi, False sinon
        """
        try:
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                logger.error(f"URL webhook manquante pour le provider {provider}")
                return False

            # Formatage spécifique au provider
            payload = None
            if provider == WebhookProvider.SLACK.value:
                payload = self._format_slack_payload(event_type, data, config)
            elif provider == WebhookProvider.DISCORD.value:
                payload = self._format_discord_payload(event_type, data, config)
            elif provider == WebhookProvider.TEAMS.value:
                payload = self._format_teams_payload(event_type, data, config)
            else:
                # Provider générique
                payload = self._format_generic_payload(event_type, data, config)

            # Envoi avec retry
            return self._send_with_retry(webhook_url, payload, config)

        except Exception as e:
            logger.exception(f"Erreur lors de l'envoi au provider {provider}: {str(e)}")
            return False

    def _send_with_retry(
        self, url: str, payload: Dict[str, Any], config: Dict[str, Any]
    ) -> bool:
        """
        Envoie une requête avec mécanisme de retry.

        Args:
            url: URL du webhook
            payload: Données à envoyer
            config: Configuration du provider

        Returns:
            True si l'envoi a réussi, False sinon
        """
        provider_timeout = config.get("timeout", self.timeout)
        retry_count = self.retry_count
        retry_delay = self.retry_delay

        # Headers par défaut
        headers = {"Content-Type": "application/json"}

        # En cas d'échec, réessayer
        for attempt in range(retry_count + 1):
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=provider_timeout
                )

                # Vérification du statut selon le provider
                if 200 <= response.status_code < 300:
                    return True

                logger.warning(
                    f"Tentative {attempt + 1}/{retry_count + 1}: "
                    f"Échec avec code {response.status_code}: {response.text}"
                )

                # Attendre avant de réessayer, sauf pour la dernière tentative
                if attempt < retry_count:
                    import time

                    time.sleep(retry_delay)

            except Exception as e:
                logger.warning(
                    f"Tentative {attempt + 1}/{retry_count + 1}: Exception: {str(e)}"
                )

        return False

    def _format_slack_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formate les données pour Slack.

        Args:
            event_type: Type d'événement
            data: Données à inclure
            config: Configuration Slack

        Returns:
            Payload formaté pour Slack
        """
        # Récupérer le template
        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            # Template minimal par défaut
            template = {
                "title": event_type.replace("_", " ").title(),
                "text": f"Événement {event_type}",
                "color": "#36a64f",
            }

        # Formater le titre et le texte
        title = self._format_string(template.get("title", ""), data)
        text = self._format_string(template.get("text", ""), data)
        color = template.get("color", "#36a64f")

        # Construction des attachments
        attachment = {
            "color": color,
            "title": title,
            "text": text,
            "fields": [],
            "footer": f"GitHub Runner Manager • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "mrkdwn_in": ["text", "fields"],
        }

        # Ajout des champs
        fields = template.get("fields", [])
        for field in fields:
            field_name = self._format_string(field.get("name", ""), data)
            field_value = self._format_string(field.get("value", ""), data)
            field_short = field.get("short", True)

            attachment["fields"].append(
                {"title": field_name, "value": field_value, "short": field_short}
            )

        # Message complet
        payload = {
            "username": config.get("username", "GitHub Runner Manager"),
            "text": text if not template.get("use_attachment", True) else "",
            "attachments": [attachment] if template.get("use_attachment", True) else [],
        }

        # Ajouter le channel si spécifié
        channel = config.get("channel")
        if channel:
            payload["channel"] = channel

        return payload

    def _format_discord_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formate les données pour Discord.

        Args:
            event_type: Type d'événement
            data: Données à inclure
            config: Configuration Discord

        Returns:
            Payload formaté pour Discord
        """
        # Récupérer le template
        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            # Template minimal par défaut
            template = {
                "title": event_type.replace("_", " ").title(),
                "description": f"Événement {event_type}",
                "color": 3066993,  # Vert
            }

        # Formater le titre et la description
        title = self._format_string(template.get("title", ""), data)
        description = self._format_string(template.get("description", ""), data)
        color = template.get("color", 3066993)  # Couleur par défaut: vert

        # Construction de l'embed
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
        }

        # Ajout des champs
        fields = template.get("fields", [])
        for field in fields:
            field_name = self._format_string(field.get("name", ""), data)
            field_value = self._format_string(field.get("value", ""), data)
            field_inline = field.get("inline", True)

            embed["fields"].append(
                {"name": field_name, "value": field_value, "inline": field_inline}
            )

        # Message complet
        payload = {
            "username": config.get("username", "GitHub Runner Manager"),
            "avatar_url": config.get("avatar_url", ""),
            "embeds": [embed],
        }

        return payload

    def _format_teams_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formate les données pour Microsoft Teams.

        Args:
            event_type: Type d'événement
            data: Données à inclure
            config: Configuration Teams

        Returns:
            Payload formaté pour Teams
        """
        # Récupérer le template
        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            # Template minimal par défaut
            template = {
                "title": event_type.replace("_", " ").title(),
                "themeColor": "0076D7",  # Bleu
                "sections": [{"activityTitle": f"Événement {event_type}", "facts": []}],
            }

        # Formater le titre
        title = self._format_string(template.get("title", ""), data)
        theme_color = template.get("themeColor", "0076D7")

        # Sections
        sections = []
        template_sections = template.get("sections", [])

        for section_template in template_sections:
            section = {}

            # Titre de l'activité
            if "activityTitle" in section_template:
                section["activityTitle"] = self._format_string(
                    section_template["activityTitle"], data
                )

            # Faits
            if "facts" in section_template:
                facts = []
                for fact_template in section_template["facts"]:
                    fact = {
                        "name": self._format_string(
                            fact_template.get("name", ""), data
                        ),
                        "value": self._format_string(
                            fact_template.get("value", ""), data
                        ),
                    }
                    facts.append(fact)
                section["facts"] = facts

            sections.append(section)

        # Message complet (Card adaptative)
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": title,
            "themeColor": theme_color,
            "title": title,
            "sections": sections,
        }

        return payload

    def _format_generic_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formate les données pour un webhook générique.

        Args:
            event_type: Type d'événement
            data: Données à inclure
            config: Configuration du webhook

        Returns:
            Payload formaté pour le webhook générique
        """
        # Message simple pour webhooks génériques
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        return payload

    def _format_string(self, template_str: str, data: Dict[str, Any]) -> str:
        """
        Formate une chaîne en remplaçant les variables par leurs valeurs.

        Args:
            template_str: Chaîne template avec variables {var}
            data: Dictionnaire de données

        Returns:
            Chaîne formatée
        """
        try:
            return template_str.format(**data)
        except KeyError as e:
            logger.warning(f"Variable manquante dans le template: {e}")
            return template_str
        except Exception as e:
            logger.warning(f"Erreur lors du formatage: {e}")
            return template_str
