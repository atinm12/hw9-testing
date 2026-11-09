"""
Evaluates model predictions against actual outcomes and Vegas prop lines.
Run after a game concludes to track real-world accuracy.
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from data.database import get_connection

TARGETS = ["pts", "reb", "ast", "stl", "blk", "tov"]


def compare_vs_actual(player_name: str = None, season: str = "2024-25") -> pd.DataFrame:
    """
    Compare saved predictions vs actual game log outcomes.
    Joins predictions table with player_game_logs on player + date.
    """
    conn = get_connection()

    query = """
        SELECT
            p.player_name,
            p.opponent_abbreviation,
            p.game_date,
            p.predicted_pts, p.predicted_reb, p.predicted_ast,
            p.predicted_stl, p.predicted_blk, p.predicted_tov,
            l.pts AS actual_pts, l.reb AS actual_reb, l.ast AS actual_ast,
            l.stl AS actual_stl, l.blk AS actual_blk, l.tov AS actual_tov
        FROM predictions p
        JOIN player_game_logs l
            ON p.player_name = l.player_name
            AND p.game_date = l.game_date
        WHERE l.season = ?
    """
    params = [season]
    if player_name:
        query += " AND p.player_name = ?"
        params.append(player_name)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        print("No matched predictions found yet.")
        return df

    # Compute errors
    for stat in TARGETS:
        pred_col = f"predicted_{stat}"
        actual_col = f"actual_{stat}"
        if pred_col in df.columns and actual_col in df.columns:
            df[f"error_{stat}"] = df[pred_col] - df[actual_col]
            df[f"abs_error_{stat}"] = df[f"error_{stat}"].abs()

    return df


def print_evaluation_summary(df: pd.DataFrame):
    """Print MAE per stat and overall accuracy summary."""
    if df.empty:
        return

    print("\n" + "=" * 55)
    print("  Prediction Accuracy Summary")
    print("=" * 55)
    for stat in TARGETS:
        col = f"abs_error_{stat}"
        if col in df.columns:
            mae = df[col].mean()
            print(f"  {stat.upper():4s}  MAE: {mae:.2f}")

    print(f"\n  Total games evaluated: {len(df)}")
    print("=" * 55)


def compare_vs_vegas(game_date: str = None) -> pd.DataFrame:
    """
    Compare our predictions vs Vegas prop lines for the same games.
    Lower MAE than Vegas = we have edge.
    """
    conn = get_connection()

    query = """
        SELECT
            p.player_name,
            p.game_date,
            p.predicted_pts,
            pr.line AS vegas_pts,
            l.pts AS actual_pts
        FROM predictions p
        JOIN prop_lines pr
            ON pr.player_name LIKE '%' || p.player_name || '%'
            AND pr.game_date = p.game_date
            AND pr.stat = 'pts'
        JOIN player_game_logs l
            ON l.player_name = p.player_name
            AND l.game_date = p.game_date
    """
    if game_date:
        query += f" WHERE p.game_date = '{game_date}'"

    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No Vegas comparison data available yet.")
        return df

    df["our_error"] = (df["predicted_pts"] - df["actual_pts"]).abs()
    df["vegas_error"] = (df["vegas_pts"] - df["actual_pts"]).abs()

    print("\n" + "=" * 55)
    print("  Our Model vs Vegas (PTS)")
    print("=" * 55)
    print(f"  Our MAE:    {df['our_error'].mean():.2f}")
    print(f"  Vegas MAE:  {df['vegas_error'].mean():.2f}")
    edge = df["vegas_error"].mean() - df["our_error"].mean()
    print(f"  Edge:       {edge:+.2f} ({'better' if edge > 0 else 'worse'} than Vegas)")
    print("=" * 55)

    return df


if __name__ == "__main__":
    df = compare_vs_actual()
    print_evaluation_summary(df)
    compare_vs_vegas()
