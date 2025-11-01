import streamlit as st
from db.database import Database
from db.services import GameService, HistoryService
from utils.auth import login_required

DB = Database()
svc = GameService(DB)
hist = HistoryService(DB)

@login_required
def page():
    st.title("🗂️ History")
    games = svc.list_games()

    if not games:
        st.info("No games yet.")
        return

    labels = [f"#{g.id} — {g.status} — {g.created_at}" + (f" → {g.finished_at}" if g.finished_at else "") for g in games]
    idx = st.selectbox("Select a game", range(len(games)), format_func=lambda i: labels[i])
    game = games[idx]

    players, _ = svc.get_scoreboard(game.id)

    st.subheader("Scoreboard")
    st.table({
        "Player": [p.name for p in players],
        "Points": [p.points for p in players],
    })

    with st.expander("Turns (chronological)"):
        rows = hist.list_turns(game.id)
        if rows:
            st.table({
                "When": [r["created_at"] for r in rows],
                "Player": [r["name"] for r in rows],
                "Δ": [r["delta"] for r in rows],
            })
        else:
            st.caption("No turns recorded yet.")

    cols = st.columns(2)
    if game.status == "active":
        if cols[0].button("▶️ Resume this game", type="primary"):
            st.session_state["current_game_id"] = game.id
            try:
                st.switch_page("pages/3_Game.py")
            except Exception:
                st.toast("Open the Game page to continue.")
    else:
        cols[0].caption("This game is finished.")

page()