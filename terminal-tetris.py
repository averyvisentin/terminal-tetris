#!/usr/bin/env python3
"""
Terminal Tetris Game
A fully-featured Tetris implementation for the terminal with modern mechanics.

Features:
- Classic Tetris gameplay with proper mechanics
- T-Spin detection and scoring
- Back-to-back bonus system
- Hold functionality
- Ghost piece preview
- High score tracking
- Level progression
- Proper lock delay
- Bag randomization system

Author: avery
"""

# Import necessary libraries
import time  # For handling time-based events like gravity and lock delays
import random  # For shuffling the bag of tetrominoes
import os  # For handling file operations, specifically for the high score file
from typing import List, Tuple, Optional, Any
from blessed import Terminal  # A library to make terminal output colorful, styled, and positioned

# --- Game Configuration & Constants ---

# Game board dimensions in terms of blocks
BOARD_WIDTH = 10
BOARD_HEIGHT = 30

# The (x, y) coordinates for the top-left corner of the playable area in the terminal.
# This allows us to position the game board anywhere on the screen.
PLAYFIELD_X_OFFSET = 25
PLAYFIELD_Y_OFFSET = 2

# High score configuration
HIGHSCORE_FILE = 'highscores.txt'  # The name of the file where scores are saved
MAX_SCORES = 5  # The maximum number of high scores to keep track of

# Game timing and input configuration
INITIAL_GRAVITY_INTERVAL = 0.8  # Starting gravity speed in seconds
GRAVITY_LEVEL_MULTIPLIER = 0.05  # How much faster gravity gets per level
MIN_GRAVITY_INTERVAL = 0.05  # Minimum gravity interval (maximum speed)
INPUT_TIMEOUT = 0.01  # Timeout for input polling in seconds
RENDER_THROTTLE_MS = 16  # Minimum milliseconds between renders (~60 FPS)

# Level and name configuration
MIN_LEVEL = 1
MAX_LEVEL = 15
MAX_NAME_LENGTH = 3  # Maximum characters for player name

# Tetromino shapes and their colors.
# Each shape is a dictionary key ('I', 'O', 'T', etc.).
# The value is a list of its 4 rotational states.
# Each rotational state is a 5x5 grid represented by a list of strings.
# 'O' represents a solid block of the piece. '.' represents empty space within the 5x5 grid.
# This 5x5 grid allows for a consistent center of rotation for all pieces.
SHAPES = {
    'I': [['.....', '..O..', '..O..', '..O..', '..O..'],
          ['.....', '.....', 'OOOO.', '.....', '.....'],
          ['.O...', '.O...', '.O...', '.O...', '.....'],
          ['.....', '.....', '.OOOO', '.....', '.....']],
    'O': [['.....', '.OO..', '.OO..', '.....', '.....'],
          ['.....', '.OO..', '.OO..', '.....', '.....'],
          ['.....', '.OO..', '.OO..', '.....', '.....'],
          ['.....', '.OO..', '.OO..', '.....', '.....']],
    'T': [['.....', '..O..', '.OOO.', '.....', '.....'],
          ['.....', '..O..', '..OO.', '..O..', '.....'],
          ['.....', '.....', '.OOO.', '..O..', '.....'],
          ['.....', '..O..', '.OO..', '..O..', '.....']],
    'S': [['.....', '..OO.', '.OO..', '.....', '.....'],
          ['.....', '.O...', '.OO..', '..O..', '.....'],
          ['.....', '..OO.', '.OO..', '.....', '.....'],
          ['.....', '.O...', '.OO..', '..O..', '.....']],
    'Z': [['.....', '.OO..', '..OO.', '.....', '.....'],
          ['.....', '..O..', '.OO..', '.O...', '.....'],
          ['.....', '.OO..', '..OO.', '.....', '.....'],
          ['.....', '..O..', '.OO..', '.O...', '.....']],
    'J': [['.....', '.O...', '.OOO.', '.....', '.....'],
          ['.....', '..OO.', '..O..', '..O..', '.....'],
          ['.....', '.....', '.OOO.', '...O.', '.....'],
          ['.....', '..O..', '..O..', '.OO..', '.....']],
    'L': [['.....', '...O.', '.OOO.', '.....', '.....'],
          ['.....', '..O..', '..O..', '..OO.', '.....'],
          ['.....', '.....', '.OOO.', '.O...', '.....'],
          ['.....', '.OO..', '..O..', '..O..', '.....']]
}

# A dictionary mapping each shape to a color name that the `blessed` library understands.
PIECE_COLORS = {
    'I': 'cyan',
    'O': 'yellow',
    'T': 'magenta',
    'S': 'green',
    'Z': 'red',
    'J': 'blue',
    'L': 'orange'
}

# --- Scoring based on modern Tetris guidelines ---
# Points are awarded per line clear, with bonuses for difficult clears like T-Spins and Tetrises.
# The base score is multiplied by the current level.
SCORE_VALUES = {
    "SINGLE": 100, "DOUBLE": 300, "TRIPLE": 500, "TETRIS": 800,
    "T_SPIN_MINI": 100, "T_SPIN": 400,
    "T_SPIN_SINGLE": 800, "T_SPIN_DOUBLE": 1200, "T_SPIN_TRIPLE": 1600,
    "BACK_TO_BACK_MULTIPLIER": 1.5  # Bonus for consecutive difficult clears
}

# --- Lock Down Logic Configuration ---
LOCK_DELAY_DURATION = 0.5  # The piece can be moved for 0.5s after touching the ground before it locks.

# Characters for rendering blocks. Using two characters makes blocks appear more square-like in most terminals.
BLOCK_CHAR = '██'  # For solid, locked pieces or the current piece
GHOST_CHAR = '▒▒'  # For the ghost piece showing where the current piece will land
EMPTY_CHAR = '  '   # Represents an empty cell on the board

# --- High Score Management ---

def load_high_scores() -> List[Tuple[int, str]]:
    """Loads high scores from the specified file."""
    if not os.path.exists(HIGHSCORE_FILE):
        return []

    scores = []
    try:
        with open(HIGHSCORE_FILE, 'r') as f:
            for line in f:
                try:
                    # Each line is expected to be "NAME SCORE". We split it and store it.
                    name, score = line.strip().split()
                    scores.append((int(score), name))
                except ValueError:
                    # Skip lines that don't have the expected format.
                    continue
    except IOError:
        # If file can't be read, return empty list
        return []

    # Sort by score in descending order (highest first).
    scores.sort(key=lambda item: item[0], reverse=True)
    return scores[:MAX_SCORES]

def save_high_scores(scores: List[Tuple[int, str]]) -> bool:
    """Saves the provided list of scores to the high score file."""
    try:
        # Sort the scores just in case they aren't already.
        scores.sort(key=lambda item: item[0], reverse=True)
        # Open the file in write mode, which overwrites the existing file.
        with open(HIGHSCORE_FILE, 'w') as f:
            # Write only the top scores, up to MAX_SCORES.
            for score, name in scores[:MAX_SCORES]:
                f.write(f"{name} {score}\n")
        return True
    except IOError:
        # If file can't be written, return False
        return False

def _display_high_scores_list(term: Terminal, start_y: int) -> int:
    """A helper function to print the high score list on the screen.

    Returns the number of lines used for the high score display.
    """
    print(term.move_y(start_y) + term.center(term.underline("Top 5 High Scores")))
    scores_to_show = load_high_scores()
    if not scores_to_show:
        print(term.center("No scores yet!"))
        return 2  # Return the number of lines printed for layout calculations
    # Loop through the scores and print them.
    for i, (score, name) in enumerate(scores_to_show):
        # The `<` in `{name:<3}` left-aligns the name in a space of 3 characters.
        line = f"{i+1}. {name:<3} - {score}"
        print(term.center(line))
    # Return the number of lines printed for layout calculations.
    return len(scores_to_show) + 2

# --- Core Game Logic Classes (The "Model") ---

class Piece:
    """Represents a single tetromino piece (I, O, T, etc.)."""

    def __init__(self, shape_name: str):
        """Initializes a new piece with its shape, color, and default position."""
        self.shape_name: str = shape_name
        self.shape_matrices: List[List[str]] = SHAPES[shape_name]  # Get the rotation matrices from the SHAPES constant
        self.color: str = PIECE_COLORS[shape_name]
        self.rotation: int = 0  # Start at the first rotation (index 0)
        # Start the piece horizontally centered and slightly above the visible board.
        self.x: int = BOARD_WIDTH // 2 - 2
        self.y: int = -2

    def get_current_shape_matrix(self) -> List[str]:
        """Returns the 5x5 string matrix for the piece's current rotation."""
        return self.shape_matrices[self.rotation]

    def get_block_locations(self) -> List[Tuple[int, int]]:
        """Calculates the absolute (x, y) board coordinates of each of the piece's four blocks.

        Translates the 'O' characters from the 5x5 local matrix to global board coordinates.
        """
        positions = []
        shape = self.get_current_shape_matrix()
        # `enumerate` gives us both the index (r, c) and the value (row_str, char).
        for r, row_str in enumerate(shape):
            for c, char in enumerate(row_str):
                if char == 'O':
                    # Add the piece's top-left (x, y) to the block's relative (c, r) to get board coordinates.
                    positions.append((self.x + c, self.y + r))
        return positions

class Game:
    """Manages the entire state and logic of the Tetris game."""

    def __init__(self, start_level: int = 1):
        """Initializes the game board, score, level, and pieces."""
        # The board is a 2D list (grid). 0 means empty, a shape name (e.g., 'T') means a locked block.
        self.board: List[List[Any]] = [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.score: int = 0
        self.lines_cleared: int = 0
        self.level: int = start_level
        self.game_over: bool = False
        self.paused: bool = False

        # The "bag" system ensures all 7 pieces appear once before any piece repeats.
        self.bag: List[str] = []
        self._refill_bag()

        # The active piece, the upcoming piece, and the piece in the hold slot.
        self.current_piece: Piece = self._new_piece()
        self.next_piece: Piece = self._new_piece()
        self.hold_piece: Optional[Piece] = None
        self.can_hold: bool = True  # You can only hold once per piece.

        # --- State for advanced mechanics ---
        self.is_back_to_back: bool = False  # True if the last clear was a Tetris or T-Spin
        self.last_move_was_rotation: bool = False # Used to check for T-Spins
        self.lock_delay_start_time: float = 0  # Timestamp for when the lock delay started

    def _refill_bag(self):
        """Fills the bag with one of each of the 7 pieces and shuffles it."""
        if not self.bag:  # Check if the bag is empty
            self.bag = list(SHAPES.keys())
            random.shuffle(self.bag)

    def _new_piece(self):
        """Gets a new piece from the bag, refilling the bag if it's empty."""
        if not self.bag:
            self._refill_bag()
        # Pop a shape name from the bag and create a new Piece object.
        return Piece(self.bag.pop())

    def _is_valid_position(self, piece, check_y_offset=0):
        """
        Checks if the piece's current position (or a potential future position) is valid.
        A position is valid if it's within the board boundaries and not colliding with locked blocks.
        """
        block_locations = piece.get_block_locations()
        for x, y in block_locations:
            y += check_y_offset  # Apply an optional vertical offset for checking moves (like soft drop)
            # Check for collision with walls or the floor.
            if not (0 <= x < BOARD_WIDTH and y < BOARD_HEIGHT):
                return False
            # Check for collision with existing locked blocks on the board.
            # We only check if y >= 0 because negative y values are above the visible board.
            if y >= 0 and self.board[y][x] != 0:
                return False
        return True

    def _is_touching_ground(self):
        """Checks if the current piece is resting on the floor or another piece."""
        # It does this by checking if the position *one block below* the current one is invalid.
        return not self._is_valid_position(self.current_piece, check_y_offset=1)

    def _lock_piece(self):
        """Locks the current piece onto the board, making it part of the terrain."""
        # Check for a T-Spin *before* locking, as the check depends on the piece's final move.
        t_spin_type = self._check_t_spin() if self.current_piece.shape_name == 'T' and self.last_move_was_rotation else None

        # Add the piece's blocks to the board grid.
        for x, y in self.current_piece.get_block_locations():
            if y >= 0:
                self.board[y][x] = self.current_piece.shape_name

        # Clear any completed lines and get the score.
        lines_cleared_this_turn = self._clear_lines(t_spin_type)

        # Update back-to-back status for scoring bonuses.
        if t_spin_type or lines_cleared_this_turn == 4: # A "difficult" clear
            self.is_back_to_back = True
        elif lines_cleared_this_turn > 0: # A "simple" clear resets the bonus
            self.is_back_to_back = False

        # Reset state for the next piece.
        self.can_hold = True
        self.current_piece = self.next_piece
        self.next_piece = self._new_piece()
        self.last_move_was_rotation = False

        # If the new piece spawns in an invalid position, the game is over.
        if not self._is_valid_position(self.current_piece):
            self.game_over = True

    def _check_t_spin(self):
        """
        Checks for a T-Spin by examining the corners around the T piece's center.
        The center of our 5x5 T-piece matrix is at grid offset (2, 1).
        A T-Spin requires 3 of the 4 corners to be occupied.
        A Mini T-Spin requires 2 corners occupied.
        """
        piece = self.current_piece
        # T-piece center's board coordinates
        center_x, center_y = piece.x + 2, piece.y + 1

        # The four diagonal corners relative to the T-piece's center.
        corners = [
            (center_x - 1, center_y - 1),  # Top-left
            (center_x + 1, center_y - 1),  # Top-right
            (center_x - 1, center_y + 1),  # Bottom-left
            (center_x + 1, center_y + 1)   # Bottom-right
        ]

        occupied_corners = 0
        for x, y in corners:
            # A corner is "occupied" if it's outside the board or contains a locked block.
            if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT) or (y >= 0 and self.board[y][x] != 0):
                occupied_corners += 1

        if occupied_corners >= 3:
            return "T_SPIN"

        # Check for Mini T-Spin (a less common but official rule).
        # It requires 2 occupied corners, and one of them must be a "front" corner relative to the T's rotation.
        if occupied_corners == 2:
            # Determine which corners are "front" corners based on the T's rotation.
            front_corners = [corners[0], corners[1]] if piece.rotation == 0 else \
                            [corners[1], corners[3]] if piece.rotation == 1 else \
                            [corners[2], corners[3]] if piece.rotation == 2 else \
                            [corners[0], corners[2]]
            # Check if at least one of the front corners is occupied.
            for x, y in front_corners:
                if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT) or (y >= 0 and self.board[y][x] != 0):
                    return "T_SPIN_MINI"
        return None

    def _clear_lines(self, t_spin_type=None):
        """Clears completed lines, calculates score, and updates game state."""
        # A list comprehension to create a new board with only the incomplete rows.
        # `any(cell == 0 for cell in row)` is True if the row has at least one empty cell.
        new_board = [row for row in self.board if any(cell == 0 for cell in row)]
        lines_cleared_count = BOARD_HEIGHT - len(new_board)

        # If no lines were cleared and it wasn't a T-Spin, there's nothing to do.
        if lines_cleared_count == 0 and not t_spin_type:
             return 0

        # Add new empty lines at the top to replace the cleared ones.
        for _ in range(lines_cleared_count):
            new_board.insert(0, [0 for _ in range(BOARD_WIDTH)])
        self.board = new_board

        # --- Scoring Logic ---
        base_score = 0
        score_key = ""
        # Determine the score key based on the T-Spin type and number of lines cleared.
        if t_spin_type:
            if lines_cleared_count == 1: score_key = "T_SPIN_SINGLE"
            elif lines_cleared_count == 2: score_key = "T_SPIN_DOUBLE"
            elif lines_cleared_count == 3: score_key = "T_SPIN_TRIPLE"
            else: score_key = t_spin_type # For T-Spin with 0 lines cleared
        else: # Regular line clears
            if lines_cleared_count == 1: score_key = "SINGLE"
            elif lines_cleared_count == 2: score_key = "DOUBLE"
            elif lines_cleared_count == 3: score_key = "TRIPLE"
            elif lines_cleared_count == 4: score_key = "TETRIS"

        if score_key:
            base_score = SCORE_VALUES.get(score_key, 0)
            # Apply Back-to-Back bonus if applicable.
            is_difficult_clear = "TETRIS" in score_key or "T_SPIN" in score_key
            if is_difficult_clear and self.is_back_to_back:
                base_score *= SCORE_VALUES["BACK_TO_BACK_MULTIPLIER"]

        # Final score is the base score multiplied by the level.
        self.score += int(base_score * self.level)
        self.lines_cleared += lines_cleared_count
        # Level increases every 10 lines cleared.
        self.level = (self.lines_cleared // 10) + 1
        return lines_cleared_count

    def move(self, dx):
        """Moves the current piece horizontally if the move is valid."""
        self.current_piece.x += dx
        if not self._is_valid_position(self.current_piece):
            # If the move was invalid, move it back.
            self.current_piece.x -= dx
        else:
            # A successful move was not a rotation.
            self.last_move_was_rotation = False
            self.reset_lock_delay()

    def rotate(self):
        """Rotates the current piece, trying 'wall kicks' if the initial rotation fails."""
        original_rotation = self.current_piece.rotation
        self.current_piece.rotation = (self.current_piece.rotation + 1) % 4 # Cycle through 0, 1, 2, 3
        if not self._is_valid_position(self.current_piece):
            # If the simple rotation is invalid, try "wall kicking" (shifting left/right).
            for kick_x in [-1, 1, -2, 2]:
                self.current_piece.x += kick_x
                if self._is_valid_position(self.current_piece):
                    # Found a valid position after a kick.
                    self.last_move_was_rotation = True
                    self.reset_lock_delay()
                    return # Exit the function
                self.current_piece.x -= kick_x # Revert the kick if it didn't work.
            # If all kicks fail, revert the rotation itself.
            self.current_piece.rotation = original_rotation
        else:
            # The simple rotation was valid.
            self.last_move_was_rotation = True
            self.reset_lock_delay()

    def soft_drop(self):
        """Moves the piece down by one row and adds a small score."""
        if not self._is_touching_ground():
            self.current_piece.y += 1
            self.score += 1 # Small bonus for actively dropping
            self.last_move_was_rotation = False
        else:
            # If it's already on the ground, dropping again should start the lock timer.
            self.initiate_lock_delay()

    def hard_drop(self):
        """Instantly drops the piece to the bottom and locks it."""
        drop_distance = 0
        # Keep moving the piece down until it's touching the ground.
        while not self._is_touching_ground():
            self.current_piece.y += 1
            drop_distance += 1
        # Award score based on how far it dropped.
        self.score += drop_distance * 2
        self._lock_piece() # Immediately lock the piece.

    def hold(self):
        """Swaps the current piece with the piece in the hold slot."""
        if self.can_hold:
            if self.hold_piece is None:
                # If hold is empty, the current piece goes to hold, and a new piece becomes current.
                self.hold_piece = Piece(self.current_piece.shape_name)
                self.current_piece = self.next_piece
                self.next_piece = self._new_piece()
            else:
                # Swap the current piece and the hold piece.
                current_shape_name = self.current_piece.shape_name
                self.current_piece = Piece(self.hold_piece.shape_name)
                self.hold_piece = Piece(current_shape_name)
            # Disable holding again until the next piece is locked.
            self.can_hold = False
            self.last_move_was_rotation = False

    def initiate_lock_delay(self):
        """Starts the lock delay timer if it hasn't already started."""
        if self.lock_delay_start_time == 0:
            self.lock_delay_start_time = time.time()

    def reset_lock_delay(self):
        """Resets the lock delay timer. If the piece is still on the ground, it restarts the timer."""
        if self._is_touching_ground():
            self.initiate_lock_delay()
        else:
            self.lock_delay_start_time = 0

    def update(self):
        """The main game logic update tick, called repeatedly in the game loop."""
        if self.paused or self.game_over: return

        # Handle the lock delay logic.
        if self._is_touching_ground():
            self.initiate_lock_delay()
            # If the piece has been on the ground for longer than the lock delay duration, lock it.
            if time.time() - self.lock_delay_start_time >= LOCK_DELAY_DURATION:
                self._lock_piece()
        else:
            # If the piece is in the air, there is no lock delay.
            self.reset_lock_delay()

    def get_ghost_piece_y(self):
        """Calculates the Y position of the 'ghost piece' (where the current piece will land)."""
        # Create a temporary copy of the current piece to manipulate.
        ghost_piece = Piece(self.current_piece.shape_name)
        ghost_piece.x = self.current_piece.x
        ghost_piece.y = self.current_piece.y
        ghost_piece.rotation = self.current_piece.rotation
        # Keep moving the ghost piece down until its next position would be invalid.
        while self._is_valid_position(ghost_piece, 1):
            ghost_piece.y += 1
        return ghost_piece.y

# --- Rendering Logic (The "View" and "Controller") ---

def get_color(term, color_name):
    """A helper to safely get a color function from the blessed terminal object."""
    # `getattr(obj, name, default)` is like `obj.name` but returns `default` if `name` doesn't exist.
    return getattr(term, color_name, term.white)

def draw_board_border(term):
    """Draws a box character border around the playfield."""
    x, y = PLAYFIELD_X_OFFSET - 2, PLAYFIELD_Y_OFFSET - 1
    # Top border
    print(term.move_xy(x, y) + '╔' + '═' * (BOARD_WIDTH * 2 + 2) + '╗')
    # Side borders
    for i in range(BOARD_HEIGHT):
        print(term.move_xy(x, y + 1 + i) + '║')
        print(term.move_xy(x + BOARD_WIDTH * 2 + 3, y + 1 + i) + '║')
    # Bottom border
    print(term.move_xy(x, y + BOARD_HEIGHT + 1) + '╚' + '═' * (BOARD_WIDTH * 2 + 2) + '╝')

def draw_piece(term, piece, offset=(0, 0), is_ghost=False):
    """Draws a single piece on the screen at a given offset."""
    char = GHOST_CHAR if is_ghost else BLOCK_CHAR
    color_func = get_color(term, piece.color)
    # Iterate through the piece's block coordinates.
    for x, y in piece.get_block_locations():
        # Only draw blocks that are within the visible area of the board (y >= 0).
        if y >= 0:
            # Calculate the screen position and draw the colored block character.
            # x is multiplied by 2 because each block character is 2 characters wide.
            print(term.move_xy((x * 2) + offset[0], y + offset[1]) + color_func(char))

def draw_ui(term, game):
    """Draws all the UI elements like score, level, next piece, etc."""
    # Title
    print(term.move_xy(0, 0) + term.bold_underline("avery's tetris"))

    # A helper function to draw a titled box.
    def draw_box(x, y, w, h, title, content):
        print(term.move_xy(x, y) + f"╔{'═'*(w-2)}╗")
        print(term.move_xy(x, y + 1) + f"║ {title:<{w-3}}║")
        # Draw empty middle part of the box
        for i in range(2, h - 1):
             print(term.move_xy(x, y + i) + f"║{' '*(w-2)}║")
        print(term.move_xy(x, y + h -1) + f"╚{'═'*(w-2)}╝")
        # Print the content inside the box
        print(term.move_xy(x + 2, y + 2) + str(content))

    # Draw the main UI info boxes.
    draw_box(0, 2, 20, 4, "SCORE", f"{game.score}")
    draw_box(0, 7, 20, 4, "LEVEL", f"{game.level}")
    draw_box(0, 12, 20, 4, "LINES CLEARED", f"{game.lines_cleared}")
    if game.is_back_to_back:
        print(term.move_xy(2, 17) + term.yellow_bold("Back-to-Back!"))

    # Draw the "Next Piece" box.
    next_box_x, next_box_y = PLAYFIELD_X_OFFSET + BOARD_WIDTH * 2 + 5, PLAYFIELD_Y_OFFSET
    draw_box(next_box_x, next_box_y, 14, 7, "NEXT", "")
    # Create a copy of the next piece to draw it without affecting the original.
    next_piece_copy = Piece(game.next_piece.shape_name)
    next_piece_copy.x, next_piece_copy.y = 0, 0 # Reset position for drawing inside the box
    draw_piece(term, next_piece_copy, offset=(next_box_x + 3, next_box_y + 2))

    # Draw the "Hold Piece" box.
    hold_box_x, hold_box_y = next_box_x, next_box_y + 8
    draw_box(hold_box_x, hold_box_y, 14, 7, "HOLD (c)", "")
    if game.hold_piece:
        hold_piece_copy = Piece(game.hold_piece.shape_name)
        hold_piece_copy.x, hold_piece_copy.y = 0, 0
        draw_piece(term, hold_piece_copy, offset=(hold_box_x + 3, hold_box_y + 2))

    # Draw the controls help text.
    controls_y = hold_box_y + 8
    print(term.move_xy(hold_box_x, controls_y) + "Controls:")
    print(term.move_xy(hold_box_x, controls_y + 1) + "←/→ : Move")
    print(term.move_xy(hold_box_x, controls_y + 2) + "↑   : Rotate")
    print(term.move_xy(hold_box_x, controls_y + 3) + "↓   : Soft Drop")
    print(term.move_xy(hold_box_x, controls_y + 4) + "Space: Hard Drop")
    print(term.move_xy(hold_box_x, controls_y + 5) + "c   : Hold")
    print(term.move_xy(hold_box_x, controls_y + 6) + "p   : Pause")
    print(term.move_xy(hold_box_x, controls_y + 7) + "q   : Quit")

def draw_game_state(term, game):
    """The main drawing function that clears the screen and redraws everything."""
    # `term.home` moves the cursor to (0,0). `term.clear_eos` clears from the cursor to the end of the screen.
    print(term.home + term.clear_eos, end='') # Use end='' to prevent extra newline
    draw_board_border(term)
    draw_ui(term, game)

    # Draw all the locked blocks on the board.
    for y, row in enumerate(game.board):
        for x, cell in enumerate(row):
            if cell != 0: # If the cell is not empty
                # Get the color for the shape name stored in the cell and draw the block.
                color = get_color(term, PIECE_COLORS[cell])
                print(term.move_xy(x * 2 + PLAYFIELD_X_OFFSET, y + PLAYFIELD_Y_OFFSET) + color(BLOCK_CHAR))

    # Draw ghost piece first so the current piece draws over it.
    ghost_y = game.get_ghost_piece_y()
    if ghost_y > game.current_piece.y:
        ghost_piece = Piece(game.current_piece.shape_name)
        ghost_piece.x, ghost_piece.y, ghost_piece.rotation = game.current_piece.x, ghost_y, game.current_piece.rotation
        draw_piece(term, ghost_piece, offset=(PLAYFIELD_X_OFFSET, PLAYFIELD_Y_OFFSET), is_ghost=True)

    # Draw the current, active piece.
    draw_piece(term, game.current_piece, offset=(PLAYFIELD_X_OFFSET, PLAYFIELD_Y_OFFSET))

    # If the game is paused, display a "PAUSED" message in the center of the board.
    if game.paused:
        msg = "PAUSED"
        print(term.move_xy(PLAYFIELD_X_OFFSET + BOARD_WIDTH - len(msg)//2, PLAYFIELD_Y_OFFSET + BOARD_HEIGHT//2) + term.black_on_white(msg))

def handle_input(term: Terminal, game: Game) -> bool:
    """Handle keyboard input and return True if game should continue."""
    key = term.inkey(timeout=INPUT_TIMEOUT)
    if not key:
        return True

    if not game.paused:
        # Handle piece movement controls.
        if key.code == term.KEY_LEFT:
            game.move(-1)
        elif key.code == term.KEY_RIGHT:
            game.move(1)
        elif key.code == term.KEY_UP:
            game.rotate()
        elif key.code == term.KEY_DOWN:
            game.soft_drop()
        elif key == ' ':
            game.hard_drop()
        elif key.lower() == 'c':
            game.hold()

    # These controls work even when paused.
    if key.lower() == 'p':
        game.paused = not game.paused
    elif key.lower() == 'q':
        game.game_over = True
        return False

    return True

def apply_gravity(game: Game, last_gravity_time: float) -> float:
    """Apply gravity to the current piece and return updated gravity time."""
    if game.paused:
        return last_gravity_time

    current_time = time.time()
    # Gravity gets faster as the level increases.
    gravity_interval = max(MIN_GRAVITY_INTERVAL, INITIAL_GRAVITY_INTERVAL - (game.level - 1) * GRAVITY_LEVEL_MULTIPLIER)

    # If enough time has passed, move the piece down one step due to gravity.
    if current_time - last_gravity_time > gravity_interval:
        if not game._is_touching_ground():
            game.current_piece.y += 1
        return current_time

    return last_gravity_time

def game_loop(term: Terminal, game: Game) -> None:
    """Contains the main loop that runs the game, handling input, updates, and drawing."""
    last_gravity_time = time.time()
    last_render_time = time.time()

    while not game.game_over:
        # Handle input
        if not handle_input(term, game):
            break

        # Apply gravity and update game state
        last_gravity_time = apply_gravity(game, last_gravity_time)

        if not game.paused:
            # Run the main game logic update (handles locking).
            game.update()

        # Throttle rendering for better performance
        current_time = time.time()
        if (current_time - last_render_time) * 1000 >= RENDER_THROTTLE_MS:
            draw_game_state(term, game)
            # It's crucial to flush stdout to ensure the terminal draws updates immediately.
            print(end='', flush=True)
            last_render_time = current_time


def handle_game_over(term, game):
    """Displays the game over screen, handles high score entry, and asks to play again."""
    high_scores = load_high_scores()
    # Check if the player's score is high enough to make the list.
    is_high_score = len(high_scores) < MAX_SCORES or (len(high_scores) > 0 and game.score > high_scores[-1][0])
    player_name = ""

    # If it's a new high score, enter the name input loop.
    if is_high_score and game.score > 0:
        while True:
            # Redraw the high score entry screen on each key press.
            print(term.home + term.clear)
            print(term.center(term.bold("🎉 NEW HIGH SCORE! 🎉")))
            print(term.center(f"Your Score: {game.score}"))
            print(term.center("Enter your name (3 chars):"))
            # Display the name being typed. `ljust` pads with underscores.
            input_box = f" {player_name.ljust(3, '_')} "
            print(term.center(term.reverse(input_box))) # `term.reverse` gives it a background color.

            key = term.inkey() # Wait for a key press.
            if key.code == term.KEY_ENTER and len(player_name) > 0: break
            elif key.code == term.KEY_BACKSPACE: player_name = player_name[:-1]
            # Add character to name if it's a letter/number and there's space.
            elif len(player_name) < 3 and not key.is_sequence and key.isalnum(): player_name += key.upper()
        # Add the new score and save the list.
        high_scores.append((game.score, player_name))
        save_high_scores(high_scores)

    # Loop for the final "Game Over" screen.
    while True:
        print(term.home + term.clear)
        print(term.move_y(term.height // 2 - 8) + term.center(term.bold("GAME OVER")))
        print(term.center(f"Final Score: {game.score}"))
        _display_high_scores_list(term, term.height // 2 - 4)
        print(term.move_y(term.height - 3) + term.center("Press 'r' to Restart or 'q' to Quit"))
        key = term.inkey()
        if key.lower() == 'r': return True  # Signal to restart
        elif key.lower() == 'q': return False # Signal to quit

def show_main_menu(term):
    """Displays the main menu with level select and high scores."""
    selected_level = 1
    while True:
        print(term.home + term.clear)
        title = "avery's tetris"
        print(term.move_y(term.height // 2 - 12) + term.center(term.bold(title)))

        # Display high scores and get how many lines it took up.
        scores_height = _display_high_scores_list(term, term.height // 2 - 9)
        controls_y = term.height // 2 - 9 + scores_height + 1

        # Display the level selector.
        print(term.move_y(controls_y) + term.center(term.bold("--- Level Select ---")))
        level_text = f"< Level {selected_level} >"
        print(term.center(level_text))
        print(term.center("(Use ←/→ to change)"))

        prompt_y = term.height - 4
        print(term.move_y(prompt_y) + term.center("Press SPACE to Play"))
        print(term.move_y(prompt_y + 1) + term.center("Press 'q' to Quit"))

        key = term.inkey()
        if key == ' ':
            return selected_level # Start game at this level
        elif key.lower() == 'q':
            return None # Quit the program
        elif key.code == term.KEY_LEFT:
            selected_level = max(1, selected_level - 1)
        elif key.code == term.KEY_RIGHT:
            selected_level = min(15, selected_level + 1)

def main():
    """The main function that sets up the terminal and runs the application."""
    term = Terminal()
    # `blessed` context manager handles setting up and tearing down the special terminal modes.
    # `fullscreen`: uses the whole terminal window.
    # `cbreak`: keys are read immediately without needing Enter.
    # `hidden_cursor`: hides the blinking cursor.
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            # The main application loop.
            while True:
                start_level = show_main_menu(term)
                if start_level is None: # User chose to quit from the menu
                    break

                game = Game(start_level=start_level)
                game_loop(term, game)

                # After the game loop ends, handle the game over screen.
                # If handle_game_over returns False, the user wants to quit.
                if not handle_game_over(term, game):
                    break
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            pass

# This is the standard entry point for a Python script.
# The code inside this block will only run when the script is executed directly.
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # This allows the user to exit cleanly with Ctrl+C without seeing an error.
        pass
    except Exception as e:
        # If any other unexpected error occurs, this will catch it.
        # The `blessed` context manager will automatically clean up the terminal state.
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc() # Print the full error details for debugging.
        input("Press Enter to exit...")
