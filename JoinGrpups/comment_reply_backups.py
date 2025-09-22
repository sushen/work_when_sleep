from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import pyautogui
from pathlib import Path
import random

from driver.driver import Driver
from login.login import Login

# Simple set of reply lines
LINES = [
    "Great point!",
    "Thanks for sharing!",
    "Interesting thought.",
    "Well said!",
]

GROUPS_FILE = "groups_list.txt"
GROUP_LOAD_WAIT = 20
LIKE_COUNT = 3

def human_hover(element, duration=0.8):
    """
    Move the real mouse pointer gradually to the center of a Selenium element
    using pyautogui.
    """
    location = element.location_once_scrolled_into_view
    size = element.size
    # Calculate the center of the element in screen coords
    center_x = location['x'] + size['width'] / 2
    center_y = location['y'] + size['height'] / 2

    # Move mouse smoothly to that spot
    pyautogui.moveTo(center_x, center_y, duration=duration, tween=pyautogui.easeInOutQuad)

def load_group_urls(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def like_and_reply(driver, count=3):
    posts = driver.find_elements(By.XPATH, '//div[@role="article"]')
    if not posts:
        print("No posts found.")
        return

    liked = 0
    for post in posts:
        if liked >= count:
            break

        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post)
            time.sleep(1)

            # Like button
            like_btn = post.find_element(
                By.XPATH,
                './/*[@role="button" and contains(@aria-label,"Like")]'
            )
            # human_hover(like_btn)
            like_btn.click()
            print("Liked a post.")

            # Reply to first comment
            reply_btn = post.find_element(
                By.XPATH,
                './/*[@role="button" and (contains(text(),"Reply") or @aria-label="Reply")]'
            )
            reply_btn.click()
            time.sleep(0.5)

            editor = driver.find_element(By.XPATH, '//div[@role="textbox" and @contenteditable="true"]')
            editor.send_keys(random.choice(LINES))
            print(input("Review Comment :"))
            editor.send_keys(Keys.ENTER)
            print("Replied to a comment.")

            liked += 1
            time.sleep(2)

        except Exception as e:
            print(f"Skipped a post due to error: {e}")


if __name__ == "__main__":
    driver = Driver().driver
    driver.get("https://facebook.com")
    Login().login(driver)

    groups = load_group_urls(GROUPS_FILE)
    for i, url in enumerate(groups, start=1):
        print(f"[{i}/{len(groups)}] Visiting {url}")
        driver.get(url)
        time.sleep(3)
        like_and_reply(driver, count=LIKE_COUNT)

    print("All groups processed.")
