"""
Pulls NBA schedule and calculates rest days per team.
"""

import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from nba_api.stats.endpoints import leaguegamefinder

sys.path.append(str(Path(__file__).parent.parent.parent))
from data.database import get_connection, init_db

CURRENT_SEASON = "2024-25"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
}


def pull_schedule(season: str = CURRENT_SEASON):
    """Pull full season schedule and store unique games."""
    try:
        finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            headers=HEADERS,
            timeout=30,
        )
        df = finder.get_data_frames()[0]
        if df.empty:
            print("No schedule data returned.")
            return

        # Each game appears twice (one row per team), deduplicate
        games = df[["GAME_ID", "GAME_DATE", "TEAM_ID", "TEAM_ABBREVIATION", "MATCHUP"]].copy()
        games = games.drop_duplicates(subset=["GAME_ID", "TEAM_ID"])

        conn = get_connection()
        c = conn.cursor()
        inserted = 0

        # Group by game_id to get home/away pairs
        for game_id, group in games.groupby("GAME_ID"):
            rows = group.to_dict("records")
            if len(rows) < 2:
                continue

            home = next((r for r in rows if "vs." in r.get("MATCHUP", "")), rows[0])
            away = next((r for r in rows if "@" in r.get("MATCHUP", "")), rows[1])

            try:
                c.execute("""
                    INSERT OR IGNORE INTO schedule
                    (game_id, game_date, home_team_id, home_team_abbreviation,
                     away_team_id, away_team_abbreviation, season)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    str(game_id),
                    str(home.get("GAME_DATE", "")),
                    str(home.get("TEAM_ID", "")),
                    str(home.get("TEAM_ABBREVIATION", "")),
                    str(away.get("TEAM_ID", "")),
                    str(away.get("TEAM_ABBREVIATION", "")),
                    season,
                ))
                inserted += c.rowcount
            except Exception as e:
                print(f"  Schedule insert error: {e}")

        conn.commit()
        conn.close()
        print(f"Schedule: {inserted} new games stored for {season}")

    except Exception as e:
        print(f"Error pulling schedule: {e}")


def get_rest_days(player_id: str, game_date: str) -> int:
    """
    Calculate how many days of rest a player has before a given game.
    Returns days since last game (capped at 7).
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT game_date FROM player_game_logs
        WHERE player_id = ? AND game_date < ?
        ORDER BY game_date DESC
        LIMIT 1
    """, (player_id, game_date))
    row = c.fetchone()
    conn.close()

    if not row:
        return 3  # default if no prior game found

    last_game = datetime.strptime(row["game_date"][:10], "%Y-%m-%d")
    target = datetime.strptime(game_date[:10], "%Y-%m-%d")
    delta = (target - last_game).days
    return min(delta, 7)


def is_back_to_back(player_id: str, game_date: str) -> int:
    """Returns 1 if this game is a back-to-back, 0 otherwise."""
    return 1 if get_rest_days(player_id, game_date) == 1 else 0


if __name__ == "__main__":
    init_db()
    pull_schedule()
