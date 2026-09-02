"""Continuous discovery scanner for Reddit service/business opportunities."""

from __future__ import annotations

import time

from .opportunity_engine import analyze_opportunity, is_fresh_opportunity_timestamp
from .reddit_client import RedditClient
from .reddit_parser import normalize_reddit_post
from .reddit_query_queue import RedditQueryQueue
from .results import (
    alert_opportunity,
    build_opportunity,
    display_opportunity,
    load_seen_opportunity_keys,
    save_opportunity,
)
from .settings import (
    REDDIT_MAX_OPPORTUNITY_AGE_SECONDS,
    REDDIT_MAX_RESULTS_PER_QUERY,
    REDDIT_POLL_INTERVAL_SECONDS,
)
from .text_utils import print_running_time


class RedditScanner:
    """Orchestrates query rotation, fetching, normalization, opportunity scoring, alerting, and persistence."""

    def __init__(
        self,
        client: RedditClient | None = None,
        query_queue: RedditQueryQueue | None = None,
        poll_interval: int = REDDIT_POLL_INTERVAL_SECONDS,
        max_age_seconds: int = REDDIT_MAX_OPPORTUNITY_AGE_SECONDS,
    ):
        self.client = client or RedditClient()
        self.query_queue = query_queue or RedditQueryQueue()
        self.poll_interval = poll_interval
        self.max_age_seconds = max_age_seconds
        self.seen_keys = load_seen_opportunity_keys()

    def process_query(self, query: str) -> list[dict]:
        """Run single search query against Reddit, parse items through shared opportunity engine."""
        print(f"[REDDIT] Query: '{query}'")
        raw_posts = self.client.search_newest(query, limit=REDDIT_MAX_RESULTS_PER_QUERY)
        print(f"[REDDIT] Results: {len(raw_posts)} posts retrieved")

        discovered_opportunities = []
        new_count = 0
        duplicate_count = 0
        old_count = 0
        unknown_time_count = 0
        weak_count = 0
        possible_count = 0
        strong_count = 0

        for raw_post in raw_posts:
            detected_at = time.time()
            normalized = normalize_reddit_post(raw_post, query=query, detected_at=detected_at)
            opportunity_key = normalized["timestamp_info"] and f"reddit:{normalized['post_id']}" or normalized["content_url"]

            if opportunity_key in self.seen_keys:
                duplicate_count += 1
                continue

            self.seen_keys.add(opportunity_key)
            new_count += 1

            timestamp_info = normalized["timestamp_info"]
            if not is_fresh_opportunity_timestamp(timestamp_info):
                if timestamp_info["freshness"] == "UNKNOWN":
                    unknown_time_count += 1
                    print(f"[REDDIT] Unknown timestamp for post {normalized['post_id']}; skipping.")
                else:
                    old_count += 1
                    print(
                        f"[REDDIT] Old post ({timestamp_info['freshness']}) "
                        f"age={timestamp_info['age_seconds']}s; skipping."
                    )
                continue

            if (
                timestamp_info["age_seconds"] is not None
                and timestamp_info["age_seconds"] > self.max_age_seconds
            ):
                old_count += 1
                continue

            opportunity_analysis = analyze_opportunity(normalized["content_text"])
            quality = opportunity_analysis["quality"]

            if quality == "WEAK":
                weak_count += 1
                continue
            elif quality == "POSSIBLE":
                possible_count += 1
            elif quality == "STRONG":
                strong_count += 1

            opportunity = build_opportunity(
                group_name=normalized["community_name"],
                group_url=normalized["source_url"],
                content_type="POST",
                author=normalized["author"],
                content_text=normalized["content_text"],
                content_url=normalized["content_url"],
                timestamp_info=timestamp_info,
                opportunity_analysis=opportunity_analysis,
                opportunity_key=opportunity_key,
                source="reddit",
                subreddit=normalized["subreddit"],
                title=normalized["title"],
                detection_latency_seconds=normalized["detection_latency_seconds"],
                query=query,
                post_id=normalized["post_id"],
            )

            save_opportunity(opportunity)
            alert_opportunity(opportunity)
            display_opportunity(opportunity)
            discovered_opportunities.append(opportunity)

        print(
            f"[REDDIT] Query summary -> "
            f"New: {new_count}, Dup: {duplicate_count}, Old: {old_count}, "
            f"UnknownTime: {unknown_time_count}, Weak: {weak_count}, "
            f"Possible: {possible_count}, Strong: {strong_count}"
        )
        return discovered_opportunities

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous scanning loop over active query queue."""
        if start_time is None:
            start_time = time.time()

        print("[REDDIT] Continuous scanner started")

        while True:
            query = self.query_queue.get_next_query()
            if not query:
                print("[REDDIT] No queries available in queue. Waiting 30s...")
                time.sleep(30)
                continue

            try:
                self.process_query(query)
                self.query_queue.record_success(query)
            except Exception as error:
                print(f"[REDDIT] Error scanning query '{query}': {error}")
                self.query_queue.record_failure(query)

            print_running_time(start_time)
            print(f"[REDDIT] Waiting {self.poll_interval} seconds before next query...")
            time.sleep(self.poll_interval)


def main():
    scanner = RedditScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[REDDIT] Scanner stopped by user.")


if __name__ == "__main__":
    main()
