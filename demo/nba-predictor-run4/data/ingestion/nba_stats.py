"""
Pulls player game logs and team stats from nba_api.
Stores results in SQLite.
"""

import time
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import (
    playergamelogs,
    leaguedashteamstats,
    commonallplayers,
)
from nba_api.stats.static import players, teams
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from data.database import get_connection, init_db

CURRENT_SEASON = "2024-25"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
    "Connection": "keep-alive",
}


def get_all_players():
    """Return list of all active NBA players."""
    all_players = players.get_active_players()
    return all_players


def pull_player_game_logs(player_id: str, player_name: str, season: str = CURRENT_SEASON):
    """Pull all game logs for a player this season and store in DB."""
    try:
        logs = playergamelogs.PlayerGameLogs(
            player_id_nullable=player_id,
            season_nullable=season,
            headers=HEADERS,
            timeout=30,
        )
        df = logs.get_data_frames()[0]
        if df.empty:
            return 0

        conn = get_connection()
        c = conn.cursor()
        inserted = 0

        for _, row in df.iterrows():
            home_away = "HOME" if row.get("MATCHUP", "").find("vs.") != -1 else "AWAY"
            matchup = row.get("MATCHUP", "")
            opp = matchup.split(" ")[-1] if matchup else ""

            try:
                c.execute("""
                    INSERT OR IGNORE INTO player_game_logs
                    (player_id, player_name, game_id, game_date, team_id, team_abbreviation,
                     opponent_team_id, opponent_abbreviation, home_away, wl, min,
                     pts, reb, ast, stl, blk, tov, fg_pct, fg3_pct, ft_pct, plus_minus, season)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    str(player_id),
                    player_name,
                    str(row.get("GAME_ID", "")),
                    str(row.get("GAME_DATE", "")),
                    str(row.get("TEAM_ID", "")),
                    str(row.get("TEAM_ABBREVIATION", "")),
                    "",  # opponent team id not directly available here
                    opp,
                    home_away,
                    str(row.get("WL", "")),
                    float(row.get("MIN", 0) or 0),
                    float(row.get("PTS", 0) or 0),
                    float(row.get("REB", 0) or 0),
                    float(row.get("AST", 0) or 0),
                    float(row.get("STL", 0) or 0),
                    float(row.get("BLK", 0) or 0),
                    float(row.get("TOV", 0) or 0),
                    float(row.get("FG_PCT", 0) or 0),
                    float(row.get("FG3_PCT", 0) or 0),
                    float(row.get("FT_PCT", 0) or 0),
                    float(row.get("PLUS_MINUS", 0) or 0),
                    season,
                ))
                inserted += c.rowcount
            except Exception as e:
                print(f"  Row insert error: {e}")

        conn.commit()
        conn.close()
        return inserted

    except Exception as e:
        print(f"  Error pulling logs for {player_name}: {e}")
        return 0


def pull_team_stats(season: str = CURRENT_SEASON):
    """Pull team defensive ratings and pace."""
    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_simple_nullable="Defense",
            headers=HEADERS,
            timeout=30,
        )
        df = stats.get_data_frames()[0]

        pace_stats = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_simple_nullable="Advanced",
            headers=HEADERS,
            timeout=30,
        )
        pace_df = pace_stats.get_data_frames()[0]

        conn = get_connection()
        c = conn.cursor()

        for _, row in df.iterrows():
            team_id = str(row.get("TEAM_ID", ""))
            pace_row = pace_df[pace_df["TEAM_ID"] == row["TEAM_ID"]]
            pace = float(pace_row["PACE"].values[0]) if not pace_row.empty and "PACE" in pace_row.columns else 0.0
            def_rating = float(pace_row["DEF_RATING"].values[0]) if not pace_row.empty and "DEF_RATING" in pace_row.columns else 0.0

            c.execute("""
                INSERT OR REPLACE INTO team_stats
                (team_id, team_abbreviation, team_name, season, def_rating, pace, opp_pts_per_game, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                team_id,
                str(row.get("TEAM_ABBREVIATION", "")),
                str(row.get("TEAM_NAME", "")),
                season,
                def_rating,
                pace,
                float(row.get("OPP_PTS_PAINT", 0) or 0),
                datetime.now().isoformat(),
            ))

        conn.commit()
        conn.close()
        print(f"Team stats pulled for {season}")

    except Exception as e:
        print(f"Error pulling team stats: {e}")


def pull_all_player_logs(limit: int = None, season: str = CURRENT_SEASON):
    """Pull game logs for all active players. Use limit for testing."""
    init_db()
    all_players = get_all_players()
    if limit:
        all_players = all_players[:limit]

    print(f"Pulling logs for {len(all_players)} players...")
    for i, player in enumerate(all_players):
        print(f"  [{i+1}/{len(all_players)}] {player['full_name']}")
        inserted = pull_player_game_logs(player["id"], player["full_name"], season)
        print(f"    → {inserted} new records")
        time.sleep(0.6)  # respect rate limits

    print("Done pulling player logs.")


if __name__ == "__main__":
    init_db()
    pull_team_stats()
    pull_all_player_logs(limit=50)  # start with 50 for testing
