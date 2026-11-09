"""
News-derived features: sentiment score, injury flag, recent coverage volume.
Wraps the news ingestion module for use in the feature pipeline.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from data.ingestion.news import get_player_news_features, pull_player_news


def get_news_features(player_name: str, refresh: bool = False) -> dict:
    """
    Return news-based features for a player.
    If refresh=True, re-pulls latest articles before computing features.

    Features returned:
    - avg_sentiment: -1 to 1, negative = bad news
    - injury_flag: 1 if recent articles mention injury/trade/suspension
    - recent_articles: count of articles in DB (signal of media attention)
    """
    if refresh:
        pull_player_news(player_name)

    return get_player_news_features(player_name)
