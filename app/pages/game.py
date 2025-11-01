import streamlit as st
from db.database import Database
from db.services import GameService
from utils.auth import login_required

DB = Database()
svc = GameService(DB)

@login_required
def page():
    st.title("🎮 Game")

    game_id = st.session_state.get("current_game_id")
    if not game_id:
        st.info("No active game in session. Open History to resume or Home to start a new one.")
        return

    try:
        players, game = svc.get_scoreboard(game_id)
    except Exception as e:
        st.error(str(e))
        return

    if game.status != "active":
        st.warning("This game is finished. Open History or start a new game.")

    st.subheader(f"Game #{game.id} — {game.status}")

    # Scoreboard (lowest to highest)
    st.write("**Scoreboard (asc):**")
    st.table({
        "Player": [p.name for p in players],
        "Points": [p.points for p in players],
    })

    st.divider()
    st.subheader("Add points")

    names = [p.name for p in players]
    if not names:
        st.info("No players in this game.")
        return

    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        name = st.selectbox("Player", names)
    with c2:
        delta = st.number_input("Δ points", step=1, value=1)
    with c3:
        add = st.button("Save", type="primary")

    if add:
        try:
            svc.add_points(game_id, name, int(delta))
            st.success(f"Added {int(delta)} to {name}.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add points: {e}")

    st.divider()
    if game.status == "active":
        if st.button("🏁 Finish game", type="secondary"):
            try:
                svc.finish_game(game_id)
                st.success("Game finished.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not finish game: {e}")

page()