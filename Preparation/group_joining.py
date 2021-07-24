from Bots.bot_LoginPage import Bot_Login

login = Bot_Login()
fb_login = login.test_login()




for groupLinkList in lines:
    driver.get(groupLinkList)
    print(groupLinkList + " link")
    time.sleep(5)

