# Find_groups.py
# Thin CLI wrapper that imports the class-based finder and runs it safely.

import argparse
from pathlib import Path

from keywords import KEYWORDS                    # your separated keyword map
from fb_groups_finder import FBGroupFinder       # the class you posted

def _split_tokens(csv: str):
    return [t.strip() for t in (csv or "").split(",") if t.strip()]

def main():
    ap = argparse.ArgumentParser(
        description="Run Facebook group discovery using pre-filtering and link saving."
    )
    ap.add_argument("--countries", nargs="*", default=[], help="Default: all countries in KEYWORDS")
    ap.add_argument("--categories", nargs="*", default=[], choices=["exchange", "multi_asset", "dev_algo"])
    ap.add_argument("--limit", type=int, default=30, help="Max keyword searches to perform")
    ap.add_argument("--sleep", type=float, default=2.0, help="Seconds between keyword searches")
    ap.add_argument("--min-members", type=int, default=1000, help="Minimum members to accept")
    ap.add_argument("--exclude-name", type=str, default="Bangladesh,BD,Bangladeshi", help="Comma-separated tokens to exclude in name")
    ap.add_argument("--open-tabs", action="store_true", help="Open accepted groups in new tabs")
    ap.add_argument("--output", type=str, default="groups_list.txt", help="Append accepted links here")
    ap.add_argument("--max-results-per-search", type=int, default=30, help="Max scraped cards per search")
    ap.add_argument("--wait-seconds", type=int, default=12, help="Explicit wait seconds for page elements")

    args = ap.parse_args()

    countries = args.countries or list(KEYWORDS.keys())
    exclude_tokens = _split_tokens(args.exclude_name)

    finder = FBGroupFinder(
        min_members=args.min_members,
        exclude_tokens=exclude_tokens,
        open_tabs=args.open_tabs,
        output_file=args.output,
        max_results_per_search=args.max_results_per_search,
        search_sleep=args.sleep,
        wait_seconds=args.wait_seconds,
    )

    print(f"[INFO] Countries={countries}")
    print(f"[INFO] Categories={args.categories or 'ALL'}")
    print(f"[INFO] Filters: min_members={args.min_members}, exclude={exclude_tokens}")
    print(f"[INFO] Output: {Path(args.output).resolve()} | Open tabs: {args.open_tabs}")

    try:
        finder.login()
        finder.run(
            countries=countries,
            categories=args.categories,
            keyword_limit=args.limit,
        )
    except KeyboardInterrupt:
        print("\n[EXIT] Interrupted by user.")
    finally:
        # Always close the browser to avoid zombie processes
        try:
            finder.driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()
