from selenium.webdriver.common.by import By

import time
from pathlib import Path

from driver.driver import Driver
from login.login import Login


driver = Driver().driver
driver.get("https://facebook.com")

Login().login(driver)


# print(input("Load All Recent Friend:"))

GROUPS_FILE = "groups_list.txt"
PAUSE_BETWEEN = 20  # seconds between opening groups

def load_group_urls(path: str | Path) -> list[str]:
    """Read all group URLs from the text file."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


groups = load_group_urls(GROUPS_FILE)
print(f"Loaded {len(groups)} groups from {GROUPS_FILE}")

for i, url in enumerate(groups, start=1):
    print(f"[{i}/{len(groups)}] Visiting {url}")
    driver.get(url)
    # let page load
    time.sleep(PAUSE_BETWEEN)
    # print(input("Next Groups :"))