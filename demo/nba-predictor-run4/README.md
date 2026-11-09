# 🏀 NBA Player Performance Predictor

A machine learning system that predicts NBA player stat lines for upcoming games using historical performance, matchup data, team defensive metrics, rest/travel factors, and real-time news sentiment.

## What It Predicts

For any NBA player vs any opponent, the model predicts:
- **Points, Rebounds, Assists, Steals, Blocks, Turnovers**

## How It Works

```
NBA Stats API + NewsAPI + Odds API
          ↓
     SQLite Database
          ↓
   Feature Engineering
   - Rolling averages (5/10/20 games)
   - Head-to-head history vs opponent
   - Performance vs similar defensive teams
   - Rest days, back-to-backs, travel fatigue
   - Altitude (Denver road games)
   - News sentiment + injury flags
   - Vegas prop lines as market baseline
          ↓
   XGBoost Models (one per stat)
          ↓
   FastAPI + Streamlit Dashboard
```

## Quickstart

### 1. Clone and set up environment

```bash
git clone https://github.com/atinm12/nba-predictor.git
cd nba-predictor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Player game logs are cached locally by `cache_player_logs()` in `data/cache.py`, so repeat runs skip the NBA API.

### 2. Configure API keys (optional but recommended)

```bash
cp .env.example .env
```

Edit `.env` and add:
- `NEWS_API_KEY` — free at [newsapi.org](https://newsapi.org)
- `ODDS_API_KEY` — free tier at [the-odds-api.com](https://the-odds-api.com)
- `WEATHER_API_KEY` — for outdoor travel conditions

The project works without these keys — you just won't get news sentiment or Vegas line features.

### 3. Run the pipeline (pulls data + trains models)

```bash
# Quick run (50 players, good for first test)
python pipeline.py --fast

# Full run (all active NBA players)
python pipeline.py
```

### 4. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

### 5. Or use the API

```bash
uvicorn api.main:app --reload
# Visit http://localhost:8000/docs for interactive API docs
```

## Project Structure

```
nba-predictor/
├── data/
│   ├── ingestion/
│   │   ├── nba_stats.py      # Player logs + team stats via nba_api
│   │   ├── schedule.py       # Game schedule + rest day calculation
│   │   ├── news.py           # NewsAPI + sentiment scoring
│   │   └── odds.py           # Vegas prop lines
│   └── database.py           # SQLite schema + query helpers
├── features/
│   ├── player_features.py    # Rolling averages, home/away splits
│   ├── matchup_features.py   # Head-to-head + similar team history
│   ├── game_features.py      # Rest, travel, altitude, back-to-back
│   ├── news_features.py      # NLP sentiment wrapper
│   └── build_features.py     # Master feature vector builder
├── models/
│   ├── train.py              # XGBoost training (one model per stat)
│   ├── predict.py            # Inference + prediction logging
│   ├── evaluate.py           # Accuracy vs actuals + vs Vegas
│   └── saved/                # Trained model files (git-ignored)
├── api/
│   └── main.py               # FastAPI endpoints
├── dashboard/
│   └── app.py                # Streamlit UI
├── pipeline.py               # End-to-end orchestration
└── requirements.txt
```

## Using the features directly

```python
from features.player_features import compute_rolling_averages, get_streak_stats
from features.matchup_features import get_vs_similar_teams

rolling = compute_rolling_averages(df, windows=[3, 7])
similar = get_vs_similar_teams("LeBron James")
```

## Evaluating the Model

After games are played, run:

```bash
python models/evaluate.py
```

This compares predictions vs actual outcomes and vs Vegas prop lines using `compare_vs_vegas()` in `models/evaluate.py`. Beating Vegas MAE on points is a meaningful benchmark.

## Tech Stack

| Layer | Tool |
|---|---|
| Data | `nba_api`, `NewsAPI`, `The Odds API` |
| Storage | SQLite via `SQLAlchemy` |
| Features | `pandas`, `numpy` |
| NLP | `TextBlob` |
| Models | `XGBoost` + `LightGBM` ensemble |
| API | `FastAPI` |
| Dashboard | `Streamlit` + `Plotly` |
