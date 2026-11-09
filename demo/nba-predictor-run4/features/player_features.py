"""
Player-level features: rolling averages, trends, shooting efficiency.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from data.database import get_connection

STATS = ["pts", "reb", "ast", "stl", "blk", "tov", "min", "fg_pct", "fg3_pct", "ft_pct"]


def get_player_game_logs(player_name: str, season: str = "2024-25") -> pd.DataFrame:
    """Load all game logs for a player from DB."""
    conn = get_connection()
    query = """
        SELECT * FROM player_game_logs
        WHERE player_name = ? AND season = ?
        ORDER BY game_date ASC
    """
    df = pd.read_sql_query(query, conn, params=(player_name, season))
    conn.close()
    return df


def compute_rolling_averages(df: pd.DataFrame, windows: list = [5, 10, 20]) -> dict:
    """
    Compute rolling averages for each stat over multiple windows.
    Returns dict of feature_name -> value based on most recent games.
    """
    features = {}

    if df.empty:
        for stat in STATS:
            for w in windows:
                features[f"{stat}_avg_{w}g"] = 0.0
        return features

    df = df.sort_values("game_date").reset_index(drop=True)

    for stat in STATS:
        col = stat
        if col not in df.columns:
            for w in windows:
                features[f"{stat}_avg_{w}g"] = 0.0
            continue

        series = df[col].astype(float)
        for w in windows:
            recent = series.tail(w)
            features[f"{stat}_avg_{w}g"] = round(float(recent.mean()), 3) if len(recent) > 0 else 0.0

    # Trend: last 5 vs last 20 (positive = improving)
    for stat in ["pts", "reb", "ast"]:
        avg5 = features.get(f"{stat}_avg_5g", 0)
        avg20 = features.get(f"{stat}_avg_20g", 0)
        features[f"{stat}_trend"] = round(avg5 - avg20, 3)

    # Games played (sample size signal)
    features["games_played"] = len(df)

    # Usage proxy: minutes played avg
    features["min_avg_5g"] = features.get("min_avg_5g", 0.0)

    return features


def get_home_away_splits(df: pd.DataFrame) -> dict:
    """Compute home vs away performance splits."""
    features = {}
    if df.empty:
        return {"home_pts_avg": 0.0, "away_pts_avg": 0.0, "home_away_diff": 0.0}

    home = df[df["home_away"] == "HOME"]
    away = df[df["home_away"] == "AWAY"]

    features["home_pts_avg"] = round(float(home["pts"].mean()), 3) if not home.empty else 0.0
    features["away_pts_avg"] = round(float(away["pts"].mean()), 3) if not away.empty else 0.0
    features["home_away_diff"] = round(features["home_pts_avg"] - features["away_pts_avg"], 3)

    return features


def get_player_features(player_name: str, is_home: bool, season: str = "2024-25") -> dict:
    """
    Master function: return all player-level features for prediction.
    """
    df = get_player_game_logs(player_name, season)
    features = {}

    # Rolling averages
    features.update(compute_rolling_averages(df))

    # Home/away splits
    features.update(get_home_away_splits(df))

    # Home flag
    features["is_home"] = 1 if is_home else 0

    return features
