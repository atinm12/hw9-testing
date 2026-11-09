"""
Master feature builder: combines all feature modules into a single
feature vector for model training or prediction.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from features.player_features import get_player_features
from features.matchup_features import get_matchup_features
from features.game_features import get_game_features
from features.news_features import get_news_features
from data.ingestion.odds import get_prop_line


def build_feature_vector(
    player_name: str,
    opponent_abbreviation: str,
    game_date: str,
    is_home: bool,
    season: str = "2024-25",
    refresh_news: bool = False,
) -> dict:
    """
    Build the full feature vector for a player/game combination.
    Used for both training (historical games) and live prediction.
    """
    features = {}

    # 1. Player rolling stats and splits
    player_feats = get_player_features(player_name, is_home, season)
    features.update(player_feats)

    # 2. Matchup history and opponent quality
    matchup_feats = get_matchup_features(player_name, opponent_abbreviation, season)
    features.update(matchup_feats)

    # 3. Game context (rest, travel, altitude)
    game_feats = get_game_features(player_name, opponent_abbreviation, game_date, is_home)
    features.update(game_feats)

    # 4. News sentiment and injury flags
    news_feats = get_news_features(player_name, refresh=refresh_news)
    features.update(news_feats)

    # 5. Vegas prop lines as market baseline (one per stat)
    for stat in ["pts", "reb", "ast", "stl", "blk", "tov"]:
        features[f"prop_line_{stat}"] = get_prop_line(player_name, stat, game_date)

    return features


def build_training_rows(season: str = "2024-25") -> list[dict]:
    """
    Build feature rows for every historical game in the DB.
    Each row includes features + actual stat targets.
    Used to train the XGBoost models.
    """
    import pandas as pd
    from data.database import get_connection

    conn = get_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT player_name, opponent_abbreviation, game_date, home_away,
               pts, reb, ast, stl, blk, tov
        FROM player_game_logs
        WHERE season = ? AND min > 10
        ORDER BY game_date ASC
    """, (season,))
    rows = c.fetchall()
    conn.close()

    training_data = []
    print(f"Building features for {len(rows)} game rows...")

    for i, row in enumerate(rows):
        if i % 100 == 0:
            print(f"  {i}/{len(rows)}")

        is_home = row["home_away"] == "HOME"
        try:
            feats = build_feature_vector(
                player_name=row["player_name"],
                opponent_abbreviation=row["opponent_abbreviation"],
                game_date=row["game_date"],
                is_home=is_home,
                season=season,
                refresh_news=False,
            )
            # Add targets
            feats["target_pts"] = float(row["pts"])
            feats["target_reb"] = float(row["reb"])
            feats["target_ast"] = float(row["ast"])
            feats["target_stl"] = float(row["stl"])
            feats["target_blk"] = float(row["blk"])
            feats["target_tov"] = float(row["tov"])
            feats["player_name"] = row["player_name"]
            feats["game_date"] = row["game_date"]
            training_data.append(feats)
        except Exception as e:
            print(f"  Error building features for {row['player_name']} on {row['game_date']}: {e}")

    return training_data
