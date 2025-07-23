"""
Terminal Tetris Game
A fully-featured Tetris implementation for the terminal with modern mechanics.
Now with database-driven configuration.

Author: avery
"""

# Import necessary libraries

import time
import sys
import collections
import copy
import random
import os
import sqlite3
import signal # resize handling
import json # Added for handling complex settings
from typing import List, Tuple, Optional, Any, Callable
from blessed import Terminal
#from ast import Index
from contextlib import nullcontext

"""--- Game Configuration & Constants ---"""
DB_DIR = os.path.expanduser('~/Games/terminal-tetris') # adding this because the current path was not permissed to the game script and I wanted to store the database in a more accessible location. Easier than permissing
DATABASE_FILE = os.path.join(DB_DIR, 'tetris.db') # Define the database file path to be in the user's Games directory.
SETTINGS = {} # This global dictionary will be populated by load_settings() from the database.
QUOTES_FILE = os.path.join(DB_DIR,'menu_quotes.txt') # NEW: Filename for our quotes

# Tetromino shapes and their colors are fundamental and remain hardcoded.
SHAPES = {
    'I': [['.....', '..O..', '..O..', '..O..', '..O..'], ['.....', '.....', 'OOOO.', '.....', '.....'], ['.O...', '.O...', '.O...', '.O...', '.....'], ['.....', '.....', '.OOOO', '.....', '.....']],
    'O': [['.....', '.OO..', '.OO..', '.....', '.....'], ['.....', '.OO..', '.OO..', '.....', '.....'], ['.....', '.OO..', '.OO..', '.....', '.....'], ['.....', '.OO..', '.OO..', '.....', '.....']],
    'T': [['.....', '..O..', '.OOO.', '.....', '.....'], ['.....', '..O..', '..OO.', '..O..', '.....'], ['.....', '.....', '.OOO.', '..O..', '.....'], ['.....', '..O..', '.OO..', '..O..', '.....']],
    'S': [['.....', '..OO.', '.OO..', '.....', '.....'], ['.....', '.O...', '.OO..', '..O..', '.....'], ['.....', '..OO.', '.OO..', '.....', '.....'], ['.....', '.O...', '.OO..', '..O..', '.....']],
    'Z': [['.....', '.OO..', '..OO.', '.....', '.....'], ['.....', '..O..', '.OO..', '.O...', '.....'], ['.....', '.OO..', '..OO.', '.....', '.....'], ['.....', '..O..', '.OO..', '.O...', '.....']],
    'J': [['.....', '.O...', '.OOO.', '.....', '.....'], ['.....', '..OO.', '..O..', '..O..', '.....'], ['.....', '.....', '.OOO.', '...O.', '.....'], ['.....', '..O..', '..O..', '.OO..', '.....']],
    'L': [['.....', '...O.', '.OOO.', '.....', '.....'], ['.....', '..O..', '..O..', '..OO.', '.....'], ['.....', '.....', '.OOO.', '.O...', '.....'], ['.....', '.OO..', '..O..', '..O..', '.....']]
}
PIECE_COLORS = {'I': 'cyan', 'O': 'yellow', 'T': 'magenta', 'S': 'green', 'Z': 'red', 'J': 'blue', 'L': 'orange', 'G': 'white'}
BLOCK_CHAR = '██'
GHOST_CHAR = '▒▒'
GARBAGE_BLOCK_TYPE = 'G'

"""--- Database & Settings Management ---"""

def get_default_settings() -> dict:     ### this  better to have up here, (I HATE GOING ALL THE WAY DOWN TO THE BOTTOM)
    """Returns a dictionary containing all default game settings."""
    return {
        # Board and UI
        "BOARD_WIDTH": 10, "BOARD_HEIGHT": 22, "PLAYFIELD_X_OFFSET": 15, "PLAYFIELD_Y_OFFSET": 2,
        # High Scores
        "MAX_SCORES": 2, "MAX_NAME_LENGTH": 3,
        # Timing
        "INITIAL_GRAVITY_INTERVAL": 1.0, "GRAVITY_LEVEL_MULTIPLIER": 0.09, "MIN_GRAVITY_INTERVAL": 0.1,
        "INPUT_TIMEOUT": 0.01, "RENDER_THROTTLE_MS": 16, "Lock Delay (s)": 0.5,
        "FLASH_DURATION": 0.2, "TIMED_MODE_DURATION_S": 120, "GARBAGE_INTERVAL_S": 15,
        # Gameplay
        "MIN_LEVEL": 1, "MAX_LEVEL": 15, "GHOST_PIECE_ENABLED": 1,
        "SPRINT_DEFAULT_LEVEL": 1,
        # Scoring
        "SCORE_VALUES": {"SINGLE": 100, "DOUBLE": 300, "TRIPLE": 500, "TETRIS": 800, "T_SPIN_MINI": 100, "T_SPIN": 400, "T_SPIN_SINGLE": 800, "T_SPIN_DOUBLE": 1200, "T_SPIN_TRIPLE": 1600, "BACK_TO_BACK_MULTIPLIER": 1.5},
        # Keybindings
        "Key: Left": "KEY_LEFT", "Key: Right": "KEY_RIGHT", "Key: Rotate": "KEY_UP",
        "Key: Soft Drop": "KEY_DOWN", "Key: Hard Drop": ' ', "Key: Hold": 'c',
    }


def initialize_database():
    """Creates the database and tables if they don't exist."""
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True) #Im so dumb
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, score INTEGER NOT NULL, time REAL NOT NULL, lines INTEGER NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS sprint_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, time REAL NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS timed_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, score INTEGER NOT NULL, lines INTEGER NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS garbage_highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, time REAL NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS saved_game (id INTEGER PRIMARY KEY, game_state TEXT NOT NULL)')

def save_settings(settings_dict):
    """Saves the entire settings dictionary to the database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        for key, value in settings_dict.items():
            value_to_save = json.dumps(value) if isinstance(value, dict) else str(value)
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value_to_save))

def load_settings():
    """Loads all settings from the database, applying defaults on first run."""
    global SETTINGS
    defaults = get_default_settings()

    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        db_settings = dict(cursor.fetchall())

    if not db_settings:
        SETTINGS = defaults
        save_settings(defaults)
        return

    loaded_settings = {}
    for key, default_value in defaults.items():
        db_value = db_settings.get(key)
        if db_value is None:
            loaded_settings[key] = default_value
            continue
        try:
            if isinstance(default_value, dict):
                loaded_settings[key] = json.loads(db_value)
            elif isinstance(default_value, float):
                loaded_settings[key] = float(db_value)
            elif isinstance(default_value, int):
                loaded_settings[key] = int(db_value)
            else:
                loaded_settings[key] = db_value
        except (json.JSONDecodeError, ValueError, TypeError):
            loaded_settings[key] = default_value
    SETTINGS = loaded_settings

def format_time(seconds: float) -> str:
    """Formats seconds into a MM:SS.ss string."""
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02}:{remaining_seconds:05.2f}"

# --- High Score Functions ---

def load_high_scores(table: str, select_cols: str, order_by_clause: str) -> List[Tuple]:
    """Loads high scores from the specified table."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        query = f"SELECT {select_cols} FROM {table} ORDER BY {order_by_clause} LIMIT ?"
        cursor.execute(query, (SETTINGS.get('MAX_SCORES', 10),))
        return cursor.fetchall()

def save_high_scores(scores: List[Tuple], table: str, db_cols: List[str], sort_key_func: Callable, sort_reverse: bool) -> bool:
    """
    Saves high scores to the specified table.
    Assumes the tuples in 'scores' have values that correspond to the order of 'db_cols'.
    """
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {table}")
            scores.sort(key=sort_key_func, reverse=sort_reverse)

            cols_str = ", ".join(db_cols)
            placeholders = ", ".join(["?"] * len(db_cols))
            query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"

            for score_tuple in scores[:SETTINGS.get('MAX_SCORES', 10)]:
                cursor.execute(query, score_tuple)
            return True
        except sqlite3.Error:
            return False

def _display_high_scores_list(term: Terminal, start_y: int, title: str, scores_to_show: List[Tuple], formatter_func: Callable[[Tuple], str]) -> int:
    """Displays a generic list of high scores."""
    print(term.move_y(start_y) + term.center(term.underline(title)))
    if not scores_to_show:
        print(term.center("No scores yet!"))
        return 2
    for i, score_tuple in enumerate(scores_to_show):
        # Assumes the last element of the tuple is the player's name.
        name = score_tuple[-1]
        score_values = score_tuple[:-1]
        score_str = formatter_func(score_values)
        line = f"{i+1}. {name:<{SETTINGS.get('MAX_NAME_LENGTH', 3)}} - {score_str}"
        print(term.center(line))
    return len(scores_to_show) + 2

# --- Core Game Logic Classes (The "Model") ---

class Piece:
    def __init__(self, shape_name: str):
        self.shape_name: str = shape_name
        self.shape_matrices: List[List[str]] = SHAPES[shape_name]
        self.color: str = PIECE_COLORS[shape_name]
        self.rotation: int = 0
        self.x: int = SETTINGS['BOARD_WIDTH'] // 2 - 2
        self.y: int = -2

    def get_current_shape_matrix(self) -> List[str]:
        return self.shape_matrices[self.rotation]

    def get_block_locations(self) -> List[Tuple[int, int]]:
        positions = []
        shape = self.get_current_shape_matrix()
        for r, row_str in enumerate(shape):
            for c, char in enumerate(row_str):
                if char == 'O':
                    positions.append((self.x + c, self.y + r))
        return positions

class Game:
    def __init__(self, gamemode: str = "standard", start_level: int = 1):
        self.board: List[List[Any]] = [[0 for _ in range(SETTINGS['BOARD_WIDTH'])] for _ in range(SETTINGS['BOARD_HEIGHT'])]
        self.score: int = 0
        self.lines_cleared: int = 0
        self.level: int = start_level
        self.start_level: int = start_level
        self.game_over: bool = False
        self.paused: bool = False
        self.bag: List[str] = []
        self.upcoming_pieces = collections.deque()
        self._refill_bag()
        for _ in range(5):
            self._add_to_upcoming()
        self.current_piece: Piece = self._get_new_piece()
        self.hold_piece: Optional[Piece] = None
        self.can_hold: bool = True
        self.is_back_to_back: bool = False
        self.last_move_was_rotation: bool = False
        self.lock_delay_start_time: float = 0
        self.quit_after_save: bool = False
        self.lines_to_flash = []
        self.flash_text = ""
        self.flash_start_time = 0
        self.gamemode: str = gamemode
        self.start_time: float = time.time()
        self.elapsed_time: float = 0
        # NEW: Attribute for garbage mode timing
        self.last_garbage_time: float = time.time()

    def add_garbage_row(self):
        """Adds a row of garbage to the bottom of the board."""
        # Create a new garbage row with one hole
        hole_position = random.randint(0, SETTINGS['BOARD_WIDTH'] - 1)
        new_row = [GARBAGE_BLOCK_TYPE if i != hole_position else 0 for i in range(SETTINGS['BOARD_WIDTH'])]

        # Remove the top row and add the garbage row to the bottom
        self.board.pop(0)
        self.board.append(new_row)

        # Check if the current piece is now in an invalid position
        if not self._is_valid_position(self.current_piece):
            self.game_over = True

    def _add_to_upcoming(self):
        if not self.bag:
            self._refill_bag()
        self.upcoming_pieces.append(self.bag.pop())

    def _get_new_piece(self) -> Piece:
        shape_name = self.upcoming_pieces.popleft()
        self._add_to_upcoming()
        return Piece(shape_name)

    def _refill_bag(self):
        self.bag = list(SHAPES.keys())
        random.shuffle(self.bag)

    def _is_valid_position(self, piece, check_y_offset=0):
        for x, y in piece.get_block_locations():
            y += check_y_offset
            if not (0 <= x < SETTINGS['BOARD_WIDTH'] and y < SETTINGS['BOARD_HEIGHT']):
                return False
            if y >= 0 and self.board[y][x] != 0:
                return False
        return True

    def _is_touching_ground(self):
        return not self._is_valid_position(self.current_piece, check_y_offset=1)

    def _lock_piece(self):
        t_spin_type = self._check_t_spin() if self.current_piece.shape_name == 'T' and self.last_move_was_rotation else None
        for x, y in self.current_piece.get_block_locations():
            if y >= 0:
                self.board[y][x] = self.current_piece.shape_name
        lines_cleared_this_turn = self._clear_lines(t_spin_type)
        if t_spin_type or lines_cleared_this_turn == 4:
            self.is_back_to_back = True
        elif lines_cleared_this_turn > 0:
            self.is_back_to_back = False
        self.can_hold = True
        self.current_piece = self._get_new_piece()
        self.last_move_was_rotation = False
        if not self._is_valid_position(self.current_piece):
            self.game_over = True

    def _check_t_spin(self):
        piece = self.current_piece
        center_x, center_y = piece.x + 2, piece.y + 1
        corners = [(center_x - 1, center_y - 1), (center_x + 1, center_y - 1), (center_x - 1, center_y + 1), (center_x + 1, center_y + 1)]
        occupied_corners = sum(1 for x, y in corners if not (0 <= x < SETTINGS['BOARD_WIDTH'] and 0 <= y < SETTINGS['BOARD_HEIGHT']) or (y >= 0 and self.board[y][x] != 0))
        if occupied_corners >= 3:
            return "T_SPIN"
        if occupied_corners == 2:
            front_corners = [corners[i] for i in [[0, 1], [1, 3], [2, 3], [0, 2]][piece.rotation]]
            if any(not (0 <= x < SETTINGS['BOARD_WIDTH'] and 0 <= y < SETTINGS['BOARD_HEIGHT']) or (y >= 0 and self.board[y][x] != 0) for x, y in front_corners):
                return "T_SPIN_MINI"
        return None

    def _clear_lines(self, t_spin_type=None):
        lines_to_clear_indices = [i for i, row in enumerate(self.board) if all(cell != 0 for cell in row)]
        if not lines_to_clear_indices and not t_spin_type:
            return 0

        self.lines_to_flash = lines_to_clear_indices
        self.flash_start_time = time.time()
        new_board = [row for row in self.board if any(cell == 0 for cell in row)]
        lines_cleared_count = len(self.board) - len(new_board)

        if lines_cleared_count > 0:
            for _ in range(lines_cleared_count):
                new_board.insert(0, [0 for _ in range(SETTINGS['BOARD_WIDTH'])])
            self.board = new_board

        if self.gamemode in ["standard", "timed", "garbage"]:
            score_key_map = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}
            t_spin_key_map = {1: "T_SPIN_SINGLE", 2: "T_SPIN_DOUBLE", 3: "T_SPIN_TRIPLE"}
            score_key = t_spin_key_map.get(lines_cleared_count, t_spin_type) if t_spin_type else score_key_map.get(lines_cleared_count)

            if score_key:
                self.flash_text = score_key.replace("_", " ")
                base_score = SETTINGS['SCORE_VALUES'].get(score_key, 0)
                is_difficult = "TETRIS" in score_key or "T_SPIN" in score_key
                if is_difficult and self.is_back_to_back:
                    base_score *= SETTINGS['SCORE_VALUES']["BACK_TO_BACK_MULTIPLIER"]
                self.score += int(base_score * self.level)

        self.lines_cleared += lines_cleared_count
        self.level = self.start_level + (self.lines_cleared // 10)

        if self.gamemode == "sprint" and self.lines_cleared >= 40:
            self.elapsed_time = time.time() - self.start_time
            self.game_over = True

        return lines_cleared_count

    def move(self, dx):
        self.current_piece.x += dx
        if not self._is_valid_position(self.current_piece):
            self.current_piece.x -= dx
        else:
            self.last_move_was_rotation = False
            self.reset_lock_delay()

    def rotate(self):
        original_rotation = self.current_piece.rotation
        self.current_piece.rotation = (self.current_piece.rotation + 1) % 4
        if self._is_valid_position(self.current_piece):
            self.last_move_was_rotation = True
            self.reset_lock_delay()
            return
        for kick_x in [-1, 1, -2, 2]:
            self.current_piece.x += kick_x
            if self._is_valid_position(self.current_piece):
                self.last_move_was_rotation = True
                self.reset_lock_delay()
                return
            self.current_piece.x -= kick_x
        self.current_piece.rotation = original_rotation

    def soft_drop(self):
        if not self._is_touching_ground():
            self.current_piece.y += 1
            if self.gamemode in ['standard', 'timed', 'garbage']:
                self.score += 1
            self.last_move_was_rotation = False
        else:
            self.initiate_lock_delay()

    def hard_drop(self):
        drop_distance = 0
        while not self._is_touching_ground():
            self.current_piece.y += 1
            drop_distance += 1
        if self.gamemode in ['standard', 'timed', 'garbage']:
            self.score += drop_distance * 2
        self._lock_piece()

    def hold(self):
        if self.can_hold:
            if self.hold_piece is None:
                self.hold_piece = Piece(self.current_piece.shape_name)
                self.current_piece = self._get_new_piece()
            else:
                self.current_piece, self.hold_piece = Piece(self.hold_piece.shape_name), Piece(self.current_piece.shape_name)
            self.can_hold = False
            self.last_move_was_rotation = False

    def initiate_lock_delay(self):
        if self.lock_delay_start_time == 0:
            self.lock_delay_start_time = time.time()

    def reset_lock_delay(self):
        self.lock_delay_start_time = 0
        if self._is_touching_ground():
            self.initiate_lock_delay()

    def update(self):
        if self.paused or self.game_over:
            return

        current_time = time.time()
        self.elapsed_time = current_time - self.start_time

        if self.gamemode == 'timed':
            if self.elapsed_time >= SETTINGS['TIMED_MODE_DURATION_S']:
                self.game_over = True
                return

        if self.gamemode == 'garbage':
            if current_time - self.last_garbage_time >= SETTINGS['GARBAGE_INTERVAL_S']:
                self.add_garbage_row()
                self.last_garbage_time = current_time

        if self._is_touching_ground():
            self.initiate_lock_delay()
            if self.lock_delay_start_time and (time.time() - self.lock_delay_start_time >= SETTINGS["Lock Delay (s)"]):
                self._lock_piece()
        else:
            self.reset_lock_delay()

    def get_ghost_piece_y(self):
        ghost_piece = copy.deepcopy(self.current_piece)
        while self._is_valid_position(ghost_piece, 1):
            ghost_piece.y += 1
        return ghost_piece.y

# --- Rendering Logic (The "View" and "Controller") ---

def get_color(term, color_name):
    return getattr(term, color_name, term.white)

def draw_board_border(term):
    x, y = SETTINGS['PLAYFIELD_X_OFFSET'] - 2, SETTINGS['PLAYFIELD_Y_OFFSET'] - 1
    width = SETTINGS['BOARD_WIDTH'] * 2 + 2
    print(term.move_xy(x, y) + '╔' + '═' * width + '╗')
    for i in range(SETTINGS['BOARD_HEIGHT']):
        print(term.move_xy(x, y + 1 + i) + '║')
        print(term.move_xy(x + width + 1, y + 1 + i) + '║')
    print(term.move_xy(x, y + SETTINGS['BOARD_HEIGHT'] + 1) + '╚' + '═' * width + '╝')

def draw_piece(term, piece, offset=(0, 0), is_ghost=False):
    char = GHOST_CHAR if is_ghost else BLOCK_CHAR
    color_func = get_color(term, piece.color)
    for px, py in piece.get_block_locations():
        if py >= 0:
            print(term.move_xy((px * 2) + offset[0], py + offset[1]) + color_func(char))

def get_key_display_name(key_str):
    if key_str == ' ':
        return "Space"
    return str(key_str).replace("KEY_", "").replace("_", " ").title()

def draw_ui(term, game):
    print(term.move_xy(SETTINGS['PLAYFIELD_X_OFFSET'], 0) + term.bold_underline("Terminal Tetris"))
    def draw_box(x, y, w, h, title, content=""):
        print(term.move_xy(x, y) + f"╔{'═'*(w-2)}╗")
        padding_size = (w - 2) - term.length(title) - 1
        padding = ' ' * padding_size
        print(term.move_xy(x, y + 1) + f"║ {title}{padding}║")
        for i in range(2, h - 1):
            print(term.move_xy(x, y + i) + f"║{' '*(w-2)}║")
        print(term.move_xy(x, y + h - 1) + f"╚{'═'*(w-2)}╝")
        if content:
            print(term.move_xy(x + 2, y + 2) + str(content))

    if game.gamemode == "sprint":
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 2, 12, 4, "TIME", f"{format_time(game.elapsed_time)}")
        lines_text = f"{min(game.lines_cleared, 40)}/40"
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 14, 12, 12, 4, "LINES", lines_text)
    elif game.gamemode == "timed":
        time_left = max(0, SETTINGS['TIMED_MODE_DURATION_S'] - game.elapsed_time)
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 2, 12, 4, "TIME LEFT", f"{format_time(time_left)}")
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 7, 12, 4, "SCORE", f"{game.score}")
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 12, 12, 4, "LINES", f"{game.lines_cleared}")
    elif game.gamemode == "garbage":
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 2, 12, 4, "TIME", f"{format_time(game.elapsed_time)}")
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 7, 12, 4, "SCORE", f"{game.score}")
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 12, 12, 4, "LINES", f"{game.lines_cleared}")
    else: # Standard mode
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 2, 12, 4, "SCORE", f"{game.score}")
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 12, 10, 4, "LINES", f"{game.lines_cleared}")

    if game.gamemode not in ['timed', 'garbage']:
        draw_box(SETTINGS['PLAYFIELD_X_OFFSET'] - 15, 7, 10, 4, "LEVEL", f"{game.level}")

    next_box_x = SETTINGS['PLAYFIELD_X_OFFSET'] + SETTINGS['BOARD_WIDTH'] * 2 + 3
    next_box_y = SETTINGS['PLAYFIELD_Y_OFFSET']
    draw_box(next_box_x, next_box_y, 10, 22, "NEXT")
    for i, shape_name in enumerate(game.upcoming_pieces):
        if i >= 4:
            break
        display_piece = Piece(shape_name)
        display_piece.x = 0
        display_piece.y = 0
        draw_piece(term, display_piece, offset=(next_box_x + 0, next_box_y + 1 + (i * 5)))

    hold_box_x, hold_box_y = next_box_x, next_box_y + 23
    draw_box(hold_box_x, hold_box_y, 10, 7, "HOLD")
    if game.hold_piece:
        hold_piece_display = Piece(game.hold_piece.shape_name)
        hold_piece_display.x = 0
        hold_piece_display.y = 0
        draw_piece(term, hold_piece_display, offset=(hold_box_x + 0, hold_box_y + 1))

# Define the coordinates for the controls box
    controls_y = SETTINGS['PLAYFIELD_Y_OFFSET'] + SETTINGS['BOARD_HEIGHT'] + 1
    controls_x = SETTINGS['PLAYFIELD_X_OFFSET'] - 5
    draw_box(controls_x - 2, controls_y, SETTINGS['BOARD_WIDTH'] * 2 + 9, 10, "CONTROLS")

    # A structured list of the controls to display
    controls_list = [
        ("Move", f"{get_key_display_name(SETTINGS['Key: Left'])}/{get_key_display_name(SETTINGS['Key: Right'])}"),
        ("Rotate", get_key_display_name(SETTINGS['Key: Rotate'])),
        ("Soft Drop", get_key_display_name(SETTINGS['Key: Soft Drop'])),
        ("Hard Drop", get_key_display_name(SETTINGS['Key: Hard Drop'])),
        ("Hold", get_key_display_name(SETTINGS['Key: Hold'])),
        ("Pause", "P"),
        ("Save", "S (Paused)"),
        ("Quit", "Q")
    ]

    # Starting position for the text inside the box
    text_start_x = controls_x - 1
    text_start_y = controls_y + 1
    label_col_width = 10 # Set a fixed width for the left "label" column

    # Loop through the list and print each formatted line
    for i, (label, key) in enumerate(controls_list):
        # Format the string with a left-aligned label to create columns
        line = f"  {label:<{label_col_width}}: {key}"

        # Print the line at the correct position
        print(term.move_xy(text_start_x, text_start_y + i) + line)


def draw_game_state(term, game):
    # This overwrites the setting with a new value based on terminal width.
    SETTINGS['PLAYFIELD_X_OFFSET'] = (term.width // 2) - SETTINGS['BOARD_WIDTH']
    # --- END OF CHANGE ---
    print(term.home + term.clear_eos, end='')
    draw_board_border(term)
    draw_ui(term, game)

    for y, row in enumerate(game.board):
        for x, cell in enumerate(row):
            if cell != 0:
                color = get_color(term, PIECE_COLORS.get(cell, 'white'))
                print(term.move_xy(x * 2 + SETTINGS['PLAYFIELD_X_OFFSET'], y + SETTINGS['PLAYFIELD_Y_OFFSET']) + color(BLOCK_CHAR))

    if game.lines_to_flash and (time.time() - game.flash_start_time < SETTINGS['FLASH_DURATION']):
        for y in game.lines_to_flash:
            for x in range(SETTINGS['BOARD_WIDTH']):
                print(term.move_xy(x * 2 + SETTINGS['PLAYFIELD_X_OFFSET'], y + SETTINGS['PLAYFIELD_Y_OFFSET']) + term.white_on_white(BLOCK_CHAR))
        if game.flash_text:
            print(term.move_xy(2, 17) + term.cyan_bold(game.flash_text))
    else:
        game.lines_to_flash = []
        game.flash_text = ""

    if SETTINGS.get('GHOST_PIECE_ENABLED') == 1:
        ghost_y = game.get_ghost_piece_y()
        if ghost_y > game.current_piece.y:
            ghost_piece = copy.deepcopy(game.current_piece)
            ghost_piece.y = ghost_y
            draw_piece(term, ghost_piece, offset=(SETTINGS['PLAYFIELD_X_OFFSET'], SETTINGS['PLAYFIELD_Y_OFFSET']), is_ghost=True)

    draw_piece(term, game.current_piece, offset=(SETTINGS['PLAYFIELD_X_OFFSET'], SETTINGS['PLAYFIELD_Y_OFFSET']))

    if game.paused:
        msg = "PAUSED"
        print(term.move_xy(SETTINGS['PLAYFIELD_X_OFFSET'] + SETTINGS['BOARD_WIDTH'] - len(msg)//2, SETTINGS['PLAYFIELD_Y_OFFSET'] + SETTINGS['BOARD_HEIGHT']//2) + term.black_on_white(msg))

def save_game_state(game: 'Game'):
    """Serializes the game state and saves it to the database."""
    state = {
        'board': game.board, 'score': game.score, 'lines_cleared': game.lines_cleared, 'level': game.level,
        'gamemode': game.gamemode,
        'current_piece': {'shape_name': game.current_piece.shape_name, 'x': game.current_piece.x, 'y': game.current_piece.y, 'rotation': game.current_piece.rotation,},
        'hold_piece': {'shape_name': game.hold_piece.shape_name,} if game.hold_piece else None,
        'can_hold': game.can_hold, 'upcoming_pieces': list(game.upcoming_pieces), 'bag': game.bag, 'is_back_to_back': game.is_back_to_back,
    }
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO saved_game (id, game_state) VALUES (1, ?)", (json.dumps(state),))

def load_game_state() -> Optional['Game']:
    """Loads a game state from the database and reconstructs the Game object."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT game_state FROM saved_game WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return None

    state = json.loads(row[0])
    game = Game(gamemode=state.get('gamemode', 'standard'), start_level=state['level'])
    game.board = state['board']
    game.score = state['score']
    game.lines_cleared = state['lines_cleared']
    game.level = state['level']
    game.can_hold = state['can_hold']
    game.upcoming_pieces = collections.deque(state['upcoming_pieces'])
    game.bag = state['bag']
    game.is_back_to_back = state['is_back_to_back']
    cp_state = state['current_piece']
    game.current_piece = Piece(cp_state['shape_name'])
    game.current_piece.x = cp_state['x']
    game.current_piece.y = cp_state['y']
    game.current_piece.rotation = cp_state['rotation']
    if state['hold_piece']:
        hp_state = state['hold_piece']
        game.hold_piece = Piece(hp_state['shape_name'])
    return game

def delete_save_state():
    """Deletes the saved game state from the database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_game WHERE id = 1")

def has_save_state() -> bool:
    """Checks if a saved game exists in the database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM saved_game WHERE id = 1")
        return cursor.fetchone() is not None

def get_key_repr(key):
    if key.is_sequence:
        return key.name
    return str(key)

def handle_input(term: Terminal, game: Game):
    key_event = term.inkey(timeout=SETTINGS['INPUT_TIMEOUT'])
    if not key_event:
        return
    key = get_key_repr(key_event)
    if game.paused and key.lower() == 's' and game.gamemode == 'standard':
        save_game_state(game)
        msg = "GAME SAVED"
        print(term.move_xy(SETTINGS['PLAYFIELD_X_OFFSET'] + SETTINGS['BOARD_WIDTH'] - len(msg)//2, SETTINGS['PLAYFIELD_Y_OFFSET'] + SETTINGS['BOARD_HEIGHT']//2 + 2) + term.black_on_green(msg))
        sys.stdout.flush()
        time.sleep(1)
        game.quit_after_save = True
        game.game_over = True
        return
    if not game.paused:
        if key == SETTINGS["Key: Left"]:
            game.move(-1)
        elif key == SETTINGS["Key: Right"]:
            game.move(1)
        elif key == SETTINGS["Key: Rotate"]:
            game.rotate()
        elif key == SETTINGS["Key: Soft Drop"]:
            game.soft_drop()
        elif key == SETTINGS["Key: Hard Drop"]:
            game.hard_drop()
        elif key == SETTINGS["Key: Hold"]:
            game.hold()
    if key == 'p':
        game.paused = not game.paused
    elif key == 'q':
        game.game_over = True

def apply_gravity(game: Game, last_gravity_time: float) -> float:
    if game.paused or game.game_over: return last_gravity_time
    current_time = time.time()
    gravity_interval = max(SETTINGS['MIN_GRAVITY_INTERVAL'], SETTINGS['INITIAL_GRAVITY_INTERVAL'] - (game.level - 1) * SETTINGS['GRAVITY_LEVEL_MULTIPLIER'])
    if current_time - last_gravity_time > gravity_interval:
        if not game._is_touching_ground():
            game.current_piece.y += 1
            game.last_move_was_rotation = False
        return current_time
    return last_gravity_time

def game_loop(term: Terminal, game: Game):
    last_gravity_time = time.time()
    last_render_time = 0
    while not game.game_over:
        handle_input(term, game)
        last_gravity_time = apply_gravity(game, last_gravity_time)
        game.update()
        current_time = time.time()
        if (current_time - last_render_time) * 1000 >= SETTINGS['RENDER_THROTTLE_MS']:
            draw_game_state(term, game)
            sys.stdout.flush()
            last_render_time = current_time

def handle_game_over(term, game):
    if game.gamemode == 'sprint':
        high_scores = load_high_scores(table='sprint_highscores', select_cols='time, name', order_by_clause='time ASC')
        is_high_score = (len(high_scores) < SETTINGS['MAX_SCORES'] or game.elapsed_time < high_scores[-1][0])
        player_name = ""
        if game.lines_cleared >= 40 and is_high_score:
            while True:
                print(term.home + term.clear)
                print(term.center(term.bold("🎉 NEW SPRINT RECORD! 🎉")))
                print(term.center(f"Your Time: {format_time(game.elapsed_time)}"))
                print(term.center(f"Enter your name ({SETTINGS['MAX_NAME_LENGTH']} chars):"))
                input_box = f" {player_name.ljust(SETTINGS['MAX_NAME_LENGTH'], '_')} "
                print(term.center(term.reverse(input_box)))
                key = term.inkey()
                if key.code == term.KEY_ENTER and len(player_name) > 0:
                    break
                elif key.code == term.KEY_BACKSPACE:
                    player_name = player_name[:-1]
                elif len(player_name) < SETTINGS['MAX_NAME_LENGTH'] and not key.is_sequence and key.isalnum():
                    player_name += key.upper()
            high_scores.append((game.elapsed_time, player_name))
            save_high_scores(high_scores, table='sprint_highscores', db_cols=['time', 'name'], sort_key_func=lambda item: item[0], sort_reverse=False)

        while True:
            print(term.home + term.clear)
            scores_to_show = load_high_scores(table='sprint_highscores', select_cols='time, name', order_by_clause='time ASC')
            result_msg = "40 LINES CLEARED!" if game.lines_cleared >= 40 else "GAME OVER"
            print(term.move_y(term.height // 2 - 8) + term.center(term.bold(result_msg)))
            print(term.center(f"Final Time: {format_time(game.elapsed_time)}"))
            _display_high_scores_list(term, term.height // 2 - 4, "Top Sprint Times", scores_to_show, lambda vals: format_time(vals[0]))
            print(term.move_y(term.height - 3) + term.center("Press 'SPACE' or 'ENTER' for Main Menu or 'q' to Quit"))
            key = term.inkey()
            if key.lower() == ' ':
                return True
            elif key.lower() == 'ENTER':
                return True    #my finger is always on enter at the end of the game so I added this
            elif key.lower() == 'q':
                return False
        return

    elif game.gamemode == 'timed':
        high_scores = load_high_scores(table='timed_highscores', select_cols='score, lines, name', order_by_clause='score DESC, lines DESC')
        is_high_score = (len(high_scores) < SETTINGS['MAX_SCORES'] or (game.score, game.lines_cleared) > (high_scores[-1][0], high_scores[-1][1]))
        player_name = ""
        if is_high_score and game.score > 0:
            while True:
                print(term.home + term.clear)
                print(term.center(term.bold("🎉 NEW TIMED HIGH SCORE! 🎉")))
                print(term.center(f"Your Score: {game.score} in {game.lines_cleared} lines"))
                print(term.center(f"Enter your name ({SETTINGS['MAX_NAME_LENGTH']} chars):"))
                input_box = f" {player_name.ljust(SETTINGS['MAX_NAME_LENGTH'], '_')} "
                print(term.center(term.reverse(input_box)))
                key = term.inkey()
                if key.code == term.KEY_ENTER and len(player_name) > 0: break
                elif key.code == term.KEY_BACKSPACE: player_name = player_name[:-1]
                elif len(player_name) < SETTINGS['MAX_NAME_LENGTH'] and not key.is_sequence and key.isalnum(): player_name += key.upper()
            high_scores.append((game.score, game.lines_cleared, player_name))
            save_high_scores(high_scores, table='timed_highscores', db_cols=['score', 'lines', 'name'], sort_key_func=lambda item: (item[0], item[1]), sort_reverse=True)

        while True:
            print(term.home + term.clear)
            scores_to_show = load_high_scores(table='timed_highscores', select_cols='score, lines, name', order_by_clause='score DESC, lines DESC')
            print(term.move_y(term.height // 2 - 8) + term.center(term.bold("TIME'S UP!")))
            print(term.center(f"Final Score: {game.score}"))
            print(term.center(f"Lines Cleared: {game.lines_cleared}"))
            _display_high_scores_list(term, term.height // 2 - 4, "Top Timed Scores", scores_to_show, lambda vals: f"{vals[0]} ({vals[1]}L)")
            print(term.move_y(term.height - 3) + term.center("Press 'SPACE' for Main Menu or 'q' to Quit"))
            key = term.inkey()
            if key.lower() == ' ':
                return True
            elif key.lower() == 'q':
                return False
        return

    elif game.gamemode == 'garbage':
        high_scores = load_high_scores(table='garbage_highscores', select_cols='time, name', order_by_clause='time DESC')
        is_high_score = (len(high_scores) < SETTINGS['MAX_SCORES'] or game.elapsed_time > high_scores[-1][0])
        player_name = ""
        if is_high_score and game.elapsed_time > 0:
            while True:
                print(term.home + term.clear)
                print(term.center(term.bold("🎉 NEW GARBAGE RECORD! 🎉")))
                print(term.center(f"You Survived For: {format_time(game.elapsed_time)}"))
                print(term.center(f"Enter your name ({SETTINGS['MAX_NAME_LENGTH']} chars):"))
                input_box = f" {player_name.ljust(SETTINGS['MAX_NAME_LENGTH'], '_')} "
                print(term.center(term.reverse(input_box)))
                key = term.inkey()
                if key.code == term.KEY_ENTER and len(player_name) > 0:
                    break
                elif key.code == term.KEY_BACKSPACE: player_name = player_name[:-1]
                elif len(player_name) < SETTINGS['MAX_NAME_LENGTH'] and not key.is_sequence and key.isalnum():
                    player_name += key.upper()
            high_scores.append((game.elapsed_time, player_name))
            save_high_scores(high_scores, table='garbage_highscores', db_cols=['time', 'name'], sort_key_func=lambda item: item[0], sort_reverse=True)

        while True:
            print(term.home + term.clear)
            scores_to_show = load_high_scores(table='garbage_highscores', select_cols='time, name', order_by_clause='time DESC')
            print(term.move_y(term.height // 2 - 8) + term.center(term.bold("GAME OVER")))
            print(term.center(f"Final Time: {format_time(game.elapsed_time)}"))
            _display_high_scores_list(term, term.height // 2 - 4, "Top Garbage Times", scores_to_show, lambda vals: format_time(vals[0]))
            print(term.move_y(term.height - 3) + term.center("Press 'SPACE' for Main Menu or 'q' to Quit"))
            key = term.inkey()
            if key.lower() == ' ':
                return True
            elif key.lower() == 'q':
                return False
        return

    else: # Standard Mode
        # Load the full data for checking and appending
        high_scores = load_high_scores(table='highscores', select_cols='score, time, lines, name', order_by_clause='score DESC')
        is_high_score = len(high_scores) < SETTINGS['MAX_SCORES'] or game.score > high_scores[-1][0]
        player_name = ""
        if is_high_score and game.score > 0:
            while True:
                print(term.home + term.clear)
                print(term.center(term.bold("🎉 NEW HIGH SCORE! 🎉")))
                print(term.center(f"Your Score: {game.score}"))
                print(term.center(f"Enter your name ({SETTINGS['MAX_NAME_LENGTH']} chars):"))
                input_box = f" {player_name.ljust(SETTINGS['MAX_NAME_LENGTH'], '_')} "
                print(term.center(term.reverse(input_box)))
                key = term.inkey()
                if key.code == term.KEY_ENTER and len(player_name) > 0: break
                elif key.code == term.KEY_BACKSPACE: player_name = player_name[:-1]
                elif len(player_name) < SETTINGS['MAX_NAME_LENGTH'] and not key.is_sequence and key.isalnum():
                    player_name += key.upper()

            # Append the full data tuple to the list
            high_scores.append((game.score, game.elapsed_time, game.lines_cleared, player_name))
            # Save the updated list, ensuring all required columns are provided
            save_high_scores(high_scores, table='highscores', db_cols=['score', 'time', 'lines', 'name'], sort_key_func=lambda item: item[0], sort_reverse=True)

        while True:
            print(term.home + term.clear)
            # Load only the data needed for the simple display (score and name)
            scores_to_show = load_high_scores(table='highscores', select_cols='score, name', order_by_clause='score DESC')
            print(term.move_y(term.height // 2 - 8) + term.center(term.bold("GAME OVER")))
            print(term.center(f"Final Score: {game.score}"))
            _display_high_scores_list(term, term.height // 2 - 4, "Top Marathon Scores", scores_to_show, lambda vals: str(vals[0]))
            print(term.move_y(term.height - 3) + term.center("Press 'SPACE' for Main Menu or 'q' to Quit"))
            key = term.inkey()
            if key.lower() == ' ':
                return True
            elif key.lower() == 'q':
                return False


# NEW: Helper class to manage resize state.
class ResizeHandler:
    def __init__(self):
        self.dirty = False
    def __call__(self, *args):
        self.dirty = True

def show_main_menu(term: Terminal, resize_handler):
    selected_level = SETTINGS['MIN_LEVEL']
    timed_selected_level = SETTINGS['MIN_LEVEL']
    sprint_selected_level = SETTINGS.get('SPRINT_DEFAULT_LEVEL', 1)
    garbage_selected_level = SETTINGS['MIN_LEVEL']

    menu_options_base = ["Marathon", "Sprint", "Timed", "Garbage", "Settings", "Quit"]
    selected_index = 0

    # -- NEW: Variables for the flashing quote animation --
    try:
        with open(QUOTES_FILE, 'r') as f:
            quotes = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        quotes = ["menu_quotes.txt not found!"]

    # FIXED: Quote is now chosen once when the menu loads and does not cycle.
    current_quote = random.choice(quotes) if quotes else ""
    is_quote_visible = True
    last_blink_time = time.time()
    # ----------------------------------------------------

    redraw_background = True

    while True:
        # -- NEW: Check if a resize happened --
        if resize_handler.dirty:
            redraw_background = True
            resize_handler.dirty = False
        # -------------------------------------

        if redraw_background:
            save_exists = has_save_state()
            menu_options = ["Resume"] + menu_options_base if save_exists else menu_options_base
            if selected_index >= len(menu_options):
                selected_index = 0

            print(term.home + term.clear, end="")

            #box_x, box_y = 1, 0
            #box_w, box_h = term.width - 2, term.height - 1
            #print(term.move_xy(box_x, box_y) + f"╔{'═'*(box_w-2)}╗")
            # Side borders will be drawn at the end of the loop to prevent erasure
            #print(term.move_xy(box_x, box_y + box_h - 1) + f"╚{'═'*(box_w-2)}╝")
            print(term.move_y(1) + term.center(term.bold("Terminal Tetris")))


            # The quote will be drawn in the animation part of the loop
            print(term.move_y(2) + term.center(' ' * (term.width - 4))) # Clear quote line

            standard_scores = load_high_scores('highscores', 'score, name', 'score DESC')
            scores_start_y = 5
            scores_height = _display_high_scores_list(term, scores_start_y, "Top Marathon Scores", standard_scores, lambda vals: str(vals[0]))

            sprint_scores = load_high_scores('sprint_highscores', 'time, name', 'time ASC')
            sprint_start_y = scores_start_y + scores_height + 1
            sprint_scores_height = _display_high_scores_list(term, sprint_start_y, "Top Sprint Times", sprint_scores, lambda vals: format_time(vals[0]))

            timed_scores = load_high_scores('timed_highscores', 'score, lines, name', 'score DESC, lines DESC')
            timed_start_y = sprint_start_y + sprint_scores_height + 1
            timed_scores_height = _display_high_scores_list(term, timed_start_y, "Top Timed Scores", timed_scores, lambda vals: f"{vals[0]} ({vals[1]}L)")

            garbage_scores = load_high_scores('garbage_highscores', 'time, name', 'time DESC')
            garbage_start_y = timed_start_y + timed_scores_height + 1
            _display_high_scores_list(term, garbage_start_y, "Top Garbage Times", garbage_scores, lambda vals: format_time(vals[0]))

            prompt_y = term.height - 7

            print(term.move_y(prompt_y) + term.center("Use ↑/↓ to navigate."))
            print(term.move_y(prompt_y + 1) + term.center("Use ←/→ to change values."))
            print(term.move_y(prompt_y + 2) + term.center("Press SPACE or ENTER to Select. 'q' to Quit."))
            redraw_background = False
        else:
            save_exists = has_save_state()
            menu_options = ["Resume"] + menu_options_base if save_exists else menu_options_base


        # -- Animation logic for the flashing quote --
        current_time = time.time()
        if current_time - last_blink_time > 1: # How fast to blink
            is_quote_visible = not is_quote_visible
            last_blink_time = current_time

        # Clear previous quote and draw current state
        quote_y = 3
        print(term.move_y(quote_y) + term.center(' ' * len(current_quote)))
        if is_quote_visible:
            print(term.move_y(quote_y) + term.center(term.blink(current_quote)))
        # ------------------------------------------------

        scores_height = len(load_high_scores('highscores', 'score, name', 'score DESC')) + 3
        sprint_scores_height = len(load_high_scores('sprint_highscores', 'time, name', 'time ASC')) + 3
        timed_scores_height = len(load_high_scores('timed_highscores', 'score, lines, name', 'score DESC, lines DESC')) + 3
        garbage_scores_height = len(load_high_scores('garbage_highscores', 'time, name', 'time DESC')) + 3
        menu_y = 5 + scores_height + sprint_scores_height + timed_scores_height + garbage_scores_height

        for i, option in enumerate(menu_options):
            print(term.move_y(menu_y + i) + term.center(' ' * (len(option) + 4))) # Clear previous
            line = f" {option} "
            if i == selected_index:
                print(term.move_y(menu_y + i) + term.center(term.reverse(line)))
            else:
                print(term.move_y(menu_y + i) + term.center(line))

        level_line_y = menu_y + len(menu_options) + 1
        print(term.move_y(level_line_y) + term.center(' ' * 30))

        current_selection = menu_options[selected_index]
        if current_selection in ["Marathon", "Sprint", "Timed", "Garbage"]:
            level_map = {"Marathon": selected_level, "Sprint": sprint_selected_level, "Timed": timed_selected_level, "Garbage": garbage_selected_level}
            print(term.move_y(level_line_y) + term.center(f"< Starting Level {level_map[current_selection]} >"))



        sys.stdout.flush()

        # Use a timeout to allow the animation loop to run
        key = term.inkey(timeout=0.1)
        if not key:
            continue # No key pressed, continue loop to animate

        if key.is_sequence:
            if key.code == term.KEY_UP:
                selected_index = (selected_index - 1) % len(menu_options)
            elif key.code == term.KEY_DOWN:
                selected_index = (selected_index + 1) % len(menu_options)
            elif key.code == term.KEY_LEFT:
                if current_selection == "Marathon":
                    selected_level = max(SETTINGS['MIN_LEVEL'], selected_level - 1)
                elif current_selection == "Sprint":
                    sprint_selected_level = max(SETTINGS['MIN_LEVEL'], sprint_selected_level - 1)
                elif current_selection == "Timed":
                    timed_selected_level = max(SETTINGS['MIN_LEVEL'], timed_selected_level - 1)
                elif current_selection == "Garbage":
                    garbage_selected_level = max(SETTINGS['MIN_LEVEL'], garbage_selected_level - 1)
            elif key.code == term.KEY_RIGHT:
                if current_selection == "Marathon":
                    selected_level = min(SETTINGS['MAX_LEVEL'], selected_level + 1)
                elif current_selection == "Sprint":
                    sprint_selected_level = min(SETTINGS['MAX_LEVEL'], sprint_selected_level + 1)
                elif current_selection == "Timed":
                    timed_selected_level = min(SETTINGS['MAX_LEVEL'], timed_selected_level + 1)
                elif current_selection == "Garbage":
                    garbage_selected_level = min(SETTINGS['MAX_LEVEL'], garbage_selected_level + 1)
            elif key.code == term.KEY_ENTER:
                selection = menu_options[selected_index]
                if selection == "Resume":
                    return "RESUME", None
                elif selection == "Marathon":
                    return "standard", selected_level
                elif selection == "Sprint":
                    return "sprint", sprint_selected_level
                elif selection == "Timed":
                    return "timed", timed_selected_level
                elif selection == "Garbage":
                    return "garbage", garbage_selected_level
                elif selection == "Settings":
                    show_settings(term)
                    redraw_background = True
                    continue
                elif selection == "Quit":
                    return None, None
        elif key == ' ':
            selection = menu_options[selected_index]
            if selection == "Resume":
                return "RESUME", None
            elif selection == "Marathon":
                return "standard", selected_level
            elif selection == "Sprint":
                return "sprint", sprint_selected_level
            elif selection == "Timed":
                return "timed", timed_selected_level
            elif selection == "Garbage":
                return "garbage", garbage_selected_level
            elif selection == "Settings":
                show_settings(term)
                redraw_background = True
                continue
            elif selection == "Quit":
                return None, None
        elif key.lower() == 'q':
            return None, None

def show_score_editor(term: Terminal, scores_dict: dict) -> Optional[dict]:
    """Displays a sub-menu to edit dictionary values like SCORE_VALUES."""
    temp_scores = copy.deepcopy(scores_dict)
    score_options = list(temp_scores.keys())
    selected_index = 0

    while True:
        print(term.home + term.clear)
        print(term.move_y(2) + term.center(term.bold("--- Score Value Editor ---")))

        for i, option in enumerate(score_options):
            value = temp_scores[option]
            display_value = f"{value:.2f}" if isinstance(value, float) else str(value)
            line = f"{option:.<35} {display_value}"

            if i == selected_index:
                print(term.move_y(5 + i) + term.center(term.reverse(line)))
            else:
                print(term.move_y(5 + i) + term.center(line))

        print(term.move_y(term.height - 4) + term.center("Use ↑/↓ to navigate."))
        print(term.move_y(term.height - 3) + term.center("Use ←/→ to change values."))
        print(term.move_y(term.height - 2) + term.center("Press ENTER or 's' to Save & Exit, 'q' to Discard & Exit."))

        key_event = term.inkey()
        key = get_key_repr(key_event)
        option_name = score_options[selected_index]
        current_value = temp_scores[option_name]

        if key == "KEY_UP":
            selected_index = (selected_index - 1) % len(score_options)
        elif key == "KEY_DOWN":
            selected_index = (selected_index + 1) % len(score_options)
        elif key in ["KEY_LEFT", "KEY_RIGHT"]:
            increment = 1 if key == "KEY_RIGHT" else -1
            if isinstance(current_value, int):
                temp_scores[option_name] = max(0, current_value + (increment * 10))
            elif isinstance(current_value, float):
                temp_scores[option_name] = round(max(0.0, current_value + (increment * 0.1)), 2)
        elif key == 's' or key_event.code == term.KEY_ENTER:
            return temp_scores
        elif key == 'q':
            return None

def show_settings(term):
    """
    Displays a full-screen settings menu without a nested border.
    """
    temp_settings = copy.deepcopy(SETTINGS)
    setting_options = list(temp_settings.keys())
    selected_index = 0

    while True:
        # --- Drawing Section ---
        # On each loop, clear the screen and draw everything fresh.
        print(term.home + term.clear, end="")

        # 1. Draw the title at the top of the terminal.
        print(term.move_y(1) + term.center(term.bold("--- Game Settings ---")), end="")

        # 2. Draw the list of settings.
        start_y = 3  # Start drawing the list from the 3rd row.
        for i, option_name in enumerate(setting_options):
            value = temp_settings[option_name]
            display_value = ""
            if option_name == "GHOST_PIECE_ENABLED":
                display_value = "Enabled" if value == 1 else "Disabled"
            elif isinstance(value, dict):
                display_value = "[Press Enter to Edit]"
            elif isinstance(value, float):
                display_value = f"{value:.2f}"
            else:
                display_value = get_key_display_name(str(value))

            # Use the full terminal width for alignment.
            start_x = 2
            end_x = term.width - 2

            # Calculate the filler to span the full width.
            space_for_filler = end_x - start_x - len(option_name) - len(display_value)
            filler = '_' * max(0, space_for_filler)

            line_text = f"{option_name}{filler}{display_value}"

            # Apply reverse styling if the item is selected.
            line_to_print = term.reverse(line_text) if i == selected_index else line_text

            # Move to the correct position and print the line.
            print(term.move_y(start_y + i) + term.move_x(start_x) + line_to_print, end="")

        # 3. Draw the control tips at the bottom of the terminal.
        tips_start_y = term.height - 6
        print(term.move_y(tips_start_y) + term.center("Use ↑/↓ to navigate."), end="")
        print(term.move_y(tips_start_y + 1) + term.center("Use ←/→ to change values."), end="")
        print(term.move_y(tips_start_y + 2) + term.center("Press ENTER to edit values."), end="")
        print(term.move_y(tips_start_y + 3) + term.center("Press 's' to Save & Exit"), end="")
        print(term.move_y(tips_start_y + 4) + term.center("Press 'q' to Discard & Exit"), end="")
        print(term.move_y(tips_start_y + 5) + term.center("Press 'r' to Restore Defaults."), end="")

        # Flush all the print statements to the screen at once.
        sys.stdout.flush()

        # --- Input Handling Section ---
        key_event = term.inkey()
        if not key_event:
            continue
        key = get_key_repr(key_event)

        option_name = setting_options[selected_index]
        current_value = temp_settings.get(option_name)

        if key == "KEY_UP":
            selected_index = (selected_index - 1) % len(setting_options)
        elif key == "KEY_DOWN":
            selected_index = (selected_index + 1) % len(setting_options)
        elif key in ["KEY_LEFT", "KEY_RIGHT"]:
            if option_name == "GHOST_PIECE_ENABLED":
                temp_settings[option_name] = 1 - current_value
            else:
                increment = 1 if key == "KEY_RIGHT" else -1
                if option_name in ["TIMED_MODE_DURATION_S", "GARBAGE_INTERVAL_S"]:
                    increment *= 5
                if isinstance(current_value, int):
                    temp_settings[option_name] = max(1, current_value + increment)
                elif isinstance(current_value, float):
                    temp_settings[option_name] = round(max(0.01, current_value + (increment * 0.05)), 2)
        elif hasattr(key_event, 'code') and key_event.code == term.KEY_ENTER:
            if "Key:" in option_name:
                prompt_y = term.height - 7
                prompt = f"Press new key for {option_name}..."
                # Temporarily draw a prompt over the tips
                print(term.move_y(prompt_y) + term.center(term.black_on_yellow(prompt.ljust(len(prompt)+2))))
                temp_settings[option_name] = get_key_repr(term.inkey())
                # The loop will then redraw everything, clearing the prompt
            elif isinstance(current_value, dict):
                updated_dict = show_score_editor(term, current_value)
                if updated_dict is not None:
                    temp_settings[option_name] = updated_dict
                # After the editor closes, the loop will redraw the main settings screen
        elif key.lower() == 'r':
            prompt_y = term.height - 7
            prompt = "Reset all settings to default? (y/n)"
            print(term.move_y(prompt_y) + term.center(term.black_on_red(prompt.ljust(len(prompt)+2))))
            confirm_key = term.inkey()
            if hasattr(confirm_key, 'lower') and confirm_key.lower() == 'y':
                temp_settings = get_default_settings()
        elif key.lower() == 's':
            save_settings(temp_settings)
            load_settings()
            return
        elif key.lower() == 'q':
            return


def main():
    """Main function to set up the terminal and run the application."""
    initialize_database()
    load_settings()
    term = Terminal()

    # NEW: Instantiate the resize handler and set up the signal
    resize_handler = ResizeHandler()
    original_sigwinch_handler = signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH, resize_handler)

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            while True:
                gamemode, start_level = show_main_menu(term, resize_handler)

                if gamemode is None:
                    break # Quit from main menu

                game = None
                if gamemode == "RESUME":
                    game = load_game_state()
                else:
                    game = Game(gamemode=gamemode, start_level=start_level)

                if game:
                    game_loop(term, game)

                    if game.quit_after_save:
                        break

                    if game.gamemode not in ['sprint', 'timed', 'garbage']:
                        delete_save_state()

                    # Set redraw flag to true after a game ends to refresh the menu
                    resize_handler.dirty = True
                    if not handle_game_over(term, game):
                        break

        except KeyboardInterrupt:
            pass
        except Exception as e:
            # Restore the original signal handler in case of an error
            signal.signal(signal.SIGWINCH, original_sigwinch_handler)
            with open("tetris_error.log", "w") as f:
                f.write(f"An unexpected error occurred: {e}\n")
                import traceback
                traceback.print_exc(file=f)

    # NEW: Always restore the original signal handler on exit
    signal.signal(signal.SIGWINCH, original_sigwinch_handler)

    if 'e' in locals() and isinstance(e, Exception):
        print("An unexpected error occurred. A log file 'tetris_error.log' has been created.")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
