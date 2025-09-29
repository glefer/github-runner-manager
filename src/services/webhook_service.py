"""
Webhook management service for GitHub Runner Manager.
This service provides a unified interface to send notifications to various
services such as Slack, Discord, Microsoft Teams, etc.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import requests
from rich.console import Console

logger = logging.getLogger(__name__)


class WebhookProvider(Enum):
    """Supported webhook provider types."""

    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    GENERIC = "generic"

    def __str__(self) -> str:
        return self.value


class WebhookService:
    """Unified service for managing outgoing webhooks."""

    def __init__(self, config: Dict[str, Any], console: Optional[Console] = None):
        """
        Initialize the webhook service.

        Args:
            config: Webhook configuration (the 'webhooks' section of the config file)
            console: Rich Console for display (optional)
        """
        self.config = config or {}
        self.console = console or Console()
        self.enabled = self.config.get("enabled", False)
        self.timeout = self.config.get("timeout", 10)
        self.retry_count = self.config.get("retry_count", 3)
        self.retry_delay = self.config.get("retry_delay", 5)

        self.providers = {}

        if self.enabled:
            self._init_providers()

    def _init_providers(self):
        """Initialize configured webhook providers."""
        # Iterate over known providers
        for provider_name in WebhookProvider:
            provider_config = self.config.get(provider_name.value)

            # If the provider is configured and enabled
            if provider_config and provider_config.get("enabled", False):
                self.console.print(
                    f"[green]Initializing webhook provider [bold]{provider_name.value}[/bold][/green]"
                )

                # Store the provider configuration
                self.providers[provider_name.value] = provider_config

    def notify(
        self, event_type: str, data: Dict[str, Any], provider: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Send a notification to all providers configured for this event.

        Args:
            event_type: Event type to notify (runner_started, build_failed, etc.)
            data: Data to include in the notification
            provider: Specific provider to use (optional)

        Returns:
            Dictionary with providers as keys and statuses as values
        """
        if not self.enabled:
            logger.info("Service webhook désactivé, notification ignorée")
            return {}

        results = {}

        # Filter the provider if specified
        providers_to_use = {}
        if provider:
            if provider in self.providers:
                providers_to_use = {provider: self.providers[provider]}
            else:
                self.console.print(
                    f"[yellow]Provider webhook [bold]{provider}[/bold] not configured[/yellow]"
                )
                return {}
        else:
            providers_to_use = self.providers

        for provider_name, provider_config in providers_to_use.items():
            if event_type in provider_config.get("events", []):
                success = self._send_notification(
                    provider_name, event_type, data, provider_config
                )
                results[provider_name] = success

                if success:
                    self.console.print(
                        f"[green]Notification [bold]{event_type}[/bold] "
                        f"sent to [bold]{provider_name}[/bold][/green]"
                    )
                else:
                    self.console.print(
                        f"[red]Failed to send notification [bold]"
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
        Send a notification to a specific provider.

        Args:
            provider: Provider name (slack, discord, teams, etc.)
            event_type: Event type to notify
            data: Data to include in the notification
            config: Provider configuration

        Returns:
            True if the send succeeded, False otherwise
        """
        try:
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                logger.error(f"Missing webhook URL for provider {provider}")
                return False

            payload = None
            if provider == WebhookProvider.SLACK.value:
                payload = self._format_slack_payload(event_type, data, config)
            elif provider == WebhookProvider.DISCORD.value:
                payload = self._format_discord_payload(event_type, data, config)
            elif provider == WebhookProvider.TEAMS.value:
                payload = self._format_teams_payload(event_type, data, config)
            else:
                payload = self._format_generic_payload(event_type, data, config)

            return self._send_with_retry(webhook_url, payload, config)

        except Exception as e:
            logger.exception(f"Error sending to provider {provider}: {str(e)}")
            return False

    def _send_with_retry(
        self, url: str, payload: Dict[str, Any], config: Dict[str, Any]
    ) -> bool:
        """
        Send a request with retry mechanism.

        Args:
            url: Webhook URL
            payload: Data to send
            config: Provider configuration

        Returns:
            True if the send succeeded, False otherwise
        """
        provider_timeout = config.get("timeout", self.timeout)
        retry_count = self.retry_count
        retry_delay = self.retry_delay

        headers = {"Content-Type": "application/json"}

        for attempt in range(retry_count + 1):
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=provider_timeout
                )

                if 200 <= response.status_code < 300:
                    return True

                logger.warning(
                    f"Attempt {attempt + 1}/{retry_count + 1}: "
                    f"Failed with status code {response.status_code}: {response.text}"
                )

                # Wait before retrying, except for the last attempt
                if attempt < retry_count:
                    import time

                    time.sleep(retry_delay)

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_count + 1}: Exception: {str(e)}"
                )

        return False

    def _format_slack_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format data for Slack.

        Args:
            event_type: Event type
            data: Data to include
            config: Slack configuration

        Returns:
            Payload formatted for Slack
        """

        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            template = {
                "title": event_type.replace("_", " ").title(),
                "text": f"Event {event_type}",
                "color": "#36a64f",
            }

        title = self._format_string(template.get("title", ""), data)
        text = self._format_string(template.get("text", ""), data)
        color = template.get("color", "#36a64f")

        attachment = {
            "color": color,
            "title": title,
            "text": text,
            "fields": [],
            "footer": f"GitHub Runner Manager • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "mrkdwn_in": ["text", "fields"],
        }

        fields = template.get("fields", [])
        for field in fields:
            field_name = self._format_string(field.get("name", ""), data)
            field_value = self._format_string(field.get("value", ""), data)
            field_short = field.get("short", True)

            attachment["fields"].append(
                {"title": field_name, "value": field_value, "short": field_short}
            )

        payload = {
            "username": config.get("username", "GitHub Runner Manager"),
            "text": text if not template.get("use_attachment", True) else "",
            "attachments": [attachment] if template.get("use_attachment", True) else [],
        }

        channel = config.get("channel")
        if channel:
            payload["channel"] = channel

        return payload

    def _format_discord_payload(
        self, event_type: str, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format data for Discord.

        Args:
            event_type: Event type
            data: Data to include
            config: Discord configuration

        Returns:
            Payload formatted for Discord
        """
        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            template = {
                "title": event_type.replace("_", " ").title(),
                "description": f"Event {event_type}",
                "color": 3066993,
            }

        title = self._format_string(template.get("title", ""), data)
        description = self._format_string(template.get("description", ""), data)
        color = template.get("color", 3066993)

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
        }

        fields = template.get("fields", [])
        for field in fields:
            field_name = self._format_string(field.get("name", ""), data)
            field_value = self._format_string(field.get("value", ""), data)
            field_inline = field.get("inline", True)

            embed["fields"].append(
                {"name": field_name, "value": field_value, "inline": field_inline}
            )

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
        Format data for Microsoft Teams.

        Args:
            event_type: Event type
            data: Data to include
            config: Teams configuration

        Returns:
            Payload formatted for Teams
        """
        templates = config.get("templates", {})
        template = templates.get(event_type, templates.get("default", {}))

        if not template:
            template = {
                "title": event_type.replace("_", " ").title(),
                "themeColor": "0076D7",
                "sections": [{"activityTitle": f"Event {event_type}", "facts": []}],
            }

        title = self._format_string(template.get("title", ""), data)
        theme_color = template.get("themeColor", "0076D7")

        sections = []
        template_sections = template.get("sections", [])

        for section_template in template_sections:
            section = {}

            if "activityTitle" in section_template:
                section["activityTitle"] = self._format_string(
                    section_template["activityTitle"], data
                )

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
        Format data for a generic webhook.

        Args:
            event_type: Event type
            data: Data to include
            config: Webhook configuration

        Returns:
            Payload formatted for the generic webhook
        """
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        return payload

    def _format_string(self, template_str: str, data: Dict[str, Any]) -> str:
        """
        Format a string by replacing variables with their values.

        Args:
            template_str: Template string with {var} variables
            data: Data dictionary

        Returns:
            Formatted string
        """
        try:
            return template_str.format(**data)
        except KeyError as e:
            logger.warning(f"Missing variable in template: {e}")
            return template_str
        except Exception as e:
            logger.warning(f"Error formatting string: {e}")
            return template_str
