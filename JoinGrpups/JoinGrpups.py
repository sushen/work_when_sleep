# JoinGroups_extended.py
# Purpose: open Facebook Group search tabs for country-specific keywords (no CSV).
# Requires: your existing driver/login modules:
#   from driver.driver import Driver
#   from login.login import Login

import argparse
import time
from urllib.parse import quote_plus

from driver.driver import Driver
from login.login import Login

# --- Country-specific keywords (non-Binance exchanges + multi-asset + dev/algo) ---
KEYWORDS = {
    "Germany": {
        "exchange": ["Bitvavo Germany", "Kraken Germany", "Bitstamp DE"],
        "multi_asset": ["Forex Deutschland", "Aktienhandel", "Gold Trading Germany"],
        "dev_algo": ["Python Trader Germany", "Algo Trading DE", "MT4 MT5 Germany"],
    },
    "France": {
        "exchange": ["Kraken France", "Bitstamp France"],
        "multi_asset": ["Forex France", "Bourse France", "Gold France"],
        "dev_algo": ["Developpeur Python Trading", "Algo Trading France"],
    },
    "Spain": {
        "exchange": ["Kraken España", "Bitvavo España"],
        "multi_asset": ["Forex España", "Bolsa España", "Oro Trading España"],
        "dev_algo": ["Trading Algorítmico España", "Python Traders ES"],
    },
    "Italy": {
        "exchange": ["Kraken Italia", "Bitstamp Italia"],
        "multi_asset": ["Forex Italia", "Borsa Italia", "Oro Trading Italia"],
        "dev_algo": ["Algo Trading Italia", "Python Trading IT"],
    },
    "Poland": {
        "exchange": ["Kraken Polska", "Bitstamp Polska"],
        "multi_asset": ["Forex Polska", "Giełda Akcji", "Złoto Trading"],
        "dev_algo": ["Algo Trading Polska", "Python Trader PL"],
    },
    "Portugal": {
        "exchange": ["Kraken Portugal", "Bitstamp Portugal"],
        "multi_asset": ["Forex Portugal", "PSI Traders", "Ouro Trading"],
        "dev_algo": ["Algo Trading Portugal", "Python Trading PT"],
    },
    "Czech Republic": {
        "exchange": ["Kraken Czech", "Bitstamp CZ"],
        "multi_asset": ["Forex Česko", "Burza Akcií", "Zlato Trading"],
        "dev_algo": ["Algo Trading CZ", "Python Trader CZ"],
    },
    "Romania": {
        "exchange": ["Kraken Romania", "Bitstamp RO"],
        "multi_asset": ["Forex România", "Bursa de Valori", "Aur Trading"],
        "dev_algo": ["Algo Trading RO", "Python Trading RO"],
    },
    "Greece": {
        "exchange": ["Kraken Greece", "Bitstamp Greece"],
        "multi_asset": ["Forex Greece", "ATHEX Traders", "Gold Greece"],
        "dev_algo": ["Algo Trading Greece", "Python Trading GR"],
    },
    "Hungary": {
        "exchange": ["Kraken Hungary", "Bitstamp HU"],
        "multi_asset": ["Forex Magyarország", "BÉT Traders", "Arany Trading"],
        "dev_algo": ["Algo Trading HU", "Python Trader HU"],
    },
    "Turkey": {
        "exchange": ["Paribu", "BtcTurk", "Kraken Turkey"],
        "multi_asset": ["Forex Türkiye", "Borsa İstanbul", "Altın Trading"],
        "dev_algo": ["Python Algo TR", "MT4 MT5 Türkiye"],
    },
    "India": {
        "exchange": ["WazirX", "CoinDCX", "Kraken India"],
        "multi_asset": ["Forex India", "NSE Traders", "Gold Trading India"],
        "dev_algo": ["Python for Trading India", "Pine Script India"],
    },
    "Australia": {
        "exchange": ["Swyftx", "Independent Reserve", "Kraken AU"],
        "multi_asset": ["Forex Australia", "ASX Traders", "Gold Trading Australia", "Commodity Trading Australia"],
        "dev_algo": ["Python Trading AU", "Algo Trading Australia"],
    },
    "Saudi Arabia": {
        "exchange": ["Rain Exchange", "BitOasis"],
        "multi_asset": ["Forex Saudi", "Tadawul Traders", "Gold Middle East", "Commodity Trading KSA"],
        "dev_algo": ["Algo Trading KSA", "Python Trading GCC"],
    },
    "Qatar": {
        "exchange": ["Rain", "BitOasis"],
        "multi_asset": ["Forex Qatar", "Gold Qatar"],
        "dev_algo": ["Algo Trading Qatar", "Python Trading Qatar"],
    },
    "Kuwait": {
        "exchange": ["Rain", "BitOasis"],
        "multi_asset": ["Forex Kuwait", "Gold Kuwait"],
        "dev_algo": ["Algo Trading Kuwait", "Python Trading Kuwait"],
    },
    "Oman": {
        "exchange": ["Rain", "BitOasis"],
        "multi_asset": ["Forex Oman", "Gold Oman"],
        "dev_algo": ["Algo Trading Oman", "Python Trading Oman"],
    },
    "Bahrain": {
        "exchange": ["Rain", "BitOasis"],
        "multi_asset": ["Forex Bahrain", "Gold Bahrain"],
        "dev_algo": ["Algo Trading Bahrain", "Python Trading Bahrain"],
    },
    "Nigeria": {
        "exchange": ["Luno Nigeria", "Kraken Nigeria"],
        "multi_asset": ["Forex Nigeria", "NGX Traders", "Gold Nigeria"],
        "dev_algo": ["Algo Trading Nigeria", "Python Traders NG"],
    },
    "Kenya": {
        "exchange": ["Luno Kenya", "Kraken Kenya"],
        "multi_asset": ["Forex Kenya", "NSE Kenya", "Gold Kenya"],
        "dev_algo": ["Algo Trading Kenya", "Python Trading Kenya"],
    },
    "South Africa": {
        "exchange": ["VALR", "Luno South Africa"],
        "multi_asset": ["Forex South Africa", "JSE Traders", "Gold South Africa"],
        "dev_algo": ["Algo Trading SA", "Python Trading ZA"],
    },
    "Brazil": {
        "exchange": ["Mercado Bitcoin", "Kraken Brasil"],
        "multi_asset": ["Forex Brasil", "B3 Traders", "Ouro Brasil"],
        "dev_algo": ["Trading Algorítmico BR", "Python Traders BR"],
    },
    "Argentina": {
        "exchange": ["Ripio", "Kraken Argentina"],
        "multi_asset": ["Forex Argentina", "Bolsa Argentina", "Oro Argentina"],
        "dev_algo": ["Algo Trading AR", "Python Traders AR"],
    },
    "Mexico": {
        "exchange": ["Bitso", "Kraken Mexico"],
        "multi_asset": ["Forex México", "BMV Traders", "Oro México"],
        "dev_algo": ["Algo Trading MX", "Python Traders MX"],
    },
}

def fb_group_search_url(query: str) -> str:
    return f"https://www.facebook.com/search/groups/?q={quote_plus(query)}"

def iter_queries(countries, include_categories):
    for country in countries:
        items = KEYWORDS.get(country, {})
        for cat, kws in items.items():
            if include_categories and cat not in include_categories:
                continue
            for kw in kws:
                yield country, cat, kw

def main():
    parser = argparse.ArgumentParser(description="Open Facebook Group searches by country keywords (no CSV).")
    parser.add_argument("--countries", nargs="*", default=[], help="Countries to include (default: all in KEYWORDS)")
    parser.add_argument("--categories", nargs="*", default=[],
                        choices=["exchange", "multi_asset", "dev_algo"],
                        help="Limit to categories (exchange|multi_asset|dev_algo). Default: all.")
    parser.add_argument("--limit", type=int, default=30, help="Max number of searches to open (tabs).")
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait between opening tabs.")
    args = parser.parse_args()

    # Build list of countries/categories
    countries = args.countries or list(KEYWORDS.keys())
    categories = set(args.categories) if args.categories else None

    print(f"[INFO] Countries: {countries}")
    print(f"[INFO] Categories: {sorted(list(categories)) if categories else 'ALL'}")
    print(f"[INFO] Limit: {args.limit} | Sleep: {args.sleep}s")

    # Login once
    driver = Driver().driver
    driver.get("https://facebook.com")
    Login().login(driver)
    time.sleep(3)

    # Open searches
    opened = 0
    for country, cat, kw in iter_queries(countries, categories):
        url = fb_group_search_url(kw)
        print(f"[OPEN] {country} | {cat} | {kw} -> {url}")
        driver.execute_script(f"window.open('{url}', '_blank');")
        opened += 1
        time.sleep(args.sleep)
        if opened >= args.limit:
            break
        print(input("Next Group:"))

    print(f"[DONE] Opened {opened} Facebook group search tabs.")

if __name__ == "__main__":
    main()
