"""Configuration loader and data models for Goethe Facebook groups member requests."""

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
    member_requests_url: str = ""
    enabled: bool = True

    def get_member_requests_url(self) -> str:
        if self.member_requests_url:
            return self.member_requests_url
        clean_url = self.url.rstrip("/")
        if clean_url.endswith("/member-requests"):
            return clean_url
        return f"{clean_url}/member-requests"


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
            member_req_url = str(item.get("member_requests_url", "")).strip()
            enabled = bool(item.get("enabled", True))

            if name and (url or member_req_url):
                if not url and member_req_url:
                    url = member_req_url.replace("/member-requests", "")

                config = GoetheGroupConfig(
                    name=name,
                    url=url,
                    member_requests_url=member_req_url,
                    enabled=enabled,
                )
                configs.append(config)
        return configs
    except Exception as error:
        print(f"[GOETHE_CONFIG] Error loading config from '{path}': {error}")
        return []


def get_enabled_goethe_groups(config_file: str | Path | None = None) -> list[GoetheGroupConfig]:
    """Return enabled Goethe group configurations."""
    all_groups = load_goethe_groups_config(config_file)
    return [g for g in all_groups if g.enabled]
