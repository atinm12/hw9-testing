"""
FastAPI backend — serves predictions and evaluation data.
Run with: uvicorn api.main:app --reload
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from models.predict import predict_game
from models.evaluate import compare_vs_actual, compare_vs_vegas
from data.database import get_connection

app = FastAPI(
    title="NBA Predictor API",
    description="Predicts NBA player stat lines using ML, matchup history, and news sentiment.",
    version="1.0.0",
)


class PredictionRequest(BaseModel):
    player_name: str
    opponent_abbreviation: str
    game_date: Optional[str] = None
    is_home: Optional[bool] = True
    season: Optional[str] = "2024-25"
    refresh_news: Optional[bool] = False


@app.get("/")
def root():
    return {"message": "NBA Predictor API is running.", "docs": "/docs"}


@app.post("/predict")
def predict(req: PredictionRequest):
    """Generate a stat prediction for a player in an upcoming game."""
    try:
        result = predict_game(
            player_name=req.player_name,
            opponent_abbreviation=req.opponent_abbreviation,
            game_date=req.game_date or datetime.today().strftime("%Y-%m-%d"),
            is_home=req.is_home,
            season=req.season,
            refresh_news=req.refresh_news,
        )
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/players")
def list_players(search: str = Query(default="", description="Search by name")):
    """List all players in the database."""
    conn = get_connection()
    c = conn.cursor()
    if search:
        c.execute("""
            SELECT DISTINCT player_name FROM player_game_logs
            WHERE player_name LIKE ? ORDER BY player_name
        """, (f"%{search}%",))
    else:
        c.execute("SELECT DISTINCT player_name FROM player_game_logs ORDER BY player_name")
    rows = c.fetchall()
    conn.close()
    return {"players": [r["player_name"] for r in rows]}


@app.get("/teams")
def list_teams():
    """List all teams in the database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT team_abbreviation, team_name FROM team_stats ORDER BY team_abbreviation")
    rows = c.fetchall()
    conn.close()
    return {"teams": [{"abbreviation": r["team_abbreviation"], "name": r["team_name"]} for r in rows]}


@app.get("/player/{player_name}/stats")
def player_stats(player_name: str, season: str = "2024-25", last_n: int = 10):
    """Return recent game logs for a player."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT game_date, opponent_abbreviation, home_away, pts, reb, ast, stl, blk, tov, min
        FROM player_game_logs
        WHERE player_name = ? AND season = ?
        ORDER BY game_date DESC
        LIMIT ?
    """, (player_name, season, last_n))
    rows = c.fetchall()
    conn.close()
    return {"player": player_name, "games": [dict(r) for r in rows]}


@app.get("/player/{player_name}/news")
def player_news(player_name: str):
    """Return recent news articles for a player."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT title, description, published_at, source, sentiment_score, injury_flag
        FROM news_articles
        WHERE player_name = ?
        ORDER BY published_at DESC
        LIMIT 10
    """, (player_name,))
    rows = c.fetchall()
    conn.close()
    return {"player": player_name, "articles": [dict(r) for r in rows]}


@app.get("/evaluate")
def evaluate(player_name: Optional[str] = None, season: str = "2024-25"):
    """Return prediction accuracy vs actual outcomes."""
    df = compare_vs_actual(player_name, season)
    if df.empty:
        return {"message": "No evaluation data available yet."}

    summary = {}
    for stat in ["pts", "reb", "ast", "stl", "blk", "tov"]:
        col = f"abs_error_{stat}"
        if col in df.columns:
            summary[stat] = round(float(df[col].mean()), 3)

    return {
        "total_games_evaluated": len(df),
        "mae_per_stat": summary,
        "records": df.head(20).to_dict(orient="records"),
    }


@app.get("/evaluate/vs-vegas")
def evaluate_vs_vegas():
    """Compare our PTS predictions vs Vegas prop lines."""
    df = compare_vs_vegas()
    if df.empty:
        return {"message": "No Vegas comparison data available yet."}

    return {
        "our_mae": round(float(df["our_error"].mean()), 3),
        "vegas_mae": round(float(df["vegas_error"].mean()), 3),
        "edge": round(float(df["vegas_error"].mean() - df["our_error"].mean()), 3),
        "sample_size": len(df),
    }
