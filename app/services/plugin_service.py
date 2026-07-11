from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import logging


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PLUGIN_DIR = BASE_DIR / "plugins"
logger = logging.getLogger(__name__)


def discover_plugins() -> list[dict[str, Any]]:
    plugins: list[dict[str, Any]] = []
    if not PLUGIN_DIR.exists():
        return plugins
    for manifest in PLUGIN_DIR.glob("*/plugin.json"):
        try:
            with manifest.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid plugin manifest %s: %s", manifest, exc)
            continue
        if not isinstance(data, dict) or not data.get("name"):
            logger.warning("Skipping plugin manifest without a name: %s", manifest)
            continue
        data["path"] = str(manifest.parent)
        plugins.append(data)
    return plugins


def plugin_capabilities() -> dict[str, list[str]]:
    caps = {
        "industry_keywords": [],
        "ai_prompts": [],
        "resume_templates": [],
        "cover_letters": [],
        "linkedin_templates": [],
        "interview_questions": [],
    }
    for plugin in discover_plugins():
        for key in caps:
            caps[key].extend(plugin.get(key, []))
    return caps
