# TODO: 1. we need to go youtube
import time

from selenium import webdriver
driver = webdriver.Chrome("chromedriver.exe")
driver.get("https://www.youtube.com/")


def add_youtube_subscriber(username, password):
    button_xpath = "//tp-yt-paper-button[@aria-label='Sign in']"
    login_button = driver.find_elements_by_xpath(button_xpath)
    login_button[0].click()
    print(len(login_button))
    time.sleep(4)

    driver.implicitly_wait(10)
    # driver.get('https://accounts.google.com/')
    password_xpath = "//input[@type='email']"
    driver.find_element_by_xpath(password_xpath).send_keys(username)

    next_button_xpath = "//span[contains(.,'Next')]/parent::button"
    next_button = driver.find_element_by_xpath(next_button_xpath)
    next_button.click()
    print(next_button.text)
    time.sleep(4)

    driver.implicitly_wait(10)
    password_xpath = "//input[@type='password']"
    driver.find_element_by_xpath(password_xpath).send_keys(password)
    driver.find_element_by_xpath(next_button_xpath).click()

    driver.implicitly_wait(10)
    driver.get("https://www.youtube.com/channel/UCsxGaMtknRcf73_lAd3_dYA")
    subscriber_xpath = "//div[@id='subscribe-button']"
    subscriber = driver.find_element_by_xpath(subscriber_xpath)
    print(subscriber.text)
    subscriber.click()

    subscriber_signing_xpath = "//ytd-button-renderer[@id='button']//tp-yt-paper-button[@id='button']"
    subscriber_signing = driver.find_element_by_xpath(subscriber_signing_xpath)
    print(subscriber_signing.text)
    subscriber_signing.click()

    driver.implicitly_wait(10)
    subscriber_xpath_reassign = "//div[@id='subscribe-button']"
    subscriber_reassign = driver.find_element_by_xpath(subscriber_xpath_reassign)
    subscriber_reassign.click()

    driver.quit()


# TODO: 4. we need to repeat that things 1000 times
add_youtube_subscriber("", "")
