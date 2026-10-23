"""
Input handling: key normalization, keybinding matching.
"""

from typing import Any

from blessed import Terminal

try:  # blessed depends on wcwidth, so this is only a safety net
    from wcwidth import wcwidth
except ImportError:  # pragma: no cover

    def wcwidth(ch: str) -> int:
        return 1


from .constants import RESERVED_KEYS
from .settings import KEY_SETTINGS, SETTINGS, SPEC_BY_KEY


def key_name(key) -> str:
    """Normalises a blessed Keystroke: special keys give their name ('KEY_UP', 'KEY_ENTER',
    ...), everything else gives the character itself. Never returns None."""
    if key.is_sequence:
        return key.name or ""
    return str(key)


def is_enter(name: str) -> bool:
    return name in ("KEY_ENTER", "\n", "\r")


def key_matches(pressed: str, bound: str) -> bool:
    """Single letters match regardless of Caps Lock; special keys must match exactly."""
    if pressed == bound:
        return True
    return len(pressed) == 1 and len(bound) == 1 and pressed.lower() == bound.lower()


def get_key_display_name(key_str: str) -> str:
    if key_str == " ":
        return "Space"
    return str(key_str).replace("KEY_", "").replace("_", " ").title()


def text_width(text: str) -> int:
    """Number of terminal columns `text` occupies (emoji take two)."""
    return sum(max(wcwidth(ch), 0) for ch in text)


def handle_input(term: Terminal, game: "Game") -> None:
    from .models import Game  # avoid circular import

    key_event = term.inkey(timeout=SETTINGS["INPUT_TIMEOUT"])
    if not key_event:
        return
    key = key_name(key_event)

    if game.paused and key.lower() == "s" and game.gamemode == "standard":
        from .database import save_game_state

        save_game_state(game)
        game.quit_after_save = True
        game.game_over = True
        return

    if not game.paused:
        actions = (
            ("Key: Left", lambda: game.move(-1)),
            ("Key: Right", lambda: game.move(1)),
            ("Key: Rotate", game.rotate),
            ("Key: Soft Drop", game.soft_drop),
            ("Key: Hard Drop", game.hard_drop),
            ("Key: Hold", game.hold),
        )
        for setting, action in actions:
            if key_matches(key, SETTINGS[setting]):
                action()
                break

    if key.lower() == "p":
        game.toggle_pause()
    elif key.lower() == "q":
        game.game_over = True