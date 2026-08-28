import pathlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
scriptDirectory = pathlib.Path().absolute()

chrome_options.add_argument("--start-maximized")
# Comment these out to test:
# chrome_options.add_argument("--user-data-dir=chrome-data")
# chrome_options.add_argument(f"--user-data-dir={scriptDirectory}\\userdata")
# chrome_options.add_argument('--profile-directory=Default')

prefs = {"profile.default_content_setting_values.notifications": 2}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument('--disable-infobars')
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

class BaseBot:
    def __init__(self):
        self.driver = webdriver.Chrome(options=chrome_options)