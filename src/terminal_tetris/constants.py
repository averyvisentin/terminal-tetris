"""
Constants and default settings for Terminal Tetris.
"""

import os

# Database and file paths
DB_DIR = os.path.expanduser("~/Games/terminal-tetris")
DATABASE_FILE = os.path.join(DB_DIR, "tetris.db")
QUOTES_FILE = os.path.join(DB_DIR, "menu_quotes.txt")
ERROR_LOG_FILE = os.path.join(DB_DIR, "tetris_error.log")

# Game settings keys that are reserved (cannot be rebound)
RESERVED_KEYS = ("p", "q")  # pause / quit can't be rebound

# Game modes where points are awarded
SCORING_MODES = ("standard", "timed", "garbage")

# Sprint mode target lines
SPRINT_TARGET_LINES = 40

# Tetromino shapes (5x5 matrices, "O" = block)
SHAPES = {
    "I": [
        [".....", "..O..", "..O..", "..O..", "..O.."],
        [".....", ".....", "OOOO.", ".....", "....."],
        [".O...", ".O...", ".O...", ".O...", "....."],
        [".....", ".....", ".OOOO", ".....", "....."],
    ],
    "O": [
        [".....", ".OO..", ".OO..", ".....", "....."],
        [".....", ".OO..", ".OO..", ".....", "....."],
        [".....", ".OO..", ".OO..", ".....", "....."],
        [".....", ".OO..", ".OO..", ".....", "....."],
    ],
    "T": [
        [".....", "..O..", ".OOO.", ".....", "....."],
        [".....", "..O..", "..OO.", "..O..", "....."],
        [".....", ".....", ".OOO.", "..O..", "....."],
        [".....", "..O..", ".OO..", "..O..", "....."],
    ],
    "S": [
        [".....", "..OO.", ".OO..", ".....", "....."],
        [".....", ".O...", ".OO..", "..O..", "....."],
        [".....", "..OO.", ".OO..", ".....", "....."],
        [".....", ".O...", ".OO..", "..O..", "....."],
    ],
    "Z": [
        [".....", ".OO..", "..OO.", ".....", "....."],
        [".....", "..O..", ".OO..", ".O...", "....."],
        [".....", ".OO..", "..OO.", ".....", "....."],
        [".....", "..O..", ".OO..", ".O...", "....."],
    ],
    "J": [
        [".....", ".O...", ".OOO.", ".....", "....."],
        [".....", "..OO.", "..O..", "..O..", "....."],
        [".....", ".....", ".OOO.", "...O.", "....."],
        [".....", "..O..", "..O..", ".OO..", "....."],
    ],
    "L": [
        [".....", "...O.", ".OOO.", ".....", "....."],
        [".....", "..O..", "..O..", "..OO.", "....."],
        [".....", ".....", ".OOO.", ".O...", "....."],
        [".....", ".OO..", "..O..", "..O..", "....."],
    ],
}

# Colors for each piece type (blessed color names)
PIECE_COLORS = {
    "I": "cyan",
    "O": "yellow",
    "T": "magenta",
    "S": "green",
    "Z": "red",
    "J": "blue",
    "L": "orange",
    "G": "white",  # Garbage
}

# Display characters
BLOCK_CHAR = "██"
GHOST_CHAR = "▒▒"
GARBAGE_BLOCK_TYPE = "G"

# Menu options
MODE_OPTIONS = {
    "Marathon": "standard",
    "Sprint": "sprint",
    "Timed": "timed",
    "Garbage": "garbage",
}

BOARD_ORDER = ("standard", "sprint", "timed", "garbage")


def get_default_settings() -> dict:
    """Returns a dictionary containing all default game settings."""
    return {
        # Board and UI
        "BOARD_WIDTH": 10,
        "BOARD_HEIGHT": 22,
        "PLAYFIELD_Y_OFFSET": 2,
        # High Scores
        "MAX_SCORES": 2,
        "MAX_NAME_LENGTH": 3,
        # Timing
        "INITIAL_GRAVITY_INTERVAL": 1.0,
        "GRAVITY_LEVEL_MULTIPLIER": 0.09,
        "MIN_GRAVITY_INTERVAL": 0.1,
        "INPUT_TIMEOUT": 0.01,
        "RENDER_THROTTLE_MS": 16,
        "Lock Delay (s)": 0.5,
        "FLASH_DURATION": 0.2,
        "TIMED_MODE_DURATION_S": 120,
        "GARBAGE_INTERVAL_S": 15,
        # Gameplay
        "MIN_LEVEL": 1,
        "MAX_LEVEL": 15,
        "GHOST_PIECE_ENABLED": 1,
        "SPRINT_DEFAULT_LEVEL": 1,
        # Scoring
        "SCORE_VALUES": {
            "SINGLE": 100,
            "DOUBLE": 300,
            "TRIPLE": 500,
            "TETRIS": 800,
            "T_SPIN_MINI": 100,
            "T_SPIN": 400,
            "T_SPIN_SINGLE": 800,
            "T_SPIN_DOUBLE": 1200,
            "T_SPIN_TRIPLE": 1600,
            "BACK_TO_BACK_MULTIPLIER": 1.5,
        },
        # Keybindings
        "Key: Left": "KEY_LEFT",
        "Key: Right": "KEY_RIGHT",
        "Key: Rotate": "KEY_UP",
        "Key: Soft Drop": "KEY_DOWN",
        "Key: Hard Drop": " ",
        "Key: Hold": "c",
    }