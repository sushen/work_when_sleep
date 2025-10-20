from selenium.webdriver.common.by import By

import time
from pathlib import Path

import pyttsx3

from driver.driver import Driver
from login.login import Login


driver = Driver().driver
driver.get("https://facebook.com")

Login().login(driver)


# print(input("Load All Recent Friend:"))

GROUPS_FILE = "programmers_groups.txt"
PAUSE_BETWEEN = 20  # seconds between opening groups

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
    engine.runAndWait()

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
    text_to_speech("Next Groups")
    print(input("Next Groups :"))


all_processed = "All groups processed."
print(all_processed)
text_to_speech(all_processed)