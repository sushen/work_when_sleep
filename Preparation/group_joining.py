import sqlite3

from Bots.bot_LoginPage import Bot_Login
from Bots.bot_base import BaseBot
from Pages.LoginPage import LoginPage

login = Bot_Login()
fb_login = login.test_login()


connection = sqlite3.connect('../DatabaseCreation/wws.db')
cursor = connection.cursor()

cursor.execute("SELECT profile_link, oid FROM facebook_profile")
records = cursor.fetchall()
# print(records)

index_record = []
for profile_link in records:
    index_record.append(profile_link)
    single_record = str(records[len(index_record)-1])
    print(single_record)

    # I need to solve it
    login.driver.get("https://meet.google.com/")
    # BaseBot.self(profile_link)

connection.commit()
connection.close()
