import streamlit as st
from db.database import Database
from utils.auth import bootstrap_admin, verify_password

st.set_page_config(page_title="Yin", page_icon="🌓", layout="centered")

# Initialize DB and default admin
DB = Database()
bootstrap_admin(DB)

# Simple top bar (shows user + logout)
if st.session_state.get("user"):
    with st.container(border=True):
        cols = st.columns([1,1,1])
        cols[0].markdown(f"**Logged in as:** `{st.session_state['user']}`")
        if cols[2].button("Log out"):
            st.session_state.clear()
            st.rerun()

st.title("🌓 Yin")

st.write("Welcome! Use the sidebar to navigate. Please log in to access pages.")

# Login panel (also accessible via Pages/0_Login.py if you prefer)
if not st.session_state.get("user"):
    st.subheader("Login")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", value="")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            if verify_password(DB, username, password):
                st.session_state["user"] = username
                st.success("Logged in!")
                try:
                    st.switch_page("pages/1_Home.py")  # Streamlit ≥1.25
                except Exception:
                    pass
                st.rerun()
            else:
                st.error("Invalid credentials.")
        except Exception as e:
            st.error(f"Login failed: {e}")

st.page_link("pages/home.py", label="Home", icon="🏠")
st.page_link("pages/history.py", label="History", icon="🗂️")
st.page_link("pages/game.py", label="Game", icon="🎮")