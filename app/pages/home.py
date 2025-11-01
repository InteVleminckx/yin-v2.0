import streamlit as st
from db.database import Database
from db.services import GameService
from utils.auth import login_required

DB = Database()
svc = GameService(DB)

@login_required
def page():
    st.title("🏠 Home")
    st.caption("Add players below, then start a new game.")

    players = st.session_state.setdefault("pending_players", [])

    with st.form("add_player", clear_on_submit=True):
        name = st.text_input("Player name", placeholder="Type a name and press Add")
        add = st.form_submit_button("Add")
    if add and name:
        if name in players:
            st.warning("Name already added.")
        else:
            players.append(name)
            st.success(f"Added {name}.")

    if players:
        st.write("**Players queued:**")
        st.write(", ".join(players))
        if st.button("🟢 Start game", type="primary"):
            try:
                game_id = svc.create_game(players)
                st.session_state["current_game_id"] = game_id
                st.session_state["pending_players"] = []
                try:
                    st.switch_page("pages/3_Game.py")
                except Exception:
                    st.success("Game created. Open the Game page.")
            except Exception as e:
                st.error(f"Could not create game: {e}")
    else:
        st.info("No players yet.")

page()