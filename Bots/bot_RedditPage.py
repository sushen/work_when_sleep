import time
import winsound
import sqlite3
from datetime import datetime
from Bots.bot_base import BaseBot
from Pages.RedditPage import RedditPage


class Bot_RedditPage(BaseBot):
    def setup_database(self):
        conn = sqlite3.connect('reddit_posts.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                link TEXT,
                detected_at TEXT,
                subreddit TEXT
            )
        ''')
        conn.commit()
        return conn

    def save_to_db(self, conn, post, subreddit):
        cursor = conn.cursor()
        detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute('''
                INSERT INTO posts (id, title, author, link, detected_at, subreddit)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (post.get("id"), post.get("title"), post.get("author"), post.get("link"), detected_at, subreddit))
            conn.commit()
            print(f"[Database] Saved post from r/{subreddit} at {detected_at}.")
        except sqlite3.IntegrityError:
            pass

    def monitor_new_posts(self, subreddits, check_interval_sec=60):
        conn = self.setup_database()
        reddit_page = RedditPage(self.driver)

        # Dictionary to track the latest post ID for each subreddit independently
        seen_post_ids = {sub: None for sub in subreddits}

        print(f"Starting monitor for: {', '.join(subreddits)}")

        while True:
            for sub in subreddits:
                try:
                    target_url = f"https://www.reddit.com/r/{sub}/new/"
                    print(f"Checking r/{sub}...")
                    self.driver.get(target_url)

                    # Wait for page to load after navigating
                    time.sleep(5)

                    post = reddit_page.get_latest_post_info()

                    if post and seen_post_ids[sub] is None:
                        # INITIALIZATION for this specific subreddit
                        seen_post_ids[sub] = post.get("id")
                        print(f"[INIT] r/{sub} - Current Latest: {post.get('title')}")
                        self.save_to_db(conn, post, sub)
                        winsound.Beep(500, 500)

                    elif post and post.get("id") != seen_post_ids[sub]:
                        # NEW POST DETECTED in this specific subreddit
                        seen_post_ids[sub] = post.get("id")
                        print(f"\n--- NEW POST IN r/{sub} ---")
                        print(f"Title:  {post.get('title')}")
                        print(f"Author: u/{post.get('author')}")
                        print(f"Link:   {post.get('link')}")


                        self.save_to_db(conn, post, sub)
                        winsound.Beep(1000, 1500)

                except Exception as e:
                    print(f"Error checking r/{sub}: {e}")

            # Sleep only after checking all subreddits in the list
            print(f"Cycle complete. Waiting {check_interval_sec} seconds...\n")
            time.sleep(check_interval_sec)