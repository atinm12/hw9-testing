"""
Pulls NBA player prop lines from The Odds API.
Used as a market baseline feature in predictions.
"""

import requests
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent.parent))
from data.database import get_connection, init_db

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4"

STAT_MARKETS = {
    "pts": "player_points",
    "reb": "player_rebounds",
    "ast": "player_assists",
    "stl": "player_steals",
    "blk": "player_blocks",
    "tov": "player_turnovers",
}


def pull_props():
    """Pull NBA player props for today's games."""
    if not ODDS_API_KEY:
        print("No ODDS_API_KEY set — skipping props pull.")
        return

    # First get today's NBA event IDs
    try:
        events_url = f"{BASE_URL}/sports/basketball_nba/events"
        resp = requests.get(events_url, params={"apiKey": ODDS_API_KEY}, timeout=10)
        events = resp.json()

        if not isinstance(events, list):
            print(f"Odds API error: {events}")
            return

        conn = get_connection()
        c = conn.cursor()

        for event in events:
            event_id = event.get("id")
            game_date = event.get("commence_time", "")[:10]

            for stat_key, market in STAT_MARKETS.items():
                try:
                    props_url = f"{BASE_URL}/sports/basketball_nba/events/{event_id}/odds"
                    r = requests.get(props_url, params={
                        "apiKey": ODDS_API_KEY,
                        "markets": market,
                        "oddsFormat": "american",
                    }, timeout=10)
                    data = r.json()

                    for bookmaker in data.get("bookmakers", [])[:1]:  # just use first bookmaker
                        bk_name = bookmaker.get("title", "")
                        for mkt in bookmaker.get("markets", []):
                            for outcome in mkt.get("outcomes", []):
                                player_name = outcome.get("description", "")
                                line = outcome.get("point", None)
                                price = outcome.get("price", None)
                                name = outcome.get("name", "")

                                if line is not None:
                                    c.execute("""
                                        INSERT INTO prop_lines
                                        (player_name, game_date, stat, line, over_odds, under_odds, bookmaker, fetched_at)
                                        VALUES (?,?,?,?,?,?,?,?)
                                    """, (
                                        player_name, game_date, stat_key,
                                        float(line),
                                        float(price) if name == "Over" else None,
                                        float(price) if name == "Under" else None,
                                        bk_name,
                                        datetime.now().isoformat(),
                                    ))
                except Exception as e:
                    print(f"  Props error for {event_id} / {stat_key}: {e}")

        conn.commit()
        conn.close()
        print("Props pulled successfully.")

    except Exception as e:
        print(f"Error pulling props: {e}")


def get_prop_line(player_name: str, stat: str, game_date: str) -> float:
    """Return the market prop line for a player/stat/date. Returns -1 if not found."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT line FROM prop_lines
        WHERE player_name LIKE ? AND stat = ? AND game_date = ?
        ORDER BY fetched_at DESC LIMIT 1
    """, (f"%{player_name.split()[-1]}%", stat, game_date))
    row = c.fetchone()
    conn.close()
    return float(row["line"]) if row else -1.0


if __name__ == "__main__":
    init_db()
    pull_props()
