from selenium import webdriver
from selenium.webdriver.common.by import By
import pyautogui
import time

# optional: small delay and failsafe for pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# Start driver (make sure to run non-headless)
driver = webdriver.Chrome()
driver.get("https://facebook.com")
time.sleep(5)  # wait for page load/login if needed

# Example: find first login button or any clickable element
element = driver.find_element(By.NAME, "login")

# Scroll into view
driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)

# Compute SCREEN coordinates of element center
rect = driver.execute_script("""
    const el = arguments[0];
    const r = el.getBoundingClientRect();
    const centerX = r.left + (r.width / 2);
    const centerY = r.top  + (r.height / 2);

    // Account for browser window offsets
    const chromeTop = window.outerHeight - window.innerHeight;
    const screenX = (window.screenX !== undefined ? window.screenX : screen.left);
    const screenY = (window.screenY !== undefined ? window.screenY : screen.top);

    return {
      x: Math.round(screenX + centerX),
      y: Math.round(screenY + chromeTop + centerY)
    };
""", element)

# Move mouse to element and click with pyautogui
print(f"Moving mouse to {rect['x']}, {rect['y']}")
pyautogui.moveTo(rect["x"], rect["y"], duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()
print("Clicked element with real mouse!")
