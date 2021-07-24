import pytest
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from Config.config import TestData


@pytest.fixture(params=["chrome"], scope="class")
def init_driver(request):
    if request.param == "chrome":
        # web_driver = webdriver.Chrome(executable_path=TestData.CHROME_EXECUTABLE_PATH)
        web_driver = webdriver.Chrome(ChromeDriverManager().install())
    if request.param == "firefox":
        web_driver = webdriver.Chrome(executable_path=TestData.FIREFOX_EXECUTABLE_PATH)
    request.cls.driver = web_driver
    yield
    web_driver.close()






