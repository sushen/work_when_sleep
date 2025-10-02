from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
import time
import pyautogui
import pyttsx3
from pathlib import Path
import random

from driver.driver import Driver
from login.login import Login

# ---------- Config ----------
LINES = [
    "Wisdom thrives where voices meet.",
    "Conversations weave pathways of wisdom.",
    "When minds connect, wisdom awakens.",
    "Connection is the soil where wisdom grows.",
    "Shared words, deeper wisdom.",
    "Dialogue blossoms into wisdom.",
    "Connection is the echo of wisdom.",
    "Wisdom is born in genuine exchange.",
    "Minds linked, wisdom multiplied.",
    "Connection turns dialogue into insight.",
    "Every bridge of words carries wisdom.",
    "Wisdom is the bridge between hearts.",
    "Conversations link wisdom to connection.",
    "Where voices bridge, wisdom flows.",
    "Dialogue is the thread weaving wisdom.",
    "Wisdom bridges the gap between minds.",
    "Connected thought builds bridges of wisdom.",
    "Every connection strengthens wisdom.",
    "Conversations are the bridges of insight.",
    "Shared wisdom creates lasting links.",
    "Wisdom flows along the currents of dialogue.",
    "Conversations carry wisdom like rivers.",
    "Connection channels the energy of wisdom.",
    "Where voices flow together, wisdom shines.",
    "Dialogue sparks the current of wisdom.",
    "Connection fuels the flow of wisdom.",
    "Every conversation is a stream of insight.",
    "Wisdom drifts where connection flows.",
    "Dialogue pours wisdom into the shared space.",
    "Connected words ripple with wisdom.",
    "Wisdom blooms through shared words.",
    "Connection cultivates wisdom.",
    "Conversations grow gardens of wisdom.",
    "The seed of wisdom is planted in dialogue.",
    "Wisdom grows where minds connect.",
    "Dialogue is fertile ground for wisdom.",
    "Connected voices nurture wisdom.",
    "Conversations blossom into wisdom’s fruit.",
    "Connection waters the roots of wisdom.",
    "Every shared word is a seed of wisdom.",
    "Wisdom belongs to the voices that gather.",
    "Connection creates a circle of wisdom.",
    "Collective voices give rise to wisdom.",
    "Where we meet, wisdom is made.",
    "Shared dialogue builds wisdom for all.",
    "Wisdom lives in the space between us.",
    "Connection creates wisdom greater than one.",
    "Conversations unite us in shared insight.",
    "Many voices, one wisdom.",
    "Wisdom is the gift of connection.",
    "Dialogue lights the path to wisdom.",
    "Connection sparks wisdom’s flame.",
    "Wisdom shines where words are shared.",
    "Conversations uncover hidden wisdom.",
    "Connection reveals wisdom’s glow.",
    "The light of wisdom emerges from dialogue.",
    "Wisdom illuminates when minds connect.",
    "Conversations spark wisdom like stars.",
    "Connection is the lantern of wisdom.",
    "Wisdom is discovered in shared stories.",
    "Dialogue is the harmony of wisdom.",
    "Connection composes the song of wisdom.",
    "Wisdom resonates through conversation.",
    "Every connected voice is part of wisdom’s chorus.",
    "Dialogue creates the rhythm of wisdom.",
    "Connection makes wisdom sing.",
    "Wisdom hums where words unite.",
    "Conversations orchestrate wisdom.",
    "Connected voices form wisdom’s melody.",
    "Wisdom dances in the rhythm of dialogue.",
    "Conversations are maps to wisdom.",
    "Wisdom is the journey we walk together.",
    "Dialogue is the compass of wisdom.",
    "Connection charts the course to wisdom.",
    "Shared voices guide the way to wisdom.",
    "Wisdom unfolds in the journey of conversation.",
    "Dialogue explores the depths of wisdom.",
    "Connection discovers wisdom in new places.",
    "Conversations open paths of insight.",
    "Wisdom is found along connected journeys.",
    "Wisdom empowers connection.",
    "Dialogue is strength shared.",
    "Connected voices create powerful wisdom.",
    "Wisdom fuels the power of dialogue.",
    "Connection multiplies wisdom’s force.",
    "Dialogue is the spark of collective power.",
    "Wisdom strengthens when shared.",
    "Connection turns words into force.",
    "Wisdom is power rooted in conversation.",
    "Shared voices amplify wisdom’s strength.",
    "Conversations open galaxies of wisdom.",
    "Connection unlocks the mystery of wisdom.",
    "Wisdom is the constellation of shared thoughts.",
    "Dialogue is the universe of connection.",
    "Wisdom expands where voices meet.",
    "Connection is the horizon of wisdom.",
    "Conversations are stars in the sky of wisdom.",
    "Wisdom stretches beyond words, through connection.",
    "Dialogue opens infinite doors of wisdom.",
    "Connected voices shape the cosmos of wisdom."
]


GROUPS_FILE = "groups_list.txt"
LIKE_COUNT = 2

# Make pyautogui a bit safer/human
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def text_to_speech(text):
    # Initialize the engine
    engine = pyttsx3.init()

    # Optional: set voice properties
    engine.setProperty("rate", 150)   # Speed (words per minute)
    engine.setProperty("volume", 1.0) # Volume (0.0 to 1.0)

    # List available voices (male/female, different accents)
    voices = engine.getProperty("voices")
    # for i, voice in enumerate(voices):
    #     print(f"Voice {i}: {voice.name} ({voice.id})")

    # Choose a voice (e.g., 0 = first, 1 = second)
    engine.setProperty("voice", voices[0].id)

    # Speak the text
    engine.say(text)
    engine.runAndWait()

# ---------- Helpers ----------
def load_group_urls(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_screen_center(driver, element):
    """
    Return (x, y) screen coordinates of an element's center.
    Uses JS to translate viewport coords -> screen coords.
    """
    return driver.execute_script("""
        const el = arguments[0];
        const r = el.getBoundingClientRect();
        const centerX = r.left + (r.width / 2);
        const centerY = r.top  + (r.height / 2);

        // Translate viewport -> screen coordinates
        const chromeTop = window.outerHeight - window.innerHeight;
        const screenX = (window.screenX !== undefined ? window.screenX : screen.left);
        const screenY = (window.screenY !== undefined ? window.screenY : screen.top);

        return {
          x: Math.round(screenX + centerX),
          y: Math.round(screenY + chromeTop + centerY)
        };
    """, element)


def human_click(driver, element, move_duration=0.7):
    """
    Human-like click: scroll into view, compute screen coords, move real mouse, click.
    Falls back to Selenium click if anything fails.
    """
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        pt = get_screen_center(driver, element)
        pyautogui.moveTo(pt["x"], pt["y"], duration=move_duration, tween=pyautogui.easeInOutQuad)
        pyautogui.click()
        time.sleep(0.2)
        return True
    except Exception as e:
        print(f"[human_click] pyautogui path failed ({e}); falling back to Selenium click.")
        try:
            element.click()
            time.sleep(0.2)
            return True
        except Exception as e2:
            print(f"[human_click] Selenium click also failed: {e2}")
            return False


def find_like_button(post):
    """
    Try several robust selectors for an *unpressed* Like control within a post.
    Returns the first visible WebElement or raises NoSuchElementException.
    """
    xpaths = [
        # Case-insensitive aria-label contains 'like' and not pressed
        './/*[@role="button" and contains(translate(@aria-label,"LIKE","like"),"like") and not(@aria-pressed="true")]',
        # Text node 'Like' (visible label) -> climb to button ancestor
        './/span[normalize-space()="Like"]/ancestor::*[@role="button" and not(@aria-pressed="true")]',
        # SVG icon labelled Like inside a button (newer UIs)
        './/*[@role="button" and not(@aria-pressed="true")]//*[name()="svg" and @aria-label="Like"]/ancestor::*[@role="button"][1]',
        # Fallback: any visible button whose accessible name includes Like
        './/*[@role="button" and (contains(normalize-space(.),"Like") or contains(@aria-label,"Like")) and not(@aria-pressed="true")]',
    ]

    for xp in xpaths:
        try:
            candidates = post.find_elements(By.XPATH, xp)
            for el in candidates:
                if el.is_displayed():
                    return el
        except Exception:
            continue

    raise NoSuchElementException("Like button not found in this post")


def find_reply_button(post):
    """
    Robust 'Reply' finder under a post (first visible).
    """
    xpaths = [
        './/*[@role="button" and (contains(translate(@aria-label,"REPLY","reply"),"reply"))]',
        './/span[normalize-space()="Reply"]/ancestor::*[@role="button"]',
        './/*[@role="button" and contains(normalize-space(.),"Reply")]',
    ]
    for xp in xpaths:
        try:
            candidates = post.find_elements(By.XPATH, xp)
            for el in candidates:
                if el.is_displayed():
                    return el
        except Exception:
            continue
    raise NoSuchElementException("Reply button not found in this post")


# ---------- Core flow ----------
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
            time.sleep(random.uniform(0.6, 1.1))  # small human-ish wait

            # --- Like (try; but if not found, still proceed to Reply) ---
            try:
                like_btn = find_like_button(post)
                if human_click(driver, like_btn):
                    print("Liked a post.")
                else:
                    print("Like: human_click fallback failed; will still attempt Reply.")
            except NoSuchElementException:
                print("Like button not found on this post; proceeding to Reply.")

            # --- Reply (required) ---
            reply_btn = find_reply_button(post)
            if not human_click(driver, reply_btn):
                print("Could not click Reply; skipping this post.")
                continue

            time.sleep(2)

            # --- Type reply (you keep your review pause) ---
            editor = driver.find_element(By.XPATH, '//div[@role="textbox" and @contenteditable="true"]')
            reply_comment = random.choice(LINES)
            print(f"Comment :{reply_comment}")
            editor.send_keys(reply_comment)
            review_comment_text = "Review Comment :"
            text_to_speech(review_comment_text)
            print(input(review_comment_text))
            # time.sleep(4)
            # editor.send_keys(Keys.ENTER)
            # time.sleep(4)
            print("Replied to a comment.")

            liked += 1
            time.sleep(4)

        except Exception as e:
            # text_to_speech(e)
            print(f"Skipped a post due to error: {e}")


    print(f"Finished this group: liked {liked} post(s).")


# ---------- Main ----------
if __name__ == "__main__":
    # IMPORTANT: run non-headless and keep the browser visible/foregrounded
    driver = Driver().driver
    driver.get("https://facebook.com")
    Login().login(driver)

    groups = load_group_urls(GROUPS_FILE)
    for i, url in enumerate(groups, start=1):
        next_group_text = "Next Groups:"
        text_to_speech(next_group_text)
        # print(input(next_group_text))
        time.sleep(4)
        print(f"[{i}/{len(groups)}] Visiting {url}")
        driver.get(url)
        time.sleep(4)
        like_and_reply(driver, count=LIKE_COUNT)

    all_processed = "All groups processed."
    print(all_processed)
    text_to_speech(all_processed)
