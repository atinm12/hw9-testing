"""
Generates predictions for a player's upcoming game.
Loads saved XGBoost models and runs inference.
"""

import pickle
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from features.build_features import build_feature_vector
from data.database import get_connection

TARGETS = ["pts", "reb", "ast", "stl", "blk", "tov"]
MODELS_DIR = Path(__file__).parent / "saved"


def load_models() -> dict:
    """Load all saved stat models."""
    models = {}
    for stat in TARGETS:
        path = MODELS_DIR / f"model_{stat}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                models[stat] = pickle.load(f)
        else:
            print(f"  Warning: model for {stat} not found at {path}")
    return models


def predict_game(
    player_name: str,
    opponent_abbreviation: str,
    game_date: str = None,
    is_home: bool = True,
    season: str = "2024-25",
    refresh_news: bool = True,
) -> dict:
    """
    Predict a player's stat line for a given game.

    Returns:
        dict with predicted stats + confidence context
    """
    if game_date is None:
        game_date = datetime.today().strftime("%Y-%m-%d")

    models = load_models()
    if not models:
        return {"error": "No trained models found. Run models/train.py first."}

    # Build feature vector
    print(f"Building features for {player_name} vs {opponent_abbreviation} on {game_date}...")
    features = build_feature_vector(
        player_name=player_name,
        opponent_abbreviation=opponent_abbreviation,
        game_date=game_date,
        is_home=is_home,
        season=season,
        refresh_news=refresh_news,
    )

    predictions = {
        "player_name": player_name,
        "opponent": opponent_abbreviation,
        "game_date": game_date,
        "is_home": is_home,
        "predictions": {},
        "context": {},
    }

    for stat, model_data in models.items():
        model = model_data["model"]
        feature_cols = model_data["feature_cols"]

        # Align features to training columns
        row = {col: features.get(col, 0.0) for col in feature_cols}
        X = pd.DataFrame([row])[feature_cols]
        X = X.fillna(0.0)

        pred = float(model.predict(X)[0])
        pred = max(0.0, round(pred, 1))  # no negative stats
        predictions["predictions"][stat] = pred

    # Add context features for display
    predictions["context"] = {
        "rest_days": features.get("rest_days", "N/A"),
        "is_back_to_back": bool(features.get("is_back_to_back", 0)),
        "opp_def_rating": features.get("opp_def_rating", "N/A"),
        "opp_pace": features.get("opp_pace", "N/A"),
        "injury_flag": bool(features.get("injury_flag", 0)),
        "avg_sentiment": round(features.get("avg_sentiment", 0.0), 3),
        "altitude_game": bool(features.get("altitude_game", 0)),
        "pts_trend": features.get("pts_trend", 0.0),
        "prop_line_pts": features.get("prop_line_pts", -1),
        "prop_line_reb": features.get("prop_line_reb", -1),
        "prop_line_ast": features.get("prop_line_ast", -1),
    }

    # Save prediction to DB
    _save_prediction(predictions)

    return predictions


def _save_prediction(pred: dict):
    """Log prediction to the predictions table."""
    try:
        conn = get_connection()
        c = conn.cursor()
        p = pred["predictions"]
        c.execute("""
            INSERT INTO predictions
            (player_name, opponent_abbreviation, game_date,
             predicted_pts, predicted_reb, predicted_ast,
             predicted_stl, predicted_blk, predicted_tov, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            pred["player_name"],
            pred["opponent"],
            pred["game_date"],
            p.get("pts", 0),
            p.get("reb", 0),
            p.get("ast", 0),
            p.get("stl", 0),
            p.get("blk", 0),
            p.get("tov", 0),
            datetime.now().isoformat(),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  Could not save prediction: {e}")


def print_prediction(pred: dict):
    """Pretty-print a prediction result."""
    if "error" in pred:
        print(f"Error: {pred['error']}")
        return

    ctx = pred["context"]
    p = pred["predictions"]

    print("\n" + "=" * 55)
    print(f"  {pred['player_name']} vs {pred['opponent']}")
    print(f"  {pred['game_date']}  |  {'HOME' if pred['is_home'] else 'AWAY'}")
    print("=" * 55)
    print(f"  PTS: {p.get('pts', '—'):>5}    REB: {p.get('reb', '—'):>5}    AST: {p.get('ast', '—'):>5}")
    print(f"  STL: {p.get('stl', '—'):>5}    BLK: {p.get('blk', '—'):>5}    TOV: {p.get('tov', '—'):>5}")
    print("-" * 55)
    print(f"  Rest days:       {ctx['rest_days']}")
    print(f"  Back-to-back:    {'YES ⚠️' if ctx['is_back_to_back'] else 'No'}")
    print(f"  Opp Def Rating:  {ctx['opp_def_rating']}")
    print(f"  Opp Pace:        {ctx['opp_pace']}")
    print(f"  Altitude game:   {'YES' if ctx['altitude_game'] else 'No'}")
    print(f"  Injury flag:     {'YES ⚠️' if ctx['injury_flag'] else 'No'}")
    print(f"  News sentiment:  {ctx['avg_sentiment']}")
    print(f"  PTS trend:       {ctx['pts_trend']:+.1f} (last 5 vs last 20)")
    if ctx["prop_line_pts"] > 0:
        print(f"  Vegas PTS line:  {ctx['prop_line_pts']}")
    print("=" * 55)


if __name__ == "__main__":
    result = predict_game(
        player_name="LeBron James",
        opponent_abbreviation="GSW",
        is_home=True,
    )
    print_prediction(result)
