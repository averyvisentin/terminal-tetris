"""Terminal Tetris - A fully-featured Tetris implementation for the terminal."""

__version__ = "1.0.0"
__author__ = "avery"

from .constants import (
    BLOCK_CHAR,
    BOARD_ORDER,
    DATABASE_FILE,
    DB_DIR,
    ERROR_LOG_FILE,
    GARBAGE_BLOCK_TYPE,
    GHOST_CHAR,
    MODE_OPTIONS,
    PIECE_COLORS,
    QUOTES_FILE,
    RESERVED_KEYS,
    SCORING_MODES,
    SHAPES,
    SPRINT_TARGET_LINES,
)
from .database import initialize_database
from .models import Game, Piece
from .database import SETTINGS, load_settings, save_settings

__all__ = [
    "SHAPES",
    "PIECE_COLORS",
    "BLOCK_CHAR",
    "GHOST_CHAR",
    "GARBAGE_BLOCK_TYPE",
    "SPRINT_TARGET_LINES",
    "SCORING_MODES",
    "RESERVED_KEYS",
    "BOARD_ORDER",
    "MODE_OPTIONS",
    "DB_DIR",
    "DATABASE_FILE",
    "QUOTES_FILE",
    "ERROR_LOG_FILE",
    "SETTINGS",
    "load_settings",
    "save_settings",
    "Game",
    "Piece",
    "initialize_database",
]