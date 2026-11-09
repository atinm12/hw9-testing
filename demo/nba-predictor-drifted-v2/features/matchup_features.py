"""
Matchup features: how a player has performed against a specific opponent
and against similar teams (by defensive rating).
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from data.database import get_connection

STATS = ["pts", "reb", "ast", "stl", "blk", "tov"]


def get_vs_opponent_stats(player_name: str, opponent_abbreviation: str) -> dict:
    """
    Historical averages for this player against this specific opponent.
    """
    conn = get_connection()
    query = """
        SELECT pts, reb, ast, stl, blk, tov
        FROM player_game_logs
        WHERE player_name = ? AND opponent_abbreviation = ?
        ORDER BY game_date DESC
        LIMIT 10
    """
    df = pd.read_sql_query(query, conn, params=(player_name, opponent_abbreviation))
    conn.close()

    features = {}
    if df.empty:
        for stat in STATS:
            features[f"vs_opp_{stat}_avg"] = -1.0  # -1 signals no history
        features["vs_opp_games"] = 0
        return features

    for stat in STATS:
        features[f"vs_opp_{stat}_avg"] = round(float(df[stat].mean()), 3)
    features["vs_opp_games"] = len(df)
    return features


def get_opponent_def_rating(opponent_abbreviation: str, season: str = "2024-25") -> float:
    """Return defensive rating of the opponent team."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT def_rating FROM team_stats
        WHERE team_abbreviation = ? AND season = ?
        LIMIT 1
    """, (opponent_abbreviation, season))
    row = c.fetchone()
    conn.close()
    return float(row["def_rating"]) if row else 110.0  # league avg fallback


def get_opponent_pace(opponent_abbreviation: str, season: str = "2024-25") -> float:
    """Return pace of the opponent team."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT pace FROM team_stats
        WHERE team_abbreviation = ? AND season = ?
        LIMIT 1
    """, (opponent_abbreviation, season))
    row = c.fetchone()
    conn.close()
    return float(row["pace"]) if row else 98.0  # league avg fallback


def get_vs_similar_teams(player_name: str, opponent_abbreviation: str, season: str = "2024-25") -> dict:
    """
    Performance against teams with similar defensive ratings (+/- 3 points).
    Fills in the gap when direct matchup history is thin.
    """
    opp_def = get_opponent_def_rating(opponent_abbreviation, season)

    conn = get_connection()

    # Get all teams within similar defensive rating band
    teams_query = """
        SELECT team_abbreviation FROM team_stats
        WHERE season = ? AND ABS(def_rating - ?) <= 3.0
    """
    teams_df = pd.read_sql_query(teams_query, conn, params=(season, opp_def))

    if teams_df.empty:
        conn.close()
        return {f"vs_similar_{stat}_avg": -1.0 for stat in STATS}

    similar_abbrevs = teams_df["team_abbreviation"].tolist()
    placeholders = ",".join(["?" for _ in similar_abbrevs])

    logs_query = f"""
        SELECT pts, reb, ast, stl, blk, tov
        FROM player_game_logs
        WHERE player_name = ? AND opponent_abbreviation IN ({placeholders})
        ORDER BY game_date DESC
        LIMIT 20
    """
    df = pd.read_sql_query(logs_query, conn, params=[player_name] + similar_abbrevs)
    conn.close()

    features = {}
    if df.empty:
        for stat in STATS:
            features[f"vs_similar_{stat}_avg"] = -1.0
        features["vs_similar_games"] = 0
        return features

    for stat in STATS:
        features[f"vs_similar_{stat}_avg"] = round(float(df[stat].mean()), 3)
    features["vs_similar_games"] = len(df)
    return features


def get_matchup_features(player_name: str, opponent_abbreviation: str, season: str = "2024-25") -> dict:
    """Master function: all matchup-level features."""
    features = {}
    features.update(get_vs_opponent_stats(player_name, opponent_abbreviation))
    features.update(get_vs_similar_teams(player_name, opponent_abbreviation, season))
    features["opp_def_rating"] = get_opponent_def_rating(opponent_abbreviation, season)
    features["opp_pace"] = get_opponent_pace(opponent_abbreviation, season)
    return features
