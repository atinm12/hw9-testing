"""
Trains one XGBoost model per stat (pts, reb, ast, stl, blk, tov).
Saves models to models/saved/.
Prints evaluation metrics on held-out test set.
"""

import pandas as pd
import numpy as np
import pickle
import sys
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

sys.path.append(str(Path(__file__).parent.parent))
from features.build_features import build_training_rows

TARGETS = ["pts", "reb", "ast", "stl", "blk", "tov"]
MODELS_DIR = Path(__file__).parent / "saved"
MODELS_DIR.mkdir(exist_ok=True)

# Features to drop when training (not predictive inputs)
DROP_COLS = ["player_name", "game_date"] + [f"target_{t}" for t in TARGETS]


def train_models(season: str = "2024-25"):
    print("=" * 60)
    print("NBA Predictor — Model Training")
    print("=" * 60)

    # Build training data
    rows = build_training_rows(season)
    if not rows:
        print("No training data found. Run data ingestion first.")
        return

    df = pd.DataFrame(rows)
    print(f"\nTotal training rows: {len(df)}")

    # Drop rows with missing targets
    for t in TARGETS:
        df = df[df[f"target_{t}"].notna()]

    # Fill missing feature values with column median
    feature_cols = [c for c in df.columns if c not in DROP_COLS]
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())

    results = {}

    for stat in TARGETS:
        print(f"\n--- Training model for: {stat.upper()} ---")
        target_col = f"target_{stat}"

        X = df[feature_cols]
        y = df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        print(f"  MAE: {mae:.3f}  |  R²: {r2:.3f}")

        # Save model
        model_path = MODELS_DIR / f"model_{stat}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump({"model": model, "feature_cols": feature_cols}, f)
        print(f"  Saved to {model_path}")

        results[stat] = {"mae": mae, "r2": r2}

    # Save feature column list
    with open(MODELS_DIR / "feature_cols.pkl", "wb") as f:
        pickle.dump(feature_cols, f)

    print("\n" + "=" * 60)
    print("Training Complete — Summary")
    print("=" * 60)
    for stat, res in results.items():
        print(f"  {stat.upper():4s}  MAE: {res['mae']:.3f}  R²: {res['r2']:.3f}")

    return results


if __name__ == "__main__":
    train_models()
