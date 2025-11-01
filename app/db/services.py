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
        self.turn_repo = TurnRepository(db)  # renamed to make it clear

    def list_games(self):
        return self.games.list()

    def scoreboard(self, game_id: int):
        return self.players.list(game_id)

    def list_turns(self, game_id: int):  # renamed
        return self.turn_repo.list_for_game(game_id)
