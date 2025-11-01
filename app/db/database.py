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