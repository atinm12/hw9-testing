"""
Streamlit dashboard for the NBA Predictor.
Run with: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.append(str(Path(__file__).parent.parent))
from models.predict import predict_game
from data.database import get_connection

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="NBA Predictor",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helpers ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_players():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT player_name FROM player_game_logs ORDER BY player_name")
    rows = c.fetchall()
    conn.close()
    return [r["player_name"] for r in rows]

@st.cache_data(ttl=300)
def get_teams():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT team_abbreviation FROM team_stats ORDER BY team_abbreviation")
    rows = c.fetchall()
    conn.close()
    return [r["team_abbreviation"] for r in rows]

@st.cache_data(ttl=60)
def get_recent_logs(player_name: str, n: int = 15):
    conn = get_connection()
    query = """
        SELECT game_date, opponent_abbreviation, home_away,
               pts, reb, ast, stl, blk, tov, min
        FROM player_game_logs
        WHERE player_name = ?
        ORDER BY game_date DESC LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(player_name, n))
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_news(player_name: str):
    conn = get_connection()
    query = """
        SELECT title, published_at, source, sentiment_score, injury_flag
        FROM news_articles WHERE player_name = ?
        ORDER BY published_at DESC LIMIT 8
    """
    df = pd.read_sql_query(query, conn, params=(player_name,))
    conn.close()
    return df

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🏀 NBA Predictor")
    st.markdown("---")

    players = get_players()
    teams = get_teams()

    if not players:
        st.warning("No data yet. Run `python pipeline.py` first.")
        st.stop()

    player_name = st.selectbox("Select Player", players)
    opponent = st.selectbox("Opponent Team", teams)
    game_date = st.date_input("Game Date", value=date.today())
    is_home = st.radio("Home or Away?", ["Home", "Away"]) == "Home"
    refresh_news = st.checkbox("Refresh news", value=False)

    predict_btn = st.button("🔮 Predict", use_container_width=True)

# ── Main ──────────────────────────────────────────────────────
st.title(f"NBA Player Performance Predictor")

if predict_btn:
    with st.spinner(f"Predicting {player_name} vs {opponent}..."):
        result = predict_game(
            player_name=player_name,
            opponent_abbreviation=opponent,
            game_date=str(game_date),
            is_home=is_home,
            refresh_news=refresh_news,
        )

    if "error" in result:
        st.error(result["error"])
    else:
        p = result["predictions"]
        ctx = result["context"]

        # ── Prediction cards ──────────────────────────────────
        st.subheader(f"📊 {player_name} vs {opponent} — {game_date}")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("PTS", p.get("pts", "—"))
        col2.metric("REB", p.get("reb", "—"))
        col3.metric("AST", p.get("ast", "—"))
        col4.metric("STL", p.get("stl", "—"))
        col5.metric("BLK", p.get("blk", "—"))
        col6.metric("TOV", p.get("tov", "—"))

        st.markdown("---")

        # ── Context flags ─────────────────────────────────────
        st.subheader("🔍 Game Context")
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Rest Days", ctx["rest_days"])
        c2.metric("Back-to-Back", "⚠️ YES" if ctx["is_back_to_back"] else "No")
        c3.metric("Opp Def Rating", ctx["opp_def_rating"])
        c4.metric("Opp Pace", ctx["opp_pace"])

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Altitude Game", "YES" if ctx["altitude_game"] else "No")
        c6.metric("Injury Flag", "⚠️ YES" if ctx["injury_flag"] else "No")
        c7.metric("News Sentiment", ctx["avg_sentiment"])
        c8.metric("PTS Trend (5v20)", f"{ctx['pts_trend']:+.1f}")

        # Vegas comparison
        if ctx["prop_line_pts"] > 0:
            st.markdown("---")
            st.subheader("💰 vs Vegas Lines")
            v1, v2, v3 = st.columns(3)
            v1.metric("Our PTS", p.get("pts"), delta=round(p.get("pts", 0) - ctx["prop_line_pts"], 1))
            v2.metric("Vegas PTS Line", ctx["prop_line_pts"])
            v3.metric("Difference", round(p.get("pts", 0) - ctx["prop_line_pts"], 1))

st.markdown("---")

# ── Recent Performance Chart ──────────────────────────────────
if player_name:
    st.subheader(f"📈 {player_name} — Last 15 Games")
    logs = get_recent_logs(player_name)

    if not logs.empty:
        logs = logs.sort_values("game_date")
        fig = go.Figure()
        for stat, color in [("pts", "#FF6B35"), ("reb", "#4ECDC4"), ("ast", "#45B7D1")]:
            fig.add_trace(go.Scatter(
                x=logs["game_date"],
                y=logs[stat],
                name=stat.upper(),
                mode="lines+markers",
                line=dict(color=color, width=2),
            ))
        fig.update_layout(
            xaxis_title="Game Date",
            yaxis_title="Stats",
            height=350,
            legend=dict(orientation="h"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Recent game log table
        st.subheader("📋 Game Log")
        display_df = logs[["game_date", "opponent_abbreviation", "home_away",
                            "pts", "reb", "ast", "stl", "blk", "tov", "min"]].copy()
        display_df.columns = ["Date", "Opponent", "H/A", "PTS", "REB", "AST", "STL", "BLK", "TOV", "MIN"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    else:
        st.info("No game log data yet for this player.")

    # ── News Section ──────────────────────────────────────────
    st.markdown("---")
    st.subheader(f"📰 Recent News — {player_name}")
    news = get_news(player_name)

    if not news.empty:
        for _, article in news.iterrows():
            sentiment = article["sentiment_score"]
            injury = article["injury_flag"]
            emoji = "🔴" if injury else ("🟢" if sentiment > 0.1 else ("🔴" if sentiment < -0.1 else "🟡"))
            with st.expander(f"{emoji} {article['title'][:90]}..."):
                st.write(f"**Source:** {article['source']}")
                st.write(f"**Published:** {article['published_at'][:10]}")
                st.write(f"**Sentiment:** {round(sentiment, 3)} | **Injury Flag:** {'Yes ⚠️' if injury else 'No'}")
    else:
        st.info("No news articles found. Add a NEWS_API_KEY in your .env file.")
