"""Group lifecycle management based on opportunity performance."""

from __future__ import annotations

import datetime
import json
import os
import pathlib
from typing import Any, Dict, List, Optional

from .group_queue import load_group_urls, move_group_to_inactive
from .settings import (
    GROUP_LIST_FILE,
    INACTIVE_GROUPS_FILE,
    PACKAGE_DIRECTORY,
    SAVE_QUALITY_LEVELS,
)


class GroupLifecycleManager:
    """Manages group active/inactive status based on real opportunity results."""

    def __init__(
        self,
        stats_file: Optional[pathlib.Path | str] = None,
        group_list_file: Optional[pathlib.Path | str] = None,
        inactive_groups_file: Optional[pathlib.Path | str] = None,
        max_inactive_days: int = 14,
    ) -> None:
        if stats_file is None:
            self.stats_file = PACKAGE_DIRECTORY / "group_stats.json"
        else:
            self.stats_file = pathlib.Path(stats_file)

        if group_list_file is None:
            self.group_list_file = GROUP_LIST_FILE
        else:
            self.group_list_file = pathlib.Path(group_list_file)

        if inactive_groups_file is None:
            self.inactive_groups_file = INACTIVE_GROUPS_FILE
        else:
            self.inactive_groups_file = pathlib.Path(inactive_groups_file)

        self.max_inactive_days = max_inactive_days
        self.stats: Dict[str, Dict[str, Any]] = self._load_stats()

    def _load_stats(self) -> Dict[str, Dict[str, Any]]:
        """Loads stats from JSON file. Returns empty dict if missing or invalid."""
        if not self.stats_file.exists():
            return {}

        try:
            with open(self.stats_file, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
                return {}
        except (OSError, json.JSONDecodeError) as error:
            print(f"[ERROR] Could not load group stats from {self.stats_file}: {error}")
            return {}

    def _save_stats(self) -> bool:
        """Atomically saves stats to JSON file."""
        temp_file = self.stats_file.with_name(f"{self.stats_file.name}.tmp")
        try:
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_file, "w", encoding="utf-8", newline="\n") as file:
                json.dump(self.stats, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_file, self.stats_file)
            return True
        except OSError as error:
            print(f"[ERROR] Could not save group stats to {self.stats_file}: {error}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def record_scan_result(
        self, group_url: str, opportunities_found_list: List[Any]
    ) -> Dict[str, Any]:
        """Updates group statistics after a scan."""
        today_str = datetime.date.today().isoformat()

        valid_opportunities = 0
        for opp in opportunities_found_list:
            quality = None
            if isinstance(opp, str):
                quality = opp
            elif isinstance(opp, dict):
                quality = opp.get("quality")
                if not quality and isinstance(opp.get("opportunity_analysis"), dict):
                    quality = opp["opportunity_analysis"].get("quality")

            if quality in SAVE_QUALITY_LEVELS:
                valid_opportunities += 1

        group_data = self.stats.get(
            group_url,
            {
                "last_strong_possible_date": None,
                "total_opportunities_found": 0,
                "last_scanned_date": None,
                "consecutive_empty_scans": 0,
            },
        )

        group_data["last_scanned_date"] = today_str

        if valid_opportunities > 0:
            group_data["last_strong_possible_date"] = today_str
            group_data["consecutive_empty_scans"] = 0
            group_data["total_opportunities_found"] += valid_opportunities
        else:
            group_data["consecutive_empty_scans"] += 1

        self.stats[group_url] = group_data
        self._save_stats()
        return group_data

    def prune_inactive_groups(self) -> List[str]:
        """Checks active groups and moves dead ones (no opportunity in 14+ days) to inactive list."""
        today = datetime.date.today()
        active_urls = load_group_urls(self.group_list_file, log=False)
        pruned_groups: List[str] = []

        for group_url in active_urls:
            group_data = self.stats.get(group_url)
            if not group_data or not group_data.get("last_scanned_date"):
                continue

            last_opp_str = group_data.get("last_strong_possible_date")
            is_dead = False

            if not last_opp_str:
                is_dead = True
            else:
                try:
                    last_opp_date = datetime.date.fromisoformat(last_opp_str)
                    days_diff = (today - last_opp_date).days
                    if days_diff > self.max_inactive_days:
                        is_dead = True
                except ValueError:
                    is_dead = True

            if is_dead:
                moved = move_group_to_inactive(
                    group_url,
                    group_list_file=self.group_list_file,
                    inactive_groups_file=self.inactive_groups_file,
                )
                if moved:
                    print(
                        f"[LIFECYCLE] Group {group_url} hasn't produced opportunities "
                        f"in {self.max_inactive_days}+ days. Moved to inactive."
                    )
                    pruned_groups.append(group_url)

        return pruned_groups

    def on_group_scanned(
        self, group_url: str, opportunities: List[Any]
    ) -> Dict[str, Any]:
        """Integration helper to record scan result and prune inactive groups."""
        stats = self.record_scan_result(group_url, opportunities)
        self.prune_inactive_groups()
        return stats
