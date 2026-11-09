"""
Master pipeline: runs the full data pull → feature build → model train cycle.
Run this once to bootstrap the project, then daily to keep data fresh.

Usage:
    python pipeline.py              # full run
    python pipeline.py --quick      # 50 players only (for testing)
    python pipeline.py --predict    # just generate today's predictions
"""

import argparse
import sys
from datetime import datetime

from data.database import init_db
from data.ingestion.nba_stats import pull_team_stats, pull_all_player_logs
from data.ingestion.schedule import pull_schedule
from data.ingestion.news import pull_player_news
from data.ingestion.odds import pull_props
from models.train import train_models
from models.predict import predict_game, print_prediction
from data.database import get_connection


def run_pipeline(quick: bool = False):
    print("\n" + "=" * 60)
    print(f"  NBA Predictor Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Initialize DB
    print("\n[1/6] Initializing database...")
    init_db()

    # 2. Pull team stats
    print("\n[2/6] Pulling team stats...")
    pull_team_stats()

    # 3. Pull schedule
    print("\n[3/6] Pulling schedule...")
    pull_schedule()

    # 4. Pull player game logs
    limit = 50 if quick else None
    print(f"\n[4/6] Pulling player game logs {'(quick: 50 players)' if quick else '(all players)'}...")
    pull_all_player_logs(limit=limit)

    # 5. Pull news for top players
    print("\n[5/6] Pulling news...")
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT player_name, AVG(pts) as avg_pts
        FROM player_game_logs
        GROUP BY player_name
        ORDER BY avg_pts DESC
        LIMIT 50
    """)
    top_players = [r["player_name"] for r in c.fetchall()]
    conn.close()

    for player in top_players:
        pull_player_news(player)

    # 6. Pull prop lines
    print("\n[6/6] Pulling prop lines...")
    pull_props()

    # 7. Train models
    print("\n[7/7] Training models...")
    train_models()

    print("\n✅ Pipeline complete. Run the dashboard with:")
    print("   streamlit run dashboard/app.py")


def run_predictions():
    """Generate predictions for a few example players."""
    examples = [
        ("LeBron James", "GSW", True),
        ("Stephen Curry", "LAL", False),
        ("Nikola Jokic", "BOS", True),
    ]
    for player, opp, home in examples:
        result = predict_game(player, opp, is_home=home, refresh_news=False)
        print_prediction(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Only pull 50 players")
    parser.add_argument("--predict", action="store_true", help="Run example predictions only")
    args = parser.parse_args()

    if args.predict:
        run_predictions()
    else:
        run_pipeline(quick=args.quick)
