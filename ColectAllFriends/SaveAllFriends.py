from selenium.webdriver.common.by import By

import time

from driver.driver import Driver
# from googlesheet.connection import Connection
from login.login import Login


# message = "Today\'s Class start at 10 am. Join \'https://meet.google.com/amj-emzj-siy\' Come early if you need more " \
#           "help. "

# message = "I am available now you guides can join now. https://meet.google.com/amj-emzj-siy"

message = "We held a free class tomorrow 10 a.m. https://meet.google.com/amj-emzj-siy  you are invited. "

print(message)


driver = Driver().driver
driver.get("https://facebook.com")

Login().login(driver)

time.sleep(4)
driver.get("https://www.facebook.com/sushen.biswas/friends_recent")
print(input("Load All Recent Friend:"))

element_list = driver.find_elements(By.XPATH, "//span[contains(@class,'xjp7ctv')]//a[contains(@href, 'https://www.facebook.com/')]")

print(element_list)
print(len(element_list))

link_list = []

for element in element_list:
    print(element)
    href = element.get_attribute("href")
    print(href)
    # print(input("Seeing Inner Html :"))

    if href:  # Only append if href is not None
        link_list.append(href)

unique_links = list(set(link_list))

# Save to file
with open(r"../AllFriendList.txt", "w", encoding="utf-8") as f:
    for link in unique_links:
        f.write(link + "\n")

print("Collected unique links:")
print(len(unique_links))
print(unique_links)

print(input("Message Next Person:"))
