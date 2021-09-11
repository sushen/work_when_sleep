# TODO: 1. we need to go youtube

from selenium import webdriver
driver = webdriver.Chrome("chromedriver.exe")
driver.get("https://www.youtube.com/")

# TODO: 2. we need to sign in
# Learning Carv Xpath https://youtube.com/playlist?list=PLmRg3gEG2XIackdOpGvb_jEX1ywaplUmh
button_xpath = "//tp-yt-paper-button[@aria-label='Sign in']"
login_button = driver.find_elements_by_xpath(button_xpath)
login_button[0].click()
print(len(login_button))

# TODO: 3. we need to subscribe
# TODO: 4. we need to repeat that things 1000 times
