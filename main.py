from Bots.bot_RedditPage import Bot_RedditPage

reddit_bot = Bot_RedditPage()


target_groups = ["algotrading", "algotradingcrypto", "python"]

reddit_bot.monitor_new_posts(subreddits=target_groups)