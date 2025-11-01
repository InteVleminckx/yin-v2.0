# yin-v2.0

# Yin — Streamlit + SQLite App (OOP scaffold)

Below is a complete, minimal-but-robust scaffold you can run locally. It’s organized for maintainability (repositories/services pattern), uses SQLite with WAL mode, has a login gate, multipage navigation, and a resumable game with history + scoreboard.

---

## Project structure

```
yin_app/
├── streamlit_app.py                 # Entry point (login + router helpers)
├── requirements.txt
├── db/
│   ├── database.py                  # DB engine + migrations/DDL
│   ├── repositories.py              # Repositories (Users, Games, GamePlayers, Turns)
│   └── services.py                  # Business logic (AuthService, GameService, HistoryService)
├── utils/
│   ├── auth.py                      # Password hashing + login guard decorator
│   └── exceptions.py                # AppError hierarchy
└── pages/
    ├── 1_Home.py                    # Add players & start game
    ├── 2_History.py                 # List games, view scoreboard, resume unfinished
    └── 3_Game.py                    # Scoreboard + add points, finish game
```

> **Run**: `pip install -r requirements.txt` then `streamlit run streamlit_app.py`

---

## requirements.txt

```txt
streamlit>=1.29
```

> (No external crypto libs; uses Python stdlib `hashlib` for PBKDF2.)

---

## db/database.py

```python
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "yin.db"

class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._ensure_db()

    def _ensure_db(self) -> None:
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=NORMAL;")
            con.execute("PRAGMA foreign_keys=ON;")
            # --- Schema ---
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY,
                  username TEXT UNIQUE NOT NULL,
                  pwd_hash TEXT NOT NULL,
                  salt TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS games (
                  id INTEGER PRIMARY KEY,
                  status TEXT NOT NULL CHECK(status IN ('active','finished')),
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  finished_at TEXT
                );

                -- We keep names per-game to avoid global collisions and allow reuse
                CREATE TABLE IF NOT EXISTS game_players (
                  id INTEGER PRIMARY KEY,
                  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  points INTEGER NOT NULL DEFAULT 0,
                  UNIQUE(game_id, name)
                );

                CREATE TABLE IF NOT EXISTS turns (
                  id INTEGER PRIMARY KEY,
                  game_player_id INTEGER NOT NULL REFERENCES game_players(id) ON DELETE CASCADE,
                  delta INTEGER NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA busy_timeout=3000;")
            yield con
        finally:
            con.close()
```

---

## db/repositories.py

```python
from __future__ import annotations
from typing import List, Optional, Sequence
from dataclasses import dataclass
from .database import Database

@dataclass
class User:
    id: int
    username: str
    pwd_hash: str
    salt: str

@dataclass
class Game:
    id: int
    status: str
    created_at: str
    finished_at: Optional[str]

@dataclass
class GamePlayer:
    id: int
    game_id: int
    name: str
    points: int

class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return User(**row) if row else None

    def create(self, username: str, pwd_hash: str, salt: str) -> User:
        with self.db.connect() as con:
            cur = con.execute(
                "INSERT INTO users(username, pwd_hash, salt) VALUES(?,?,?)",
                (username, pwd_hash, salt),
            )
            row = con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
            return User(**row)

class GameRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self) -> Game:
        with self.db.connect() as con:
            cur = con.execute("INSERT INTO games(status) VALUES('active')")
            row = con.execute("SELECT * FROM games WHERE id=?", (cur.lastrowid,)).fetchone()
            return Game(**row)

    def list(self) -> List[Game]:
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM games ORDER BY created_at DESC").fetchall()
            return [Game(**r) for r in rows]

    def get(self, game_id: int) -> Optional[Game]:
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
            return Game(**row) if row else None

    def finish(self, game_id: int) -> None:
        with self.db.connect() as con:
            con.execute(
                "UPDATE games SET status='finished', finished_at=datetime('now') WHERE id=?",
                (game_id,),
            )

class GamePlayerRepository:
    def __init__(self, db: Database):
        self.db = db

    def add_many(self, game_id: int, names: Sequence[str]) -> List[GamePlayer]:
        with self.db.connect() as con:
            ids = []
            for n in names:
                cur = con.execute(
                    "INSERT OR IGNORE INTO game_players(game_id, name) VALUES(?,?)",
                    (game_id, n.strip()),
                )
                ids.append(cur.lastrowid)
            rows = con.execute(
                "SELECT * FROM game_players WHERE game_id=? ORDER BY name ASC",
                (game_id,),
            ).fetchall()
            return [GamePlayer(**r) for r in rows]

    def list(self, game_id: int) -> List[GamePlayer]:
        with self.db.connect() as con:
            rows = con.execute(
                "SELECT * FROM game_players WHERE game_id=? ORDER BY points ASC, name ASC",
                (game_id,),
            ).fetchall()
            return [GamePlayer(**r) for r in rows]

    def get_by_name(self, game_id: int, name: str) -> Optional[GamePlayer]:
        with self.db.connect() as con:
            row = con.execute(
                "SELECT * FROM game_players WHERE game_id=? AND name=?",
                (game_id, name),
            ).fetchone()
            return GamePlayer(**row) if row else None

    def add_points(self, game_player_id: int, delta: int) -> None:
        with self.db.connect() as con:
            con.execute(
                "UPDATE game_players SET points = points + ? WHERE id=?",
                (delta, game_player_id),
            )

class TurnRepository:
    def __init__(self, db: Database):
        self.db = db

    def record(self, game_player_id: int, delta: int) -> None:
        with self.db.connect() as con:
            con.execute(
                "INSERT INTO turns(game_player_id, delta) VALUES(?,?)",
                (game_player_id, delta),
            )

    def list_for_game(self, game_id: int):
        with self.db.connect() as con:
            rows = con.execute(
                """
                SELECT t.id, gp.name, t.delta, t.created_at
                FROM turns t
                JOIN game_players gp ON gp.id = t.game_player_id
                WHERE gp.game_id=?
                ORDER BY t.created_at ASC
                """,
                (game_id,),
            ).fetchall()
            return rows
```

---

## utils/exceptions.py

```python
class AppError(Exception):
    pass

class AuthError(AppError):
    pass

class NotFoundError(AppError):
    pass
```

---

## utils/auth.py

```python
from __future__ import annotations
import os, secrets, hashlib
from functools import wraps
import streamlit as st
from db.repositories import UserRepository
from db.database import Database
from .exceptions import AuthError

ITERATIONS = 150_000

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return dk.hex()

def create_user_if_missing(db: Database, username: str, plain_password: str) -> None:
    repo = UserRepository(db)
    if repo.get_by_username(username):
        return
    salt = secrets.token_bytes(16)
    pwd_hash = _hash_password(plain_password, salt)
    repo.create(username, pwd_hash, salt.hex())

def verify_password(db: Database, username: str, password: str) -> bool:
    repo = UserRepository(db)
    user = repo.get_by_username(username)
    if not user:
        return False
    salt = bytes.fromhex(user.salt)
    return _hash_password(password, salt) == user.pwd_hash

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("user"):
            st.error("Please log in to view this page.")
            st.stop()
        return fn(*args, **kwargs)
    return wrapper

# Bootstrapping default admin from Streamlit secrets or fallback
# Add in .streamlit/secrets.toml: ADMIN_USERNAME="admin" ADMIN_PASSWORD="strongpass"

def bootstrap_admin(db: Database):
    username = st.secrets.get("ADMIN_USERNAME", "admin")
    password = st.secrets.get("ADMIN_PASSWORD", "changeme")
    create_user_if_missing(db, username, password)
```

---

## db/services.py

```python
from __future__ import annotations
from typing import List
from .database import Database
from .repositories import GameRepository, GamePlayerRepository, TurnRepository
from utils.exceptions import NotFoundError, AppError

class GameService:
    def __init__(self, db: Database):
        self.db = db
        self.games = GameRepository(db)
        self.players = GamePlayerRepository(db)
        self.turns = TurnRepository(db)

    def create_game(self, names: List[str]) -> int:
        names = [n.strip() for n in names if n and n.strip()]
        if not names:
            raise AppError("Please provide at least one player name.")
        game = self.games.create()
        self.players.add_many(game.id, names)
        return game.id

    def list_games(self):
        return self.games.list()

    def get_scoreboard(self, game_id: int):
        game = self.games.get(game_id)
        if not game:
            raise NotFoundError("Game not found.")
        return self.players.list(game_id), game

    def add_points(self, game_id: int, player_name: str, delta: int):
        gp = self.players.get_by_name(game_id, player_name)
        if not gp:
            raise NotFoundError("Player not found for this game.")
        self.turns.record(gp.id, delta)
        self.players.add_points(gp.id, delta)

    def finish_game(self, game_id: int):
        if not self.games.get(game_id):
            raise NotFoundError("Game not found.")
        self.games.finish(game_id)

class HistoryService:
    def __init__(self, db: Database):
        self.db = db
        self.games = GameRepository(db)
        self.players = GamePlayerRepository(db)
        self.turns = TurnRepository(db)

    def list_games(self):
        return self.games.list()

    def scoreboard(self, game_id: int):
        return self.players.list(game_id)

    def turns(self, game_id: int):
        return self.turns.list_for_game(game_id)
```

---

## streamlit_app.py (entry)

```python
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

st.page_link("pages/1_Home.py", label="Home", icon="🏠")
st.page_link("pages/2_History.py", label="History", icon="🗂️")
st.page_link("pages/3_Game.py", label="Game", icon="🎮")
```

---

## pages/1_Home.py

```python
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
```

---

## pages/2_History.py

```python
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
        rows = hist.turns(game.id)
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
```

---

## pages/3_Game.py

```python
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
```

---

## Notes & Next steps

* **Security (local)**: This uses PBKDF2-HMAC (SHA-256) with per-user random salt. For a local-only app, this is sufficient. You can change the default admin by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.streamlit/secrets.toml`.
* **Resumability**: Selecting a game in **History** sets `current_game_id` and routes you to **Game**.
* **Auditability**: Every score change is recorded in `turns` for a complete history.
* **Error handling**: Repository/service layers raise concise exceptions; pages catch and display them via Streamlit UI.
* **Extensibility**: You can add rules of Yin later (e.g., validation of moves) inside `GameService`.
* **Multipage nav**: We use `st.switch_page` where available and still provide sidebar links.

```
```
