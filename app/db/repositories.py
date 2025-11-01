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