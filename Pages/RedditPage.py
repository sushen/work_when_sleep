from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class RedditPage:
    def __init__(self, driver):
        self.driver = driver

        self.wait = WebDriverWait(self.driver, 15)

    def get_latest_post_info(self):
        try:

            latest_post = self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "shreddit-post"))
            )

            post_id = latest_post.get_attribute("id")
            title = latest_post.get_attribute("post-title")
            author = latest_post.get_attribute("author")

            permalink = latest_post.get_attribute("permalink")
            link = f"https://www.reddit.com{permalink}"

            return {
                "id": post_id,
                "title": title,
                "author": author,
                "link": link
            }

        except Exception as e:
            print(f"  -> Could not locate post elements: {e}")
            return None