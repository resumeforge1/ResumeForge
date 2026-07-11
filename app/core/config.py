from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "data" / "ai_config.json"


DEFAULT_CONFIG = {
    "provider": "mock",
    "providers": {
        "mock": {"enabled": True},
        "openai": {"enabled": False, "model": "gpt-4.1-mini"},
        "anthropic": {"enabled": False, "model": "claude-3-5-sonnet-latest"},
        "gemini": {"enabled": False, "model": "gemini-1.5-pro"},
        "ollama": {"enabled": False, "model": "llama3.1", "base_url": "http://localhost:11434"},
    },
}


def load_ai_config() -> dict[str, Any]:
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
