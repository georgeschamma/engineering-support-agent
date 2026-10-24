import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Session:
    tenant: str
    user: str = "local-operator"
    role: str = "engineer"
    environment: str = "sandbox"


class Finding(BaseModel):
    claim: str
    evidence: str = Field(description="Relevant observation from a tool, including its source")


class Report(BaseModel):
    """An incident summary with supporting observations and a suggested next step."""

    summary: str
    findings: list[Finding]
    confidence: Literal["low", "medium", "high"]
    next_step: str


@dataclass(frozen=True)
class ModelSettings:
    model: str = "openai:openai/gpt-4.1-mini"
    temperature: float | None = 0.0
    reply_tokens: int = 2048
    request_timeout: float = 60.0

    @classmethod
    def from_environment(cls):
        sampling = os.environ.get("SUPPORT_TEMPERATURE", "0")
        return cls(
            model=os.environ.get("SUPPORT_MODEL", cls.model),
            temperature=None if sampling.strip().lower() in {"none", ""} else float(sampling),
            reply_tokens=int(os.environ.get("SUPPORT_REPLY_TOKENS", "2048")),
            request_timeout=float(os.environ.get("SUPPORT_REQUEST_TIMEOUT", "60")),
        )
