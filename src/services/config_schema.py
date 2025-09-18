from typing import List, Union

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


class FullConfig(BaseModel):
    runners_defaults: RunnersDefaults
    runners: List[RunnerConfig]
