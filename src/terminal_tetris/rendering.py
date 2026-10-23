"""
Terminal helpers: Styles, Screen (flicker-free renderer), GameLayout, drawing functions.
"""

import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from blessed import Terminal

try:  # blessed depends on wcwidth, so this is only a safety net
    from wcwidth import wcwidth
except ImportError:  # pragma: no cover

    def wcwidth(ch: str) -> int:
        return 1


from .constants import (
    BLOCK_CHAR,
    GHOST_CHAR,
    PIECE_COLORS,
    SPRINT_TARGET_LINES,
)
from .settings import SETTINGS
from .models import Game, Piece


def text_width(text: str) -> int:
    """Number of terminal columns `text` occupies (emoji take two)."""
    return sum(max(wcwidth(ch), 0) for ch in text)


class Styles:
    """Escape sequences looked up once, so building a frame is just string handling."""

    def __init__(self, term: Terminal):
        self.bold = str(term.bold)
        self.reverse = str(term.reverse)
        self.title = str(term.bold_underline)
        self.underline = str(term.underline)
        self.alert = str(term.black_on_red)
        self.prompt = str(term.black_on_yellow)
        self.ok = str(term.black_on_green)
        self.paused = str(term.black_on_white)
        self.flash_block = str(term.white_on_white)
        self.flash_text = str(term.cyan_bold)
        white = str(term.white)
        # Terminals without 256 colours give '' for 'orange' - fall back to white.
        self.piece = {
            name: (str(getattr(term, name)) or white)
            for name in set(PIECE_COLORS.values())
        }


class Screen:
    _BLANK = (" ", "")

    def __init__(self, term: Terminal):
        self.term = term
        self.width = 0
        self.height = 0
        self._size = None
        self._front: Optional[Dict[Tuple[int, int], Tuple[str, str]]] = (
            None  # None = must clear first
        )
        self._back: Dict[Tuple[int, int], Tuple[str, str]] = {}

    def begin(self) -> None:
        """Starts a new frame. A changed window size forces one full repaint."""
        size = (self.term.width, self.term.height)
        if size != self._size:
            self._size = size
            self.invalidate()
        self.width, self.height = size
        self._back = {}

    def invalidate(self) -> None:
        """Forget what is on screen; the next flush clears and repaints everything."""
        self._front = None

    def put(self, x: int, y: int, text: str, style: str = "") -> None:
        if not 0 <= y < self.height:
            return
        for ch in text:
            w = wcwidth(ch)
            if w <= 0:
                continue
            if 0 <= x and x + w <= self.width:
                self._back[(x, y)] = (ch, style)
                if w == 2:
                    self._back[(x + 1, y)] = (
                        "",
                        style,
                    )  # right half of a wide character
            x += w

    def center(self, y: int, text: str, style: str = "") -> None:
        self.put(max(0, (self.width - text_width(text)) // 2), y, text, style)

    def box(
        self, x: int, y: int, w: int, h: int, title: str = "", content: Any = ""
    ) -> None:
        """A double-line box with a title row and optional first line of content."""
        inner = w - 2
        self.put(x, y, f"╔{'═' * inner}╗")
        self.put(x, y + 1, f"║ {title.ljust(inner - 1)}║")
        for i in range(2, h - 1):
            self.put(x, y + i, f"║{' ' * inner}║")
        self.put(x, y + h - 1, f"╚{'═' * inner}╝")
        if content != "":
            self.put(x + 2, y + 2, str(content))

    def flush(self) -> None:
        term, back = self.term, self._back
        out: List[str] = []
        if self._front is None:
            out.append(term.normal + term.home + term.clear)
            self._front = {}
        front = self._front

        cursor = None  # where the terminal's cursor is after the last write
        active_style = ""
        for pos in sorted(set(front) | set(back), key=lambda p: (p[1], p[0])):
            cell = back.get(pos, self._BLANK)
            if front.get(pos, self._BLANK) == cell:
                continue
            ch, style = cell
            if ch == "":  # covered by the wide character written just before it
                continue
            if cursor != pos:
                out.append(term.move_xy(*pos))
            if style != active_style:
                out.append(term.normal + style)
                active_style = style
            out.append(ch)
            cursor = (pos[0] + max(wcwidth(ch), 1), pos[1])
        if active_style:
            out.append(term.normal)

        self._front = back
        if out:
            sys.stdout.write("".join(out))
            sys.stdout.flush()


@dataclass(frozen=True)
class GameLayout:
    """Where everything goes. Worked out from the window width each frame, and never
    stored in SETTINGS (the old code overwrote a saved setting every frame)."""

    px: int  # screen column of the playfield's first cell
    py: int  # screen row of the playfield's first row
    left_x: int  # column of the SCORE / LEVEL / LINES boxes
    next_x: int  # column of the NEXT and HOLD boxes
    hold_y: int
    controls_x: int
    controls_y: int
    controls_w: int

    @classmethod
    def create(cls, term_width: int, game: Game) -> "GameLayout":
        px = term_width // 2 - game.width
        py = SETTINGS["PLAYFIELD_Y_OFFSET"]
        return cls(
            px=px,
            py=py,
            left_x=px - 15,
            next_x=px + game.width * 2 + 3,
            hold_y=py + 23,
            controls_x=px - 7,
            controls_y=py + game.height + 1,
            controls_w=game.width * 2 + 9,
        )

    @staticmethod
    def minimum_size(game: Game) -> Tuple[int, int]:
        """Smallest (columns, rows) the whole screen fits in."""
        py = SETTINGS["PLAYFIELD_Y_OFFSET"]
        return 2 * (game.width + 15), max(py + game.height + 1 + 10, py + 23 + 7)


def stat_boxes(game: Game) -> List[Tuple[str, Any]]:
    """The three boxes on the left, which depend on the game mode."""
    from .settings import format_time

    if game.gamemode == "sprint":
        return [
            ("TIME", format_time(game.elapsed_time)),
            ("LEVEL", game.level),
            (
                "LINES",
                f"{min(game.lines_cleared, SPRINT_TARGET_LINES)}/{SPRINT_TARGET_LINES}",
            ),
        ]
    if game.gamemode == "timed":
        time_left = max(0, SETTINGS["TIMED_MODE_DURATION_S"] - game.elapsed_time)
        return [
            ("TIME LEFT", format_time(time_left)),
            ("SCORE", game.score),
            ("LINES", game.lines_cleared),
        ]
    if game.gamemode == "garbage":
        return [
            ("TIME", format_time(game.elapsed_time)),
            ("SCORE", game.score),
            ("LINES", game.lines_cleared),
        ]
    return [("SCORE", game.score), ("LEVEL", game.level), ("LINES", game.lines_cleared)]


def draw_piece(
    screen: Screen,
    styles: Styles,
    piece: Piece,
    offset_x: int,
    offset_y: int,
    ghost: bool = False,
) -> None:
    char = GHOST_CHAR if ghost else BLOCK_CHAR
    style = styles.piece[piece.color]
    for px, py in piece.get_block_locations():
        if py >= 0:
            screen.put(px * 2 + offset_x, py + offset_y, char, style)


def draw_preview(
    screen: Screen, styles: Styles, shape_name: str, width: int, x: int, y: int
) -> None:
    preview = Piece(shape_name, width)
    preview.x = preview.y = 0
    draw_piece(screen, styles, preview, x, y)


def draw_game(screen: Screen, styles: Styles, game: Game, layout: GameLayout) -> None:
    px, py = layout.px, layout.py
    screen.put(px, 0, "Terminal Tetris", styles.title)

    # Playfield border
    bx, by, bw = px - 2, py - 1, game.width * 2 + 2
    screen.put(bx, by, "╔" + "═" * bw + "╗")
    for i in range(game.height):
        screen.put(bx, by + 1 + i, "║")
        screen.put(bx + bw + 1, by + 1 + i, "║")
    screen.put(bx, by + game.height + 1, "╚" + "═" * bw + "╝")

    # Left-hand stat boxes
    for i, (title, content) in enumerate(stat_boxes(game)):
        screen.box(layout.left_x, py + i * 5, 12, 4, title, content)

    # NEXT and HOLD
    screen.box(layout.next_x, py, 10, 22, "NEXT")
    for i, shape_name in enumerate(list(game.upcoming_pieces)[:4]):
        draw_preview(
            screen, styles, shape_name, game.width, layout.next_x, py + 1 + i * 5
        )
    screen.box(layout.next_x, layout.hold_y, 10, 7, "HOLD")
    if game.hold_piece:
        draw_preview(
            screen,
            styles,
            game.hold_piece.shape_name,
            game.width,
            layout.next_x,
            layout.hold_y + 1,
        )

    # Controls
    from .input import get_key_display_name

    screen.box(layout.controls_x, layout.controls_y, layout.controls_w, 10, "CONTROLS")
    controls = [
        (
            "Move",
            f"{get_key_display_name(SETTINGS['Key: Left'])}/{get_key_display_name(SETTINGS['Key: Right'])}",
        ),
        ("Rotate", get_key_display_name(SETTINGS["Key: Rotate"])),
        ("Soft Drop", get_key_display_name(SETTINGS["Key: Soft Drop"])),
        ("Hard Drop", get_key_display_name(SETTINGS["Key: Hard Drop"])),
        ("Hold", get_key_display_name(SETTINGS["Key: Hold"])),
        ("Pause/Quit", "P / Q"),
        ("Save", "S (Paused)"),
    ]
    for i, (label, key) in enumerate(controls):
        line = f"{label:<10}: {key}"
        screen.put(
            layout.controls_x + 2,
            layout.controls_y + 2 + i,
            line[: layout.controls_w - 4],
        )

    # Settled blocks
    for y, row in enumerate(game.board):
        for x, cell in enumerate(row):
            if cell != 0:
                screen.put(
                    x * 2 + px,
                    y + py,
                    BLOCK_CHAR,
                    styles.piece[PIECE_COLORS.get(cell, "white")],
                )

    # Line-clear flash (expiry is handled in Game.update, not here)
    for y in game.lines_to_flash:
        screen.put(px, y + py, BLOCK_CHAR * game.width, styles.flash_block)
    if game.flash_text:
        screen.put(layout.left_x + 2, py + 15, game.flash_text, styles.flash_text)

    # Ghost, then the active piece on top
    if SETTINGS.get("GHOST_PIECE_ENABLED") == 1:
        ghost = game.ghost_piece()
        if ghost.y > game.current_piece.y:
            draw_piece(screen, styles, ghost, px, py, ghost=True)
    draw_piece(screen, styles, game.current_piece, px, py)

    if game.paused:
        msg = "PAUSED"
        screen.put(
            px + game.width - len(msg) // 2, py + game.height // 2, msg, styles.paused
        )


def draw_too_small(screen: Screen, styles: Styles, need_w: int, need_h: int) -> None:
    lines = [
        "Terminal too small",
        f"Needs at least {need_w} x {need_h}",
        f"Currently {screen.width} x {screen.height}",
        "Enlarge the window (the game is paused)",
    ]
    top = max(0, screen.height // 2 - len(lines) // 2)
    for i, line in enumerate(lines):
        screen.center(top + i, line, styles.bold if i == 0 else "")


def render_game(
    screen: Screen, styles: Styles, game: Game, message: Optional[str] = None
) -> bool:
    """Draws one frame. Returns False (and draws a notice) if the window is too small."""
    screen.begin()
    need_w, need_h = GameLayout.minimum_size(game)
    if screen.width < need_w or screen.height < need_h:
        draw_too_small(screen, styles, need_w, need_h)
        screen.flush()
        return False
    layout = GameLayout.create(screen.width, game)
    draw_game(screen, styles, game, layout)
    if message:
        screen.put(
            layout.px + game.width - len(message) // 2,
            layout.py + game.height // 2 + 2,
            message,
            styles.ok,
        )
    screen.flush()
    return True