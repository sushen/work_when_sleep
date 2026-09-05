"""Configuration loader and data models for Goethe Facebook groups."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from search_interested.settings import GOETHE_GROUPS_CONFIG_FILE


@dataclass
class GoetheGroupConfig:
    name: str
    url: str
    enabled: bool = True
    search_interests: list[str] = field(default_factory=list)


def load_goethe_groups_config(config_file: str | Path | None = None) -> list[GoetheGroupConfig]:
    """Load and parse Goethe Facebook group configurations from JSON file."""
    path = Path(config_file or GOETHE_GROUPS_CONFIG_FILE)
    if not path.is_file():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        configs = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            enabled = bool(item.get("enabled", True))
            raw_interests = item.get("search_interests", [])
            interests = [
                str(kw).strip()
                for kw in raw_interests
                if kw and str(kw).strip()
            ]

            if name and url:
                configs.append(
                    GoetheGroupConfig(
                        name=name,
                        url=url,
                        enabled=enabled,
                        search_interests=interests,
                    )
                )
        return configs
    except Exception as error:
        print(f"[GOETHE_CONFIG] Error loading config from '{path}': {error}")
        return []


def get_enabled_goethe_groups(config_file: str | Path | None = None) -> list[GoetheGroupConfig]:
    """Return enabled Goethe group configurations."""
    all_groups = load_goethe_groups_config(config_file)
    return [g for g in all_groups if g.enabled]
