from selenium.webdriver.common.by import By

from Config.config import TestData
from Pages.BasePage import BasePage


class LoginPage(BasePage):

    """ By Locators - OR """
    EMAIL = (By.ID, "email")
    PASSWORD = (By.ID, "pass")
    LOGIN_BUTTON = (By.XPATH, "//button[normalize-space()='Log In']")
    FORGOTTEN_PASSWORD = (By.LINK_TEXT, "Forgotten password?")

    """ constructor of the page class """
    def __init__(self, driver):
        super().__init__(driver)
        self.driver.get(TestData.BASE_URL)

    """ Page Action for Login Page """
    """ this is used to get the page title """
    def get_login_page_title(self, title):
        return self.get_title(title)

    """ this is used to check Forgotten password? Button Link """
    def is_forgotten_password_button_exist(self):
        return self.is_visible(self.FORGOTTEN_PASSWORD)

    """ this is used to login """
    def do_login(self, username, password):
        self.do_send_keys(self.EMAIL, username)
        self.do_send_keys(self.PASSWORD, password)
        self.do_click(self.LOGIN_BUTTON)
