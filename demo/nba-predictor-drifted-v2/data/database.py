"""
SQLite database setup and query helpers.
All tables are created here on first run.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "nba.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Player game logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS player_game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            player_name TEXT,
            game_id TEXT,
            game_date TEXT,
            team_id TEXT,
            team_abbreviation TEXT,
            opponent_team_id TEXT,
            opponent_abbreviation TEXT,
            home_away TEXT,
            wl TEXT,
            min REAL,
            pts REAL,
            reb REAL,
            ast REAL,
            stl REAL,
            blk REAL,
            tov REAL,
            fg_pct REAL,
            fg3_pct REAL,
            ft_pct REAL,
            plus_minus REAL,
            season TEXT,
            UNIQUE(player_id, game_id)
        )
    """)

    # Team defensive stats
    c.execute("""
        CREATE TABLE IF NOT EXISTS team_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            team_abbreviation TEXT,
            team_name TEXT,
            season TEXT,
            def_rating REAL,
            pace REAL,
            opp_pts_per_game REAL,
            updated_at TEXT,
            UNIQUE(team_id, season)
        )
    """)

    # Schedule / upcoming games
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            game_date TEXT,
            home_team_id TEXT,
            home_team_abbreviation TEXT,
            away_team_id TEXT,
            away_team_abbreviation TEXT,
            season TEXT
        )
    """)

    # News articles
    c.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            title TEXT,
            description TEXT,
            published_at TEXT,
            source TEXT,
            sentiment_score REAL,
            injury_flag INTEGER DEFAULT 0,
            fetched_at TEXT,
            UNIQUE(player_name, title)
        )
    """)

    # Prop lines
    c.execute("""
        CREATE TABLE IF NOT EXISTS prop_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            game_date TEXT,
            stat TEXT,
            line REAL,
            over_odds REAL,
            under_odds REAL,
            bookmaker TEXT,
            fetched_at TEXT
        )
    """)

    # Predictions log
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            opponent_abbreviation TEXT,
            game_date TEXT,
            predicted_pts REAL,
            predicted_reb REAL,
            predicted_ast REAL,
            predicted_stl REAL,
            predicted_blk REAL,
            predicted_tov REAL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
