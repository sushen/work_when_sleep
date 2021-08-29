from Bots.bot_base import BaseBot
from Config.bot_config import BotData
from Pages.LoginPage import LoginPage


class Bot_Login(BaseBot):
    def test_login(self):
        self.loginPage = LoginPage(self.driver)
        self.loginPage.do_login(BotData.USER_NAME, BotData.PASSWORD)







