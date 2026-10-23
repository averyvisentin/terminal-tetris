"""
Game model (Piece, Game, ScoreBoard) - no drawing, no input.
"""

import collections
import copy
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import (
    GARBAGE_BLOCK_TYPE,
    PIECE_COLORS,
    SCORING_MODES,
    SHAPES,
    SPRINT_TARGET_LINES,
)
from .settings import SETTINGS, format_time


class Piece:
    def __init__(self, shape_name: str, board_width: int):
        self.shape_name: str = shape_name
        self.shape_matrices: List[List[str]] = SHAPES[shape_name]
        self.color: str = PIECE_COLORS[shape_name]
        self.rotation: int = 0
        self.x: int = board_width // 2 - 2
        self.y: int = -2

    def copy(self) -> "Piece":
        return copy.copy(self)  # shape matrices are shared and never modified

    def get_current_shape_matrix(self) -> List[str]:
        return self.shape_matrices[self.rotation]

    def get_block_locations(self) -> List[Tuple[int, int]]:
        positions = []
        for r, row_str in enumerate(self.get_current_shape_matrix()):
            for c, char in enumerate(row_str):
                if char == "O":
                    positions.append((self.x + c, self.y + r))
        return positions


@dataclass(frozen=True)
class ScoreBoard:
    """Everything that differs between the four game modes' high-score tables."""

    mode: str
    table: str
    title: str  # heading of the list
    value_cols: Tuple[str, ...]  # stored columns (the name column always follows)
    order_by: str  # SQL ordering, best first
    rank: Callable[[tuple], tuple]  # bigger = better; mirrors order_by
    fmt: Callable[[tuple], str]  # how a row's values are shown in a list
    qualifies: Callable[["Game"], bool]  # can this game be a record at all?
    row_from_game: Callable[
        ["Game"], tuple
    ]  # values to store (same order as value_cols)
    banner: str  # "new record" banner
    heading: Callable[["Game"], str]  # result-screen heading
    summary: Callable[["Game"], List[str]]  # result-screen lines under the heading
    record_line: Callable[["Game"], str]  # line shown while entering a name


SCOREBOARDS: Dict[str, ScoreBoard] = {
    "standard": ScoreBoard(
        mode="standard",
        table="highscores",
        title="Top Marathon Scores",
        value_cols=("score", "time", "lines"),
        order_by="score DESC",
        rank=lambda v: (v[0],),
        fmt=lambda v: str(v[0]),
        qualifies=lambda g: g.score > 0,
        row_from_game=lambda g: (g.score, g.elapsed_time, g.lines_cleared),
        banner="🎉 NEW HIGH SCORE! 🎉",
        heading=lambda g: "GAME OVER",
        summary=lambda g: [f"Final Score: {g.score}"],
        record_line=lambda g: f"Your Score: {g.score}",
    ),
    "sprint": ScoreBoard(
        mode="sprint",
        table="sprint_highscores",
        title="Top Sprint Times",
        value_cols=("time",),
        order_by="time ASC",
        rank=lambda v: (-v[0],),
        fmt=lambda v: format_time(v[0]),
        qualifies=lambda g: g.lines_cleared >= SPRINT_TARGET_LINES,
        row_from_game=lambda g: (g.elapsed_time,),
        banner="🎉 NEW SPRINT RECORD! 🎉",
        heading=lambda g: (
            f"{SPRINT_TARGET_LINES} LINES CLEARED!"
            if g.lines_cleared >= SPRINT_TARGET_LINES
            else "GAME OVER"
        ),
        summary=lambda g: [f"Final Time: {format_time(g.elapsed_time)}"],
        record_line=lambda g: f"Your Time: {format_time(g.elapsed_time)}",
    ),
    "timed": ScoreBoard(
        mode="timed",
        table="timed_highscores",
        title="Top Timed Scores",
        value_cols=("score", "lines"),
        order_by="score DESC, lines DESC",
        rank=lambda v: (v[0], v[1]),
        fmt=lambda v: f"{v[0]} ({v[1]}L)",
        qualifies=lambda g: g.score > 0,
        row_from_game=lambda g: (g.score, g.lines_cleared),
        banner="🎉 NEW TIMED HIGH SCORE! 🎉",
        heading=lambda g: "TIME'S UP!",
        summary=lambda g: [
            f"Final Score: {g.score}",
            f"Lines Cleared: {g.lines_cleared}",
        ],
        record_line=lambda g: f"Your Score: {g.score} in {g.lines_cleared} lines",
    ),
    "garbage": ScoreBoard(
        mode="garbage",
        table="garbage_highscores",
        title="Top Garbage Times",
        value_cols=("time",),
        order_by="time DESC",
        rank=lambda v: (v[0],),
        fmt=lambda v: format_time(v[0]),
        qualifies=lambda g: g.elapsed_time > 0,
        row_from_game=lambda g: (g.elapsed_time,),
        banner="🎉 NEW GARBAGE RECORD! 🎉",
        heading=lambda g: "GAME OVER",
        summary=lambda g: [f"Final Time: {format_time(g.elapsed_time)}"],
        record_line=lambda g: f"You Survived For: {format_time(g.elapsed_time)}",
    ),
}
BOARD_ORDER = ("standard", "sprint", "timed", "garbage")


class Game:
    def __init__(
        self,
        gamemode: str = "standard",
        start_level: int = 1,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        # The board size is fixed for the life of a game, so changing settings
        # (or resuming an old save) can never put the game out of step with its board.
        self.width: int = width or SETTINGS["BOARD_WIDTH"]
        self.height: int = height or SETTINGS["BOARD_HEIGHT"]
        self.board: List[List[Any]] = [[0] * self.width for _ in range(self.height)]
        self.gamemode: str = gamemode

        self.score: int = 0
        self.lines_cleared: int = 0
        self.level: int = start_level
        self.start_level: int = start_level
        self.game_over: bool = False
        self.paused: bool = False
        self.quit_after_save: bool = False

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
        self.lines_to_flash: List[int] = []
        self.flash_text: str = ""
        self.flash_start_time: float = 0

        now = time.time()
        self.start_time: float = now
        self.elapsed_time: float = 0
        self.last_garbage_time: float = now
        self.last_gravity_time: float = now
        self._paused_at: float = 0

    # --- pause -------------------------------------------------------------

    def set_paused(self, paused: bool):
        """Pauses or resumes. Every running timer is pushed back by the time spent paused,
        so pausing never costs time in Sprint / Timed / Garbage or moves the piece."""
        if paused == self.paused:
            return
        now = time.time()
        if paused:
            self._paused_at = now
        else:
            shift = now - self._paused_at
            self.start_time += shift
            self.last_garbage_time += shift
            self.last_gravity_time += shift
            self.flash_start_time += shift
            if self.lock_delay_start_time:
                self.lock_delay_start_time += shift
        self.paused = paused

    def toggle_pause(self):
        self.set_paused(not self.paused)

    # --- piece supply ------------------------------------------------------

    def _refill_bag(self):
        self.bag = list(SHAPES.keys())
        random.shuffle(self.bag)

    def _add_to_upcoming(self):
        if not self.bag:
            self._refill_bag()
        self.upcoming_pieces.append(self.bag.pop())

    def _get_new_piece(self) -> Piece:
        shape_name = self.upcoming_pieces.popleft()
        self._add_to_upcoming()
        return Piece(shape_name, self.width)

    # --- board queries -----------------------------------------------------

    def _is_valid_position(self, piece: Piece, check_y_offset: int = 0) -> bool:
        for x, y in piece.get_block_locations():
            y += check_y_offset
            if not (0 <= x < self.width and y < self.height):
                return False
            if y >= 0 and self.board[y][x] != 0:
                return False
        return True

    def _is_touching_ground(self) -> bool:
        return not self._is_valid_position(self.current_piece, check_y_offset=1)

    def _is_blocked(self, x: int, y: int) -> bool:
        """True for a wall, the floor, the ceiling or a filled cell (used for T-spin corners)."""
        return not (0 <= x < self.width and 0 <= y < self.height) or (
            y >= 0 and self.board[y][x] != 0
        )

    def ghost_piece(self) -> Piece:
        """A copy of the current piece resting where a hard drop would put it."""
        ghost = self.current_piece.copy()
        while self._is_valid_position(ghost, 1):
            ghost.y += 1
        return ghost

    # --- locking & scoring -------------------------------------------------

    def add_garbage_row(self):
        """Adds a row of garbage with one hole to the bottom of the board."""
        hole_position = random.randint(0, self.width - 1)
        new_row = [
            GARBAGE_BLOCK_TYPE if i != hole_position else 0 for i in range(self.width)
        ]
        self.board.pop(0)
        self.board.append(new_row)
        if not self._is_valid_position(self.current_piece):
            self.game_over = True

    def _lock_piece(self):
        piece = self.current_piece
        t_spin_type = (
            self._check_t_spin()
            if piece.shape_name == "T" and self.last_move_was_rotation
            else None
        )
        for x, y in piece.get_block_locations():
            if y >= 0:
                self.board[y][x] = piece.shape_name
        lines_cleared_this_turn = self._clear_lines(t_spin_type)
        if t_spin_type or lines_cleared_this_turn == 4:
            self.is_back_to_back = True
        elif lines_cleared_this_turn > 0:
            self.is_back_to_back = False
        self.can_hold = True
        self.lock_delay_start_time = 0
        self.last_move_was_rotation = False
        self.current_piece = self._get_new_piece()
        if not self._is_valid_position(self.current_piece):
            self.game_over = True

    def _check_t_spin(self):
        piece = self.current_piece
        center_x, center_y = piece.x + 2, piece.y + 1
        corners = [
            (center_x - 1, center_y - 1),
            (center_x + 1, center_y - 1),
            (center_x - 1, center_y + 1),
            (center_x + 1, center_y + 1),
        ]
        occupied_corners = sum(1 for x, y in corners if self._is_blocked(x, y))
        if occupied_corners >= 3:
            return "T_SPIN"
        if occupied_corners == 2:
            front_corners = [
                corners[i] for i in [[0, 1], [1, 3], [2, 3], [0, 2]][piece.rotation]
            ]
            if any(self._is_blocked(x, y) for x, y in front_corners):
                return "T_SPIN_MINI"
        return None

    def _clear_lines(self, t_spin_type=None) -> int:
        lines_to_clear_indices = [
            i for i, row in enumerate(self.board) if all(cell != 0 for cell in row)
        ]
        if not lines_to_clear_indices and not t_spin_type:
            return 0

        self.lines_to_flash = lines_to_clear_indices
        self.flash_start_time = time.time()
        new_board = [row for row in self.board if any(cell == 0 for cell in row)]
        lines_cleared_count = len(self.board) - len(new_board)

        if lines_cleared_count > 0:
            for _ in range(lines_cleared_count):
                new_board.insert(0, [0] * self.width)
            self.board = new_board

        if self.gamemode in SCORING_MODES:
            score_key_map = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}
            t_spin_key_map = {
                1: "T_SPIN_SINGLE",
                2: "T_SPIN_DOUBLE",
                3: "T_SPIN_TRIPLE",
            }
            score_key = (
                t_spin_key_map.get(lines_cleared_count, t_spin_type)
                if t_spin_type
                else score_key_map.get(lines_cleared_count)
            )

            if score_key:
                self.flash_text = score_key.replace("_", " ")
                base_score = SETTINGS["SCORE_VALUES"].get(score_key, 0)
                is_difficult = "TETRIS" in score_key or "T_SPIN" in score_key
                if is_difficult and self.is_back_to_back:
                    base_score *= SETTINGS["SCORE_VALUES"]["BACK_TO_BACK_MULTIPLIER"]
                self.score += int(base_score * self.level)

        self.lines_cleared += lines_cleared_count
        self.level = self.start_level + (self.lines_cleared // 10)

        if self.gamemode == "sprint" and self.lines_cleared >= SPRINT_TARGET_LINES:
            self.elapsed_time = time.time() - self.start_time
            self.game_over = True

        return lines_cleared_count

    # --- player actions ----------------------------------------------------

    def move(self, dx: int):
        self.current_piece.x += dx
        if not self._is_valid_position(self.current_piece):
            self.current_piece.x -= dx
        else:
            self.last_move_was_rotation = False
            self.reset_lock_delay()

    def rotate(self):
        piece = self.current_piece
        original_rotation = piece.rotation
        piece.rotation = (piece.rotation + 1) % 4
        if self._is_valid_position(piece):
            self.last_move_was_rotation = True
            self.reset_lock_delay()
            return
        for kick_x in [-1, 1, -2, 2]:
            piece.x += kick_x
            if self._is_valid_position(piece):
                self.last_move_was_rotation = True
                self.reset_lock_delay()
                return
            piece.x -= kick_x
        piece.rotation = original_rotation

    def soft_drop(self):
        if not self._is_touching_ground():
            self.current_piece.y += 1
            if self.gamemode in SCORING_MODES:
                self.score += 1
            self.last_move_was_rotation = False
        else:
            self.initiate_lock_delay()

    def hard_drop(self):
        drop_distance = 0
        while not self._is_touching_ground():
            self.current_piece.y += 1
            drop_distance += 1
        if self.gamemode in SCORING_MODES:
            self.score += drop_distance * 2
        self._lock_piece()

    def hold(self):
        if not self.can_hold:
            return
        current = Piece(self.current_piece.shape_name, self.width)
        if self.hold_piece is None:
            self.hold_piece = current
            self.current_piece = self._get_new_piece()
        else:
            self.current_piece = Piece(self.hold_piece.shape_name, self.width)
            self.hold_piece = current
        self.can_hold = False
        self.last_move_was_rotation = False
        self.lock_delay_start_time = 0

    # --- lock delay --------------------------------------------------------

    def initiate_lock_delay(self):
        if self.lock_delay_start_time == 0:
            self.lock_delay_start_time = time.time()

    def reset_lock_delay(self):
        self.lock_delay_start_time = 0
        if self._is_touching_ground():
            self.initiate_lock_delay()

    # --- time --------------------------------------------------------------

    def gravity_interval(self) -> float:
        return max(
            SETTINGS["MIN_GRAVITY_INTERVAL"],
            SETTINGS["INITIAL_GRAVITY_INTERVAL"]
            - (self.level - 1) * SETTINGS["GRAVITY_LEVEL_MULTIPLIER"],
        )

    def update(self):
        """Advances everything that depends on time. Call once per loop iteration."""
        if self.paused or self.game_over:
            return

        now = time.time()
        self.elapsed_time = now - self.start_time

        if (
            self.gamemode == "timed"
            and self.elapsed_time >= SETTINGS["TIMED_MODE_DURATION_S"]
        ):
            self.game_over = True
            return

        if (
            self.gamemode == "garbage"
            and now - self.last_garbage_time >= SETTINGS["GARBAGE_INTERVAL_S"]
        ):
            self.add_garbage_row()
            self.last_garbage_time = now

        if now - self.last_gravity_time > self.gravity_interval():
            if not self._is_touching_ground():
                self.current_piece.y += 1
                self.last_move_was_rotation = False
            self.last_gravity_time = now

        if (
            self.lines_to_flash or self.flash_text
        ) and now - self.flash_start_time >= SETTINGS["FLASH_DURATION"]:
            self.lines_to_flash = []
            self.flash_text = ""

        if self._is_touching_ground():
            self.initiate_lock_delay()
            if (
                self.lock_delay_start_time
                and now - self.lock_delay_start_time >= SETTINGS["Lock Delay (s)"]
            ):
                self._lock_piece()
        else:
            self.reset_lock_delay()