import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

DATA_FILE = Path("data/openings.json")

GOOGLE_NEWS_QUERIES = [
    "store opening Philippines 2026",
    "restaurant opening Manila 2026",
    "mall opening Philippines",
    "brand opens Philippines",
    "first store Philippines",
    "supermarket opens Philippines",
    "opens BGC Taguig",
    "opens Makati Philippines",
    "grand opening Philippines",
    "retail opens Philippines",
    # Mall / commercial development
    "new mall Philippines 2026",
    "mall development Philippines",
    "commercial development Philippines retail",
    "retail park Philippines",
    "groundbreaking mall Philippines",
    "mixed use development Philippines",
    # Brand expansion announcements
    "brand enters Philippines",
    "brand announces Philippines entry",
    "expanding to Philippines",
    "entering Philippine market",
    "to open in Philippines 2026",
    "international brand Philippines debut",
]

PH_RSS_FEEDS = [
    ("Inquirer Business", "https://business.inquirer.net/feed"),
    ("Manila Bulletin", "https://mb.com.ph/category/business/feed"),
    ("BusinessWorld", "https://businessworld.com.ph/feed"),
    ("PhilStar Business", "https://philstar.com/business/rss"),
    ("Rappler Business", "https://rappler.com/business/feed"),
]

INCLUDE_KEYWORDS = [
    "opens", "opening", "grand opening", "new store", "new branch",
    "new outlet", "launches", "first store", "debut", "inaugurates",
    "now open", "soft opening", "opened", "will open", "set to open",
    "enters", "entering", "announces entry", "expanding to",
    "groundbreaking", "to open", "coming soon", "coming to philippines",
    "mall development", "commercial development", "retail park",
]

EXCLUDE_KEYWORDS = [
    "closes", "closure", "shutdown", "bankrupt", "layoff", "laid off",
    "anniversary", "recall", "investigation", "lawsuit", "robbery",
    "fire", "raided", "suspended", "revoked",
]

CATEGORY_RULES = [
    ("Brand Announcement", [
        "enters philippines", "entering the philippine", "expanding to the philippines",
        "expanding to philippines", "announces philippine", "announces ph entry",
        "to debut in", "coming to the philippines", "coming to manila",
        "first time in the philippines", "international brand", "entering philippine market",
    ]),
    ("Mall Development", [
        "mall development", "retail park", "commercial development",
        "mixed-use", "mixed use development", "groundbreaking",
        "new mall", "shopping center development", "commercial complex",
    ]),
    ("Restaurant", ["restaurant", "cafe", "coffee", "dining", "eatery", "bistro",
                    "food hall", "fastfood", "fast food", "pizza", "burger",
                    "ramen", "sushi", "bar and grill", "bar & grill"]),
    ("Supermarket", ["supermarket", "grocery", "hypermarket", "fresh market",
                     "puregold", "savemore", "robinsons supermarket", "walter mart"]),
    ("Department Store", ["department store", "sm ", "ayala mall",
                          "robinsons place", "megamall", "landmark", "rustans"]),
    ("Fashion", ["fashion", "apparel", "clothing", "shoes", "footwear",
                 "boutique", "wear", "denim", "uniqlo", "zara", "h&m",
                 "forever 21", "levi", "nike", "adidas", "vans"]),
]


def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in text_lower for kw in keywords):
            return category
    return "Other"


def is_relevant(title: str, description: str = "") -> bool:
    text = (title + " " + description).lower()
    if any(kw in text for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in text for kw in INCLUDE_KEYWORDS)


def parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                pass
    return None


def fetch_google_news() -> list[dict]:
    articles = []
    for query in GOOGLE_NEWS_QUERIES:
        encoded = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-PH&gl=PH&ceid=PH:en"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "description": re.sub(r"<[^>]+>", "", entry.get("summary", "")),
                    "source": "Google News",
                    "published_at": parse_date(entry),
                })
        except Exception as e:
            print(f"Error fetching Google News query '{query}': {e}")
    return articles


def fetch_ph_rss() -> list[dict]:
    articles = []
    for source_name, feed_url in PH_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "description": re.sub(r"<[^>]+>", "", entry.get("summary", "")),
                    "source": source_name,
                    "published_at": parse_date(entry),
                })
        except Exception as e:
            print(f"Error fetching {source_name}: {e}")
    return articles


def load_existing() -> list[dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return []


def save(openings: list[dict]) -> None:
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(openings, indent=2, ensure_ascii=False))


def main():
    existing = load_existing()
    seen_hashes = {item["url_hash"] for item in existing}

    all_articles = fetch_google_news() + fetch_ph_rss()
    print(f"Fetched {len(all_articles)} total articles")

    new_openings = []
    for article in all_articles:
        if not article["url"]:
            continue
        h = url_hash(article["url"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        if not is_relevant(article["title"], article["description"]):
            continue

        opening = {
            "title": article["title"],
            "url": article["url"],
            "source": article["source"],
            "category": detect_category(article["title"] + " " + article["description"]),
            "found_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "published_at": article["published_at"],
            "url_hash": h,
        }
        new_openings.append(opening)

    print(f"Found {len(new_openings)} new relevant openings")
    save(existing + new_openings)


if __name__ == "__main__":
    main()
