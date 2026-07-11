from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import load_ai_config


class AIProvider(Protocol):
    def rewrite(self, text: str, instruction: str) -> str:
        ...


@dataclass
class MockProvider:
    """Deterministic provider used until a paid or local AI provider is configured."""

    def rewrite(self, text: str, instruction: str) -> str:
        if not text.strip():
            return ""
        cleaned = " ".join(text.split())
        if instruction == "summary":
            return f"{cleaned} Demonstrates reliable execution, clear communication, and consistent attention to detail."
        if instruction == "skills":
            return cleaned
        if instruction == "cover_letter":
            return cleaned.replace("I am excited", "I am pleased")
        return cleaned


def get_ai_provider() -> AIProvider:
    config = load_ai_config()
    provider_name = config.get("provider", "mock")
    if provider_name != "mock":
        # Provider adapters are intentionally separated from the app surface. Until API keys
        # are configured, fall back to deterministic behavior rather than failing user work.
        return MockProvider()
    return MockProvider()
