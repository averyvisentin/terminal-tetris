#!/usr/bin/env python3
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
import json # Added for handling complex settings
from typing import List, Tuple, Optional, Any
from blessed import Terminal

# --- Game Configuration & Constants ---
script_dir = os.path.dirname(os.path.abspath(__file__)) # Get the absolute path of the directory containing this script.
DATABASE_FILE = os.path.join(script_dir, 'tetris.db') # Define the database file path to be in the same directory as the script.
SETTINGS = {} # This global dictionary will be populated by load_settings() from the database.

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
PIECE_COLORS = {'I': 'cyan', 'O': 'yellow', 'T': 'magenta', 'S': 'green', 'Z': 'red', 'J': 'blue', 'L': 'orange'}
BLOCK_CHAR = '██'
GHOST_CHAR = '▒▒'

# --- Database & Settings Management ---

def initialize_database():
    """Creates the database and tables if they don't exist."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS highscores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, score INTEGER NOT NULL)')

def save_settings(settings_dict):
    """Saves the entire settings dictionary to the database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        for key, value in settings_dict.items():
            # Serialize dicts to JSON strings before saving
            value_to_save = json.dumps(value) if isinstance(value, dict) else str(value)
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value_to_save))

def load_settings():
    """Loads all settings from the database, applying defaults on first run."""
    global SETTINGS
    defaults = get_default_settings() # Use the new helper function

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

def load_high_scores() -> List[Tuple[int, str]]:
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT score, name FROM highscores ORDER BY score DESC LIMIT ?", (SETTINGS.get('MAX_SCORES', 10),))
        return cursor.fetchall()

def save_high_scores(scores: List[Tuple[int, str]]) -> bool:
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM highscores")
            scores.sort(key=lambda item: item[0], reverse=True)
            for score, name in scores[:SETTINGS.get('MAX_SCORES', 10)]:
                cursor.execute("INSERT INTO highscores (name, score) VALUES (?, ?)", (name, score))
            return True
        except sqlite3.Error:
            return False

def _display_high_scores_list(term: Terminal, start_y: int) -> int:
    print(term.move_y(start_y) + term.center(term.underline("Top High Scores")))
    scores_to_show = load_high_scores()
    if not scores_to_show:
        print(term.center("No scores yet!"))
        return 2
    for i, (score, name) in enumerate(scores_to_show):
        line = f"{i+1}. {name:<{SETTINGS.get('MAX_NAME_LENGTH', 3)}} - {score}"
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
    def __init__(self, start_level: int = 1):
        self.board: List[List[Any]] = [[0 for _ in range(SETTINGS['BOARD_WIDTH'])] for _ in range(SETTINGS['BOARD_HEIGHT'])]
        self.score: int = 0
        self.lines_cleared: int = 0
        self.level: int = start_level
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

        # NEW: Attributes for flash animation
        self.lines_to_flash = []
        self.flash_text = ""
        self.flash_start_time = 0

    def _add_to_upcoming(self):
        if not self.bag: self._refill_bag()
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
            if not (0 <= x < SETTINGS['BOARD_WIDTH'] and y < SETTINGS['BOARD_HEIGHT']): return False
            if y >= 0 and self.board[y][x] != 0: return False
        return True

    def _is_touching_ground(self):
        return not self._is_valid_position(self.current_piece, check_y_offset=1)

    def _lock_piece(self):
        t_spin_type = self._check_t_spin() if self.current_piece.shape_name == 'T' and self.last_move_was_rotation else None
        for x, y in self.current_piece.get_block_locations():
            if y >= 0: self.board[y][x] = self.current_piece.shape_name
        lines_cleared_this_turn = self._clear_lines(t_spin_type)
        if t_spin_type or lines_cleared_this_turn == 4:
            self.is_back_to_back = True
        elif lines_cleared_this_turn > 0:
            self.is_back_to_back = False
        self.can_hold = True
        self.current_piece = self._get_new_piece()
        self.last_move_was_rotation = False
        if not self._is_valid_position(self.current_piece): self.game_over = True

    def _check_t_spin(self):
        piece = self.current_piece
        center_x, center_y = piece.x + 2, piece.y + 1
        corners = [(center_x - 1, center_y - 1), (center_x + 1, center_y - 1), (center_x - 1, center_y + 1), (center_x + 1, center_y + 1)]
        occupied_corners = sum(1 for x, y in corners if not (0 <= x < SETTINGS['BOARD_WIDTH'] and 0 <= y < SETTINGS['BOARD_HEIGHT']) or (y >= 0 and self.board[y][x] != 0))
        if occupied_corners >= 3: return "T_SPIN"
        if occupied_corners == 2:
            front_corners = [corners[i] for i in [[0, 1], [1, 3], [2, 3], [0, 2]][piece.rotation]]
            if any(not (0 <= x < SETTINGS['BOARD_WIDTH'] and 0 <= y < SETTINGS['BOARD_HEIGHT']) or (y >= 0 and self.board[y][x] != 0) for x, y in front_corners):
                return "T_SPIN_MINI"
        return None

    def _clear_lines(self, t_spin_type=None):
        """Clears completed lines, calculates score, and sets up flash animation."""
        lines_to_clear_indices = [i for i, row in enumerate(self.board) if all(cell != 0 for cell in row)]

        if not lines_to_clear_indices and not t_spin_type:
            return 0

        # Set up the flash animation
        self.lines_to_flash = lines_to_clear_indices
        self.flash_start_time = time.time()
        new_board = [row for row in self.board if any(cell == 0 for cell in row)]
        lines_cleared_count = len(self.board) - len(new_board)

        if lines_cleared_count > 0:
            for _ in range(lines_cleared_count):
                new_board.insert(0, [0 for _ in range(SETTINGS['BOARD_WIDTH'])])
            self.board = new_board

        score_key_map = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}
        t_spin_key_map = {1: "T_SPIN_SINGLE", 2: "T_SPIN_DOUBLE", 3: "T_SPIN_TRIPLE"}
        score_key = t_spin_key_map.get(lines_cleared_count, t_spin_type) if t_spin_type else score_key_map.get(lines_cleared_count)

        if score_key:
            # Set the text to be displayed
            self.flash_text = score_key.replace("_", " ")
            base_score = SETTINGS['SCORE_VALUES'].get(score_key, 0)
            is_difficult = "TETRIS" in score_key or "T_SPIN" in score_key
            if is_difficult and self.is_back_to_back:
                base_score *= SETTINGS['SCORE_VALUES']["BACK_TO_BACK_MULTIPLIER"]
            self.score += int(base_score * self.level)

        self.lines_cleared += lines_cleared_count
        self.level = (self.lines_cleared // 10) + 1
        return lines_cleared_count

    def move(self, dx):
        self.current_piece.x += dx
        if not self._is_valid_position(self.current_piece): self.current_piece.x -= dx
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
            self.score += 1
            self.last_move_was_rotation = False
        else: self.initiate_lock_delay()

    def hard_drop(self):
        drop_distance = 0
        while not self._is_touching_ground():
            self.current_piece.y += 1
            drop_distance += 1
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
        if self.lock_delay_start_time == 0: self.lock_delay_start_time = time.time()

    def reset_lock_delay(self):
        self.lock_delay_start_time = 0
        if self._is_touching_ground(): self.initiate_lock_delay()

    def update(self):
        if self.paused or self.game_over: return
        if self._is_touching_ground():
            self.initiate_lock_delay()
            if self.lock_delay_start_time and (time.time() - self.lock_delay_start_time >= SETTINGS["Lock Delay (s)"]):
                self._lock_piece()
        else: self.reset_lock_delay()

    def get_ghost_piece_y(self):
        ghost_piece = copy.deepcopy(self.current_piece)
        while self._is_valid_position(ghost_piece, 1): ghost_piece.y += 1
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
        if py >= 0: print(term.move_xy((px * 2) + offset[0], py + offset[1]) + color_func(char))

def get_key_display_name(key_str):
    if key_str == ' ': return "Space"
    return str(key_str).replace("KEY_", "").replace("_", " ").title()

def draw_ui(term, game):
    print(term.move_xy(0, 0) + term.bold_underline("Terminal Tetris"))
    def draw_box(x, y, w, h, title, content=""):
        print(term.move_xy(x, y) + f"╔{'═'*(w-2)}╗")
        print(term.move_xy(x, y + 1) + f"║ {term.bold(title):<{w-3}}║")
        for i in range(2, h - 1): print(term.move_xy(x, y + i) + f"║{' '*(w-2)}║")
        print(term.move_xy(x, y + h -1) + f"╚{'═'*(w-2)}╝")
        if content: print(term.move_xy(x + 2, y + 2) + str(content))

    draw_box(0, 2, 20, 4, "SCORE", f"{game.score}")
    draw_box(0, 7, 20, 4, "LEVEL", f"{game.level}")
    draw_box(0, 12, 20, 4, "LINES", f"{game.lines_cleared}")
    if game.is_back_to_back: print(term.move_xy(2, 17) + term.yellow_bold("Back-to-Back!"))

    next_box_x = SETTINGS['PLAYFIELD_X_OFFSET'] + SETTINGS['BOARD_WIDTH'] * 2 + 5
    next_box_y = SETTINGS['PLAYFIELD_Y_OFFSET']
    draw_box(next_box_x, next_box_y, 16, 22, "NEXT")
    for i, shape_name in enumerate(game.upcoming_pieces):
        if i >= 4: break
        display_piece = Piece(shape_name)
        display_piece.x = 0; display_piece.y = 0
        draw_piece(term, display_piece, offset=(next_box_x + 4, next_box_y + 2 + (i * 5)))

    hold_box_x, hold_box_y = next_box_x, next_box_y + 23
    draw_box(hold_box_x, hold_box_y, 16, 7, "HOLD")
    if game.hold_piece:
        hold_piece_display = Piece(game.hold_piece.shape_name)
        hold_piece_display.x = 0; hold_piece_display.y = 0
        draw_piece(term, hold_piece_display, offset=(hold_box_x + 4, hold_box_y + 2))

    controls_y = hold_box_y + 8
    print(term.move_xy(hold_box_x, controls_y) + term.bold("Controls:"))
    controls = {"Move": f"{get_key_display_name(SETTINGS['Key: Left'])}/{get_key_display_name(SETTINGS['Key: Right'])}", "Rotate": get_key_display_name(SETTINGS['Key: Rotate']), "Soft Drop": get_key_display_name(SETTINGS['Key: Soft Drop']), "Hard Drop": get_key_display_name(SETTINGS['Key: Hard Drop']), "Hold": get_key_display_name(SETTINGS['Key: Hold']), "Pause": "P", "Quit": "Q"}
    for i, (action, key) in enumerate(controls.items()): print(term.move_xy(hold_box_x, controls_y + 1 + i) + f"{key:<10}: {action}")

def draw_game_state(term, game):
    print(term.home + term.clear_eos, end='')
    draw_board_border(term)
    draw_ui(term, game)

    # Draw all the locked blocks on the board
    for y, row in enumerate(game.board):
        for x, cell in enumerate(row):
            if cell != 0:
                color = get_color(term, PIECE_COLORS[cell])
                print(term.move_xy(x * 2 + SETTINGS['PLAYFIELD_X_OFFSET'], y + SETTINGS['PLAYFIELD_Y_OFFSET']) + color(BLOCK_CHAR))

    # --- NEW: Flash Animation Logic ---
    FLASH_DURATION = 0.2
    if game.lines_to_flash and (time.time() - game.flash_start_time < SETTINGS['FLASH_DURATION']):
        # Draw the flashing lines
        for y in game.lines_to_flash:
            for x in range(SETTINGS['BOARD_WIDTH']):
                print(term.move_xy(x * 2 + SETTINGS['PLAYFIELD_X_OFFSET'], y + SETTINGS['PLAYFIELD_Y_OFFSET']) + term.white_on_white(BLOCK_CHAR))

        # Display the clear text
        if game.flash_text:
            print(term.move_xy(2, 17) + term.cyan_bold(game.flash_text))
    else:
        # Reset flash state after duration
        game.lines_to_flash = []
        game.flash_text = ""

    # Draw ghost piece only if the setting is enabled
    if SETTINGS.get('GHOST_PIECE_ENABLED') == 1:
        ghost_y = game.get_ghost_piece_y()
        if ghost_y > game.current_piece.y:
            ghost_piece = copy.deepcopy(game.current_piece)
            ghost_piece.y = ghost_y
            draw_piece(term, ghost_piece, offset=(SETTINGS['PLAYFIELD_X_OFFSET'], SETTINGS['PLAYFIELD_Y_OFFSET']), is_ghost=True)

    # Draw the current, active piece
    draw_piece(term, game.current_piece, offset=(SETTINGS['PLAYFIELD_X_OFFSET'], SETTINGS['PLAYFIELD_Y_OFFSET']))

    if game.paused:
        msg = "PAUSED"
        print(term.move_xy(SETTINGS['PLAYFIELD_X_OFFSET'] + SETTINGS['BOARD_WIDTH'] - len(msg)//2, SETTINGS['PLAYFIELD_Y_OFFSET'] + SETTINGS['BOARD_HEIGHT']//2) + term.black_on_white(msg))

def get_key_repr(key):
    if key.is_sequence: return key.name
    return str(key)

def handle_input(term: Terminal, game: Game):
    key_event = term.inkey(timeout=SETTINGS['INPUT_TIMEOUT'])
    if not key_event: return
    key = get_key_repr(key_event)
    if not game.paused:
        if key == SETTINGS["Key: Left"]: game.move(-1)
        elif key == SETTINGS["Key: Right"]: game.move(1)
        elif key == SETTINGS["Key: Rotate"]: game.rotate()
        elif key == SETTINGS["Key: Soft Drop"]: game.soft_drop()
        elif key == SETTINGS["Key: Hard Drop"]: game.hard_drop()
        elif key == SETTINGS["Key: Hold"]: game.hold()
    if key == 'p': game.paused = not game.paused
    elif key == 'q': game.game_over = True

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
    high_scores = load_high_scores()
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
            elif len(player_name) < SETTINGS['MAX_NAME_LENGTH'] and not key.is_sequence and key.isalnum(): player_name += key.upper()
        high_scores.append((game.score, player_name))
        save_high_scores(high_scores)
    while True:
        print(term.home + term.clear)
        print(term.move_y(term.height // 2 - 8) + term.center(term.bold("GAME OVER")))
        print(term.center(f"Final Score: {game.score}"))
        _display_high_scores_list(term, term.height // 2 - 4)
        print(term.move_y(term.height - 3) + term.center("Press 'SPACE' for Main Menu or 'q' to Quit"))
        key = term.inkey()
        if key.lower() == ' ': return True
        elif key.lower() == 'q': return False

def get_default_settings() -> dict:
    """Returns a dictionary containing all default game settings."""
    return {
        # Board and UI
        "BOARD_WIDTH": 10, "BOARD_HEIGHT": 40, "PLAYFIELD_X_OFFSET": 25, "PLAYFIELD_Y_OFFSET": 2,
        # High Scores
        "MAX_SCORES": 10, "MAX_NAME_LENGTH": 3,
        # Timing
        "INITIAL_GRAVITY_INTERVAL": 1.0, "GRAVITY_LEVEL_MULTIPLIER": 0.09, "MIN_GRAVITY_INTERVAL": 0.1,
        "INPUT_TIMEOUT": 0.01, "RENDER_THROTTLE_MS": 16, "Lock Delay (s)": 0.5,
        "FLASH_DURATION": 0.2,
        # Gameplay
        "MIN_LEVEL": 1, "MAX_LEVEL": 15, "GHOST_PIECE_ENABLED": 1,
        # Scoring
        "SCORE_VALUES": {"SINGLE": 100, "DOUBLE": 300, "TRIPLE": 500, "TETRIS": 800, "T_SPIN_MINI": 100, "T_SPIN": 400, "T_SPIN_SINGLE": 800, "T_SPIN_DOUBLE": 1200, "T_SPIN_TRIPLE": 1600, "BACK_TO_BACK_MULTIPLIER": 1.5},
        # Keybindings
        "Key: Left": "KEY_LEFT", "Key: Right": "KEY_RIGHT", "Key: Rotate": "KEY_UP",
        "Key: Soft Drop": "KEY_DOWN", "Key: Hard Drop": ' ', "Key: Hold": 'c',
    }

def show_main_menu(term):
    selected_level = SETTINGS['MIN_LEVEL']
    while True:
        print(term.home + term.clear)
        print(term.move_y(term.height // 2 - 12) + term.center(term.bold("Terminal Tetris")))
        scores_height = _display_high_scores_list(term, term.height // 2 - 9)
        menu_y = term.height // 2 - 9 + scores_height + 2
        print(term.move_y(menu_y) + term.center(term.bold("--- Level Select ---")))
        print(term.center(f"< Level {selected_level} >"))
        print(term.center("(Use ←/→ to change)"))
        prompt_y = term.height - 5
        print(term.move_y(prompt_y) + term.center("Press SPACE to Play"))
        print(term.move_y(prompt_y + 1) + term.center("Press 's' for Settings"))
        print(term.move_y(prompt_y + 2) + term.center("Press 'q' to Quit"))
        print(term.move_y(prompt_y + 3) + term.center("""
            Tetris © 1985~2025 Tetris Holding.
            Tetris logos and Tetriminos are trademarks of Tetris Holding.
            The Tetris trade dress is owned by Tetris Holding.
            Licensed to The Tetris Company.
            Tetris Game Design by Alexey Pajitnov.
            Tetris Logo Design by Roger Dean.
            Licensed to The Tetris Company.
            All Rights Reserved."""))
        key = term.inkey()
        if key == ' ': return selected_level
        elif key == 'q': return None
        elif key.code == term.KEY_LEFT: selected_level = max(SETTINGS['MIN_LEVEL'], selected_level - 1)
        elif key.code == term.KEY_RIGHT: selected_level = min(SETTINGS['MAX_LEVEL'], selected_level + 1)
        elif key == 's': show_settings(term)

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

        print(term.move_y(term.height - 3) + term.center("Use ↑/↓ to navigate. Use ←/→ to change values."))
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
            return temp_scores # Return the edited dictionary
        elif key == 'q':
            return None # Return None to indicate cancellation

def show_settings(term):
    """
    Displays the settings menu, optimized to reduce flickering by only
    redrawing parts of the screen that have changed.
    """
    temp_settings = copy.deepcopy(SETTINGS)
    setting_options = list(temp_settings.keys())
    selected_index = 0

    def redraw_all(selected_idx):
        """Clears and redraws the entire settings screen."""
        print(term.home + term.clear, end="")
        print(term.move_y(2) + term.center(term.bold("--- Game Settings ---")), end="")

        for i, option in enumerate(setting_options):
            draw_line(i, is_selected=(i == selected_idx))

        # Instructions
        print(term.move_y(term.height - 5) + term.center("Use ↑/↓ to navigate. Use ←/→ to change values."), end="")
        print(term.move_y(term.height - 4) + term.center("Press ENTER to change a keybinding or edit values."), end="")
        print(term.move_y(term.height - 3) + term.center("Press 's' to Save & Exit, or 'q' to Discard & Exit."), end="")
        print(term.move_y(term.height - 2) + term.center("Press 'd' to Restore Defaults."), end="")
        sys.stdout.flush()

    def draw_line(index, is_selected):
        """Draws a single line of the settings menu."""
        option_name = setting_options[index]
        value = temp_settings[option_name]

        # Determine the display value string
        display_value = ""
        if option_name == "GHOST_PIECE_ENABLED":
            display_value = "Enabled" if value == 1 else "Disabled"
        elif isinstance(value, dict):
            display_value = "[Press Enter to Edit]"
        elif isinstance(value, float):
            display_value = f"{value:.2f}"
        else:
            display_value = get_key_display_name(str(value))

        line = f"{option_name:.<35} {display_value}"

        with term.location(y=5 + index):
            # Center the line. Add padding to clear previous, longer text.
            print(term.center(line.ljust(50)))

        with term.location(y=5 + index):
             if is_selected:
                print(term.center(term.reverse(line)))
             else:
                print(term.center(line))

    redraw_all(selected_index)
    previous_index = selected_index

    while True:
        # Update visuals only if selection changed
        if selected_index != previous_index:
            draw_line(previous_index, is_selected=False) # De-highlight old
            draw_line(selected_index, is_selected=True)  # Highlight new
            sys.stdout.flush()

        previous_index = selected_index

        # Wait for input
        key_event = term.inkey()
        key = get_key_repr(key_event)

        # Handle input and update state
        option_name = setting_options[selected_index]
        current_value = temp_settings.get(option_name)

        if key == "KEY_UP":
            selected_index = (selected_index - 1) % len(setting_options)
        elif key == "KEY_DOWN":
            selected_index = (selected_index + 1) % len(setting_options)

        elif key in ["KEY_LEFT", "KEY_RIGHT"]:
            if option_name == "GHOST_PIECE_ENABLED":
                temp_settings[option_name] = 1 - current_value #says its a bug but won't work without it

            else:
                increment = 1 if key == "KEY_RIGHT" else -1
                if isinstance(current_value, int):
                    temp_settings[option_name] += increment
                elif isinstance(current_value, float):
                    temp_settings[option_name] = round(current_value + (increment * 0.05), 2)
            draw_line(selected_index, is_selected=True) # Redraw the updated line
            sys.stdout.flush()

        elif key_event.code == term.KEY_ENTER:
            if "Key:" in option_name:
                prompt_y = term.height - 7
                prompt = f"Press new key for {option_name}..."
                with term.location(y=prompt_y):
                    print(term.center(term.black_on_yellow(prompt.ljust(len(prompt)+2))))

                temp_settings[option_name] = get_key_repr(term.inkey())

                with term.location(y=prompt_y):
                    print(term.center(" " * (len(prompt) + 2))) # Clear prompt
                draw_line(selected_index, is_selected=True)
                sys.stdout.flush()

            elif isinstance(current_value, dict):
                updated_dict = show_score_editor(term, current_value)
                if updated_dict is not None:
                    temp_settings[option_name] = updated_dict
                # A full redraw is necessary after returning from a sub-menu
                redraw_all(selected_index)

        elif key.lower() == 'd':
            prompt_y = term.height - 7
            prompt = "Reset all settings to default? (y/n)"
            with term.location(y=prompt_y):
                print(term.center(term.black_on_red(prompt.ljust(len(prompt)+2))))

            confirm_key = term.inkey()
            with term.location(y=prompt_y):
                print(term.center(" " * (len(prompt) + 2))) # Clear prompt

            if confirm_key.lower() == 'y':
                temp_settings = get_default_settings()
                redraw_all(selected_index)
            else: # Redraw the line the prompt was covering
                draw_line(selected_index, is_selected=True)
                sys.stdout.flush()

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
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            while True:
                start_level = show_main_menu(term)
                if start_level is None: break
                print(term.home + term.clear) # Clear screen once before a new game
                draw_board_border(term)
                draw_ui(term, Game(start_level=start_level)) # Draw the static UI elements
                sys.stdout.flush()
                game = Game(start_level=start_level)
                game_loop(term, game)
                if not handle_game_over(term, game): break
        except KeyboardInterrupt: pass
        except Exception as e:
            # This block might not print if the terminal state is corrupted.
            # It's here as a last resort.
            pass
    # After exiting the blessed context, we can safely print errors.
    if 'e' in locals() and isinstance(e, Exception):
        print("An unexpected error occurred:")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
