from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl


class RunnerConfig(BaseModel):
    id: str
    name_prefix: str
    labels: List[str]
    nb: int = Field(ge=0)
    build_image: Union[str, None] = None
    techno: Union[str, None] = None
    techno_version: Union[str, int, float, None] = None


class RunnersDefaults(BaseModel):
    base_image: str
    org_url: str


class WebhookConfig(BaseModel):
    url: str
    events: List[str] = []


# Définitions communes pour les champs de notification
class NotificationField(BaseModel):
    """Configuration d'un champ dans une notification"""

    name: str
    value: str
    short: bool = True  # Pour Slack
    inline: bool = True  # Pour Discord


# Templates pour Slack
class SlackTemplateConfig(BaseModel):
    """Template pour une notification Slack"""

    title: str
    text: str
    color: str = "#36a64f"  # Vert par défaut
    use_attachment: bool = True
    fields: List[NotificationField] = []


# Templates pour Discord
class DiscordTemplateConfig(BaseModel):
    """Template pour une notification Discord"""

    title: str
    description: str
    color: int = 3066993  # Vert en décimal
    fields: List[NotificationField] = []


# Section pour Teams
class TeamsSection(BaseModel):
    """Section dans une carte Microsoft Teams"""

    activityTitle: str
    facts: List[Dict[str, str]] = []


# Templates pour Microsoft Teams
class TeamsTemplateConfig(BaseModel):
    """Template pour une notification Microsoft Teams"""

    title: str
    themeColor: str = "0076D7"  # Bleu par défaut
    sections: List[TeamsSection] = []


# Configuration Slack
class SlackConfig(BaseModel):
    """Configuration des notifications Slack"""

    enabled: bool = False
    webhook_url: HttpUrl
    channel: str = ""  # Optionnel, peut être défini dans l'URL du webhook
    username: str = "GitHub Runner Manager"
    timeout: int = 10
    events: List[str] = []
    templates: Dict[str, SlackTemplateConfig] = {}


# Configuration Discord
class DiscordConfig(BaseModel):
    """Configuration des notifications Discord"""

    enabled: bool = False
    webhook_url: HttpUrl
    username: str = "GitHub Runner Manager"
    avatar_url: Optional[HttpUrl] = None
    timeout: int = 10
    events: List[str] = []
    templates: Dict[str, DiscordTemplateConfig] = {}


# Configuration Microsoft Teams
class TeamsConfig(BaseModel):
    """Configuration des notifications Microsoft Teams"""

    enabled: bool = False
    webhook_url: HttpUrl
    timeout: int = 10
    events: List[str] = []
    templates: Dict[str, TeamsTemplateConfig] = {}


class SchedulerConfig(BaseModel):
    enabled: bool = False
    check_interval: str = "15s"
    time_window: str = "00:00-23:59"
    days: List[str] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    actions: List[str] = []
    max_retries: int = 3
    notify_on: List[str] = []
    webhook: Optional[WebhookConfig] = None


# Configuration globale des webhooks
class WebhooksConfig(BaseModel):
    """Configuration globale des webhooks"""

    enabled: bool = False
    timeout: int = 10
    retry_count: int = 3
    retry_delay: int = 5
    slack: Optional[SlackConfig] = None
    discord: Optional[DiscordConfig] = None
    teams: Optional[TeamsConfig] = None


class FullConfig(BaseModel):
    runners_defaults: RunnersDefaults
    runners: List[RunnerConfig]
    scheduler: Optional[SchedulerConfig] = None
    webhooks: Optional[WebhooksConfig] = None
