"""Page Object Model class for Facebook Group Search page interactions."""

from __future__ import annotations

import time
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from Pages.BasePage import BasePage
from search_interested.facebook_dom import (
    extract_author,
    extract_content_text,
    extract_content_type,
    extract_content_url,
    extract_timestamp,
    find_post_containers,
    scroll_down,
    wait_for_posts,
)
from search_interested.facebook_urls import clean_facebook_url
from search_interested.settings import (
    MAX_SCROLLS_PER_GOETHE_SEARCH,
    POST_CONTAINER_XPATHS,
    POST_WAIT_XPATH,
    SCROLL_PAUSE_SECONDS,
    WAIT_SECONDS,
)


class FacebookGroupSearchPage(BasePage):
    """Page Object for Facebook Group internal search."""

    SEARCH_INPUT = (By.XPATH, "//input[@aria-label='Search this group' or @placeholder='Search this group' or @aria-label='Search group' or @placeholder='Search group']")
    RESULTS_CONTAINER = (By.XPATH, POST_WAIT_XPATH)

    def __init__(self, driver):
        super().__init__(driver)

    def navigate_to_group(self, group_url: str) -> None:
        """Navigate to group main page."""
        self.driver.get(group_url)
        time.sleep(2)

    def navigate_to_group_search(self, group_url: str, query: str) -> None:
        """Navigate directly to group search URL for given query."""
        clean_url = group_url.rstrip("/")
        encoded_query = quote(query)
        search_url = f"{clean_url}/search/?q={encoded_query}"
        self.driver.get(search_url)

    def enter_search_query(self, query: str) -> None:
        """Enter search query into group search box if visible."""
        try:
            search_box = WebDriverWait(self.driver, WAIT_SECONDS).until(
                EC.visibility_of_element_located(self.SEARCH_INPUT)
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.ENTER)
        except Exception as error:
            print(f"[POM] Could not enter query in search box: {error}")

    def wait_for_results(self, timeout: int = WAIT_SECONDS) -> bool:
        """Wait for post elements or search result containers to appear."""
        return wait_for_posts(self.driver, timeout=timeout)

    def get_visible_post_elements(self) -> list:
        """Retrieve visible post container elements."""
        return find_post_containers(self.driver)

    def scroll_results(self, scroll_count: int = 1) -> None:
        """Scroll down to load additional search results."""
        for _ in range(scroll_count):
            scroll_down(self.driver)
            time.sleep(SCROLL_PAUSE_SECONDS)

    def extract_post_data(
        self,
        element,
        query: str = "",
        group_name: str = "",
        group_url: str = "",
    ) -> dict | None:
        """Extract structured dictionary from single post DOM element."""
        try:
            content_type = extract_content_type(element)
            author = extract_author(element)
            text = extract_content_text(element, content_type, author=author)

            if not text:
                return None

            content_url = extract_content_url(element, content_type)
            timestamp_info = extract_timestamp(element, content_type)

            post_url = clean_facebook_url(content_url) if content_url else ""

            return {
                "source": "facebook",
                "source_type": "goethe_group",
                "group_name": group_name,
                "group_url": group_url,
                "search_interest": query,
                "query": query,
                "author": author,
                "content_text": text,
                "content_url": post_url or group_url,
                "post_url": post_url,
                "content_type": content_type,
                "timestamp_info": timestamp_info,
            }
        except Exception as error:
            print(f"[POM] Error extracting post data from element: {error}")
            return None

    def recover_from_failure(self, group_url: str) -> None:
        """Attempt page reload or recovery after failure."""
        try:
            self.driver.get(group_url)
            time.sleep(3)
        except Exception as error:
            print(f"[POM] Recovery failed: {error}")
