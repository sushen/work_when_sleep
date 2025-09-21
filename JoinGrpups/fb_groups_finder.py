# fb_groups_finder.py
# Class-based Facebook Group finder:
#  - login once (uses your driver/login wrappers)
#  - search by country keywords (from keywords.py)
#  - scrape search results (name, members, url)
#  - filter by min members & excluded tokens in name
#  - optionally open accepted groups in tabs
#  - append accepted links to a text file

import time
import re
from pathlib import Path
from urllib.parse import quote_plus
from typing import Iterable, Optional, Sequence

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from driver.driver import Driver
from login.login import Login
from keywords import KEYWORDS  # your separated keyword map

class FBGroupFinder:
    def __init__(
        self,
        min_members: int = 1000,
        exclude_tokens: Optional[Sequence[str]] = None,
        open_tabs: bool = False,
        output_file: str = "groups_list.txt",
        max_results_per_search: int = 30,
        search_sleep: float = 2.0,
        wait_seconds: int = 12,
    ):
        self.min_members = min_members
        self.exclude_tokens = [t.strip().lower() for t in (exclude_tokens or ["Bangladesh", "BD", "Bangladeshi"]) if t.strip()]
        self.open_tabs = open_tabs
        self.output_path = Path(output_file)
        self.max_results_per_search = max_results_per_search
        self.search_sleep = search_sleep
        self.wait_seconds = wait_seconds

        self.driver = Driver().driver
        self.wait = WebDriverWait(self.driver, self.wait_seconds)

    # ---------- Public API ----------
    def login(self):
        self.driver.get("https://facebook.com")
        Login().login(self.driver)
        time.sleep(3)

    def run(
        self,
        countries: Iterable[str],
        categories: Optional[Iterable[str]] = None,
        keyword_limit: int = 30,
    ):
        categories = set(categories) if categories else None
        accepted_total = 0
        processed_kw = 0

        for country, cat, kw in self._iter_queries(countries, categories):
            if processed_kw >= keyword_limit:
                break

            url = self._search_url(kw)
            print(f"\n[SEARCH] {country} | {cat} | {kw} -> {url}")
            self.driver.get(url)

            try:
                groups = self._scrape_groups_from_search(self.max_results_per_search)
            except Exception as e:
                print(f"[WARN] scrape failed for '{kw}': {e}")
                groups = []

            accepted = [g for g in groups if self._accept_group(g["name"], g["members"])]
            print(f"[INFO] Results {len(groups)} | Accepted {len(accepted)}")

            links = [g["url"] for g in accepted]
            if links:
                self._save_links(links)
                accepted_total += len(links)

            if self.open_tabs:
                for link in links:
                    self.driver.execute_script(f"window.open('{link}', '_blank');")
                    time.sleep(0.6)

            processed_kw += 1
            time.sleep(self.search_sleep)
            print(input("Next Group :"))

        print(f"\n[DONE] Processed {processed_kw} keyword searches. Accepted links total: {accepted_total}")

    # ---------- Internals ----------
    @staticmethod
    def _search_url(query: str) -> str:
        return f"https://www.facebook.com/search/groups/?q={quote_plus(query)}"

    @staticmethod
    def _iter_queries(countries: Iterable[str], include_categories: Optional[set]):
        for country in countries:
            items = KEYWORDS.get(country, {})
            for cat, kws in items.items():
                if include_categories and cat not in include_categories:
                    continue
                for kw in kws:
                    yield country, cat, kw

    @staticmethod
    def _parse_member_count(text: str) -> int:
        # Accepts: '1,234 members', '12K members', '1.2M Members', etc.
        if not text:
            return 0
        t = text.strip().lower().replace(",", "")
        m = re.search(r"([\d\.]+)\s*([km])?\s*member", t)
        if not m:
            m2 = re.search(r"(\d+)", t)
            return int(m2.group(1)) if m2 else 0
        num = float(m.group(1))
        suf = m.group(2)
        if suf == "k":
            num *= 1_000
        elif suf == "m":
            num *= 1_000_000
        return int(num)

    def _accept_group(self, name: str, members: int) -> bool:
        if members < self.min_members:
            return False
        n = name.lower()
        if any(tok in n for tok in self.exclude_tokens):
            return False
        return True

    def _save_links(self, links):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as f:
            for link in links:
                f.write(link.rstrip() + "\n")
        print(f"[SAVE] {len(links)} links -> {self.output_path.resolve()}")

    def _scrape_groups_from_search(self, max_results: int = 30, scroll_pause: float = 1.2):
        """
        Scrapes current search page into: [{name, members, url}, ...]
        """
        driver, wait = self.driver, self.wait
        results, seen = [], set()

        def collect():
            # FB DOM changes; selectors are intentionally broad
            cards = driver.find_elements(By.CSS_SELECTOR, "div[role='article'], div.x1y1aw1k")
            for card in cards:
                try:
                    link_el = card.find_element(By.CSS_SELECTOR, "a[role='link'][href*='/groups/']")
                    url = link_el.get_attribute("href")
                    name = link_el.text.strip()
                    member_text = ""
                    info_candidates = card.find_elements(
                        By.XPATH, ".//*[contains(translate(text(),'MEMBER','member'),'member')]"
                    )
                    for c in info_candidates:
                        t = c.text.strip()
                        if "member" in t.lower():
                            member_text = t
                            break
                    members = self._parse_member_count(member_text)
                    key = (url, name)
                    if key not in seen and name and url:
                        seen.add(key)
                        results.append({"name": name, "members": members, "url": url})
                except Exception:
                    continue

        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']")))
        except TimeoutException:
            pass

        last_height = 0
        collect()
        while len(results) < max_results:
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            collect()
            new_height = driver.execute_script("return document.body.scrollHeight;")
            if new_height == last_height:
                break
            last_height = new_height

        return results[:max_results]
