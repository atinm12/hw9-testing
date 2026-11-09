"""
Game context features: rest days, back-to-back, home/away, altitude, travel.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from data.database import get_connection

# Teams that play at altitude (affects visiting players)
ALTITUDE_TEAMS = {"DEN"}

# Rough time zones for each team abbreviation (offset from ET)
TEAM_TIMEZONES = {
    "ATL": 0, "BOS": 0, "BKN": 0, "CHA": 0, "CHI": -1, "CLE": 0,
    "DAL": -1, "DEN": -2, "DET": 0, "GSW": -3, "HOU": -1, "IND": 0,
    "LAC": -3, "LAL": -3, "MEM": -1, "MIA": 0, "MIL": -1, "MIN": -1,
    "NOP": -1, "NYK": 0, "OKC": -1, "ORL": 0, "PHI": 0, "PHX": -3,
    "POR": -3, "SAC": -3, "SAS": -1, "TOR": 0, "UTA": -2, "WAS": 0,
}


def get_rest_days(player_name: str, game_date: str) -> int:
    """Days since player's last game (capped at 7)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT game_date FROM player_game_logs
        WHERE player_name = ? AND game_date < ?
        ORDER BY game_date DESC LIMIT 1
    """, (player_name, game_date))
    row = c.fetchone()
    conn.close()

    if not row:
        return 3  # neutral default

    last = datetime.strptime(row["game_date"][:10], "%Y-%m-%d")
    target = datetime.strptime(game_date[:10], "%Y-%m-%d")
    return min((target - last).days, 7)


def get_travel_fatigue(player_name: str, opponent_abbreviation: str, game_date: str) -> int:
    """
    Estimate time zone shift from player's last game location to current game.
    Returns absolute time zone difference (0-3).
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT opponent_abbreviation, home_away FROM player_game_logs
        WHERE player_name = ? AND game_date < ?
        ORDER BY game_date DESC LIMIT 1
    """, (player_name, game_date))
    row = c.fetchone()
    conn.close()

    if not row:
        return 0

    prev_location = row["opponent_abbreviation"] if row["home_away"] == "AWAY" else None
    if not prev_location:
        return 0

    prev_tz = TEAM_TIMEZONES.get(prev_location, 0)
    curr_tz = TEAM_TIMEZONES.get(opponent_abbreviation, 0)
    return abs(curr_tz - prev_tz)


def get_game_features(player_name: str, opponent_abbreviation: str,
                      game_date: str, is_home: bool) -> dict:
    """Master function: all game-context features."""
    rest = get_rest_days(player_name, game_date)
    travel = get_travel_fatigue(player_name, opponent_abbreviation, game_date)

    return {
        "rest_days": rest,
        "is_back_to_back": 1 if rest == 1 else 0,
        "is_home": 1 if is_home else 0,
        "altitude_game": 1 if opponent_abbreviation in ALTITUDE_TEAMS and not is_home else 0,
        "travel_fatigue": travel,
    }
