import pyautogui
import time

# try:
#     while True:
#         x, y = pyautogui.position()
#         print(f"Mouse position: X={x}, Y={y}", end="\r")
# except KeyboardInterrupt:
#     print("\nStopped.")
#
# print(input("Stop:"))

pyautogui.moveTo(x=128,y=326, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)

pyautogui.moveTo(x=261,y=377, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=137,y=554, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=200,y=420, duration=0.8, tween=pyautogui.easeInOutQuad)
# pyautogui.click()

time.sleep(.5)
pyautogui.scroll(-500)

time.sleep(.5)
pyautogui.moveTo(x=124,y=355, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=124,y=625, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(5.)
pyautogui.moveTo(x=124,y=595, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=124,y=705, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=124,y=327, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.moveTo(x=700,y=600, duration=0.8, tween=pyautogui.easeInOutQuad)
time.sleep(.5)
pyautogui.click()
pyautogui.scroll(-500)

time.sleep(.5)
pyautogui.moveTo(x=124,y=365, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

pyautogui.moveTo(x=124,y=500, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

time.sleep(.5)
pyautogui.click()
pyautogui.hotkey('ctrl', 'v')

time.sleep(.5)
pyautogui.moveTo(x=500,y=550, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()
pyautogui.scroll(-500)

pyautogui.moveTo(x=500,y=550, duration=0.8, tween=pyautogui.easeInOutQuad)
pyautogui.click()

