from typing import List, Optional, Union

from pydantic import BaseModel, Field


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


class SchedulerConfig(BaseModel):
    enabled: bool = False
    check_interval: str = "15s"
    time_window: str = "00:00-23:59"
    days: List[str] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    actions: List[str] = []
    max_retries: int = 3
    notify_on: List[str] = []
    webhook: Optional[WebhookConfig] = None


class FullConfig(BaseModel):
    runners_defaults: RunnersDefaults
    runners: List[RunnerConfig]
    scheduler: Optional[SchedulerConfig] = None
