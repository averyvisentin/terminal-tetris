"""
Database operations: connection management, high scores, game state persistence.
"""

import collections
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from .constants import DATABASE_FILE, DB_DIR
from .models import Game, Piece, SCOREBOARDS, ScoreBoard
from .settings import SETTINGS, SPEC_BY_KEY, sanitize_settings


@contextmanager
def db_connection():
    """Opens the database, commits on success, rolls back on error, and always closes."""
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_database() -> None:
    """Creates the database and tables if they don't exist."""
    import os

    os.makedirs(DB_DIR, exist_ok=True)
    with db_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, score INTEGER NOT NULL, time REAL NOT NULL, lines INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sprint_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, time REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS timed_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, score INTEGER NOT NULL, lines INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS garbage_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, time REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS saved_game (id INTEGER PRIMARY KEY, game_state TEXT NOT NULL)"
        )


def save_settings(settings_dict: dict) -> None:
    """Saves the entire settings dictionary to the database."""
    rows = [
        (key, json.dumps(value) if isinstance(value, dict) else str(value))
        for key, value in settings_dict.items()
    ]
    with db_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", rows
        )


def load_settings() -> None:
    """Loads all settings from the database into SETTINGS, applying defaults for anything
    missing or invalid. The first run writes the defaults to the database."""
    import json

    with db_connection() as conn:
        stored = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    SETTINGS.clear()
    SETTINGS.update(sanitize_settings(stored))
    if not stored:
        save_settings(SETTINGS)


def load_high_scores(board: ScoreBoard) -> List[Tuple]:
    """Returns the top rows as (*values, name), best first."""
    cols = ", ".join(board.value_cols + ("name",))
    with db_connection() as conn:
        cursor = conn.execute(
            f"SELECT {cols} FROM {board.table} ORDER BY {board.order_by}, id ASC LIMIT ?",
            (SETTINGS["MAX_SCORES"],),
        )
        return cursor.fetchall()


def is_new_record(board: ScoreBoard, game: Game) -> bool:
    """True if this game earns a place on the board."""
    if not board.qualifies(game):
        return False
    scores = load_high_scores(board)
    if len(scores) < SETTINGS["MAX_SCORES"]:
        return True
    worst_values = scores[-1][:-1]
    return board.rank(board.row_from_game(game)) > board.rank(worst_values)


def add_high_score(board: ScoreBoard, values: tuple, name: str) -> None:
    """Inserts one score and trims the table, in a single transaction."""
    cols = board.value_cols + ("name",)
    placeholders = ", ".join("?" * len(cols))
    with db_connection() as conn:
        conn.execute(
            f"INSERT INTO {board.table} ({', '.join(cols)}) VALUES ({placeholders})",
            (*values, name),
        )
        conn.execute(
            f"DELETE FROM {board.table} WHERE id NOT IN "
            f"(SELECT id FROM {board.table} ORDER BY {board.order_by}, id ASC LIMIT ?)",
            (SETTINGS["MAX_SCORES"],),
        )


def save_game_state(game: Game) -> None:
    """Serializes the game state and saves it to the database."""
    state = {
        "board": game.board,
        "score": game.score,
        "lines_cleared": game.lines_cleared,
        "level": game.level,
        "start_level": game.start_level,
        "elapsed_time": game.elapsed_time,
        "gamemode": game.gamemode,
        "current_piece": {
            "shape_name": game.current_piece.shape_name,
            "x": game.current_piece.x,
            "y": game.current_piece.y,
            "rotation": game.current_piece.rotation,
        },
        "hold_piece": {"shape_name": game.hold_piece.shape_name}
        if game.hold_piece
        else None,
        "can_hold": game.can_hold,
        "upcoming_pieces": list(game.upcoming_pieces),
        "bag": game.bag,
        "is_back_to_back": game.is_back_to_back,
    }
    with db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO saved_game (id, game_state) VALUES (1, ?)",
            (json.dumps(state),),
        )


def load_game_state() -> Optional[Game]:
    """Rebuilds a Game from the saved state, or returns None if there isn't a usable save."""
    with db_connection() as conn:
        row = conn.execute("SELECT game_state FROM saved_game WHERE id = 1").fetchone()
    if not row:
        return None
    try:
        state = json.loads(row[0])
        board = state["board"]
        level, lines = state["level"], state["lines_cleared"]
        # Saves made before 'start_level' existed: work it back out from level and lines.
        start_level = state.get("start_level", max(1, level - lines // 10))
        elapsed = float(state.get("elapsed_time", 0))

        game = Game(
            gamemode=state.get("gamemode", "standard"),
            start_level=start_level,
            width=len(board[0]),
            height=len(board),
        )
        game.board = board
        game.score = state["score"]
        game.lines_cleared = lines
        game.level = level
        game.can_hold = state["can_hold"]
        game.upcoming_pieces = collections.deque(state["upcoming_pieces"])
        game.bag = state["bag"]
        game.is_back_to_back = state["is_back_to_back"]
        cp = state["current_piece"]
        game.current_piece = Piece(cp["shape_name"], game.width)
        game.current_piece.x, game.current_piece.y, game.current_piece.rotation = (
            cp["x"],
            cp["y"],
            cp["rotation"],
        )
        if state["hold_piece"]:
            game.hold_piece = Piece(state["hold_piece"]["shape_name"], game.width)
        game.elapsed_time = elapsed
        game.start_time = time.time() - elapsed
        return game
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def delete_save_state() -> None:
    """Deletes the saved game state from the database."""
    with db_connection() as conn:
        conn.execute("DELETE FROM saved_game WHERE id = 1")


def has_save_state() -> bool:
    """Checks if a saved game exists in the database."""
    with db_connection() as conn:
        return (
            conn.execute("SELECT id FROM saved_game WHERE id = 1").fetchone()
            is not None
        )