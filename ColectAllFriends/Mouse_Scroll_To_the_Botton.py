import pyautogui
import time

while True:
    time.sleep(10)  # Gives you 2 seconds to move your mouse to the right position
    # pyautogui.hscroll(200)   # Scroll right
    pyautogui.hscroll(-200)  # Scroll left
    pyautogui.hscroll(-200)  # Scroll left
    pyautogui.hscroll(-200)  # Scroll left
    pyautogui.hscroll(-200)  # Scroll left

