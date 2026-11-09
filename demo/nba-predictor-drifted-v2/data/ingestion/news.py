"""
Pulls NBA player news from NewsAPI and scores sentiment.
Flags injury-related articles.
"""

import requests
import sys
from pathlib import Path
from datetime import datetime
from textblob import TextBlob
import os
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent.parent))
from data.database import get_connection, init_db

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"

INJURY_KEYWORDS = [
    "injury", "injured", "out", "questionable", "doubtful",
    "probable", "day-to-day", "ruled out", "miss", "sprain",
    "strain", "fracture", "surgery", "trade", "traded", "suspended"
]


def score_sentiment(text: str) -> float:
    """TextBlob polarity: -1 (negative) to 1 (positive)."""
    if not text:
        return 0.0
    return TextBlob(text).sentiment.polarity


def has_injury_flag(title: str, description: str) -> int:
    """Returns 1 if article mentions injury/trade/suspension."""
    combined = f"{title} {description}".lower()
    return 1 if any(kw in combined for kw in INJURY_KEYWORDS) else 0


def pull_player_news(player_name: str, days_back: int = 7):
    """Pull recent news for a player and store in DB."""
    if not NEWS_API_KEY:
        print("No NEWS_API_KEY set — skipping news pull.")
        return 0

    params = {
        "q": f'"{player_name}" NBA',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY,
    }

    try:
        resp = requests.get(NEWS_API_URL, params=params, timeout=10)
        data = resp.json()

        if data.get("status") != "ok":
            print(f"  NewsAPI error for {player_name}: {data.get('message', '')}")
            return 0

        articles = data.get("articles", [])
        conn = get_connection()
        c = conn.cursor()
        inserted = 0

        for article in articles:
            title = article.get("title", "") or ""
            description = article.get("description", "") or ""
            published_at = article.get("publishedAt", "") or ""
            source = article.get("source", {}).get("name", "") or ""

            sentiment = score_sentiment(f"{title} {description}")
            injury = has_injury_flag(title, description)

            try:
                c.execute("""
                    INSERT OR IGNORE INTO news_articles
                    (player_name, title, description, published_at, source,
                     sentiment_score, injury_flag, fetched_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    player_name, title, description, published_at,
                    source, sentiment, injury, datetime.now().isoformat()
                ))
                inserted += c.rowcount
            except Exception as e:
                print(f"  News insert error: {e}")

        conn.commit()
        conn.close()
        return inserted

    except Exception as e:
        print(f"  Error fetching news for {player_name}: {e}")
        return 0


def get_player_news_features(player_name: str) -> dict:
    """
    Return aggregated news features for a player.
    Used in feature engineering.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT sentiment_score, injury_flag
        FROM news_articles
        WHERE player_name = ?
        ORDER BY published_at DESC
        LIMIT 5
    """, (player_name,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return {
            "avg_sentiment": 0.0,
            "injury_flag": 0,
            "recent_articles": 0,
        }

    sentiments = [r["sentiment_score"] for r in rows]
    injury = max(r["injury_flag"] for r in rows)

    return {
        "avg_sentiment": sum(sentiments) / len(sentiments),
        "injury_flag": injury,
        "recent_articles": len(rows),
    }


if __name__ == "__main__":
    init_db()
    players_to_check = ["LeBron James", "Stephen Curry", "Nikola Jokic", "Giannis Antetokounmpo"]
    for p in players_to_check:
        n = pull_player_news(p)
        print(f"{p}: {n} articles stored")
