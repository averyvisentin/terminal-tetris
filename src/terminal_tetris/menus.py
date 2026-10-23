"""
Menus: game over, main menu, settings, score editor.
"""

import copy
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from blessed import Terminal

from .constants import (
    BOARD_ORDER,
    MODE_OPTIONS,
    QUOTES_FILE,
)
from .database import (
    add_high_score,
    has_save_state,
    is_new_record,
    load_high_scores,
    load_settings,
    save_settings,
)
from .input import is_enter, key_name
from .models import SCOREBOARDS, Game, ScoreBoard
from .rendering import Screen, Styles
from .settings import (
    KEY_SETTINGS,
    RESERVED_KEYS,
    SETTING_SPECS,
    SETTINGS,
    SPEC_BY_KEY,
    SettingSpec,
    adjust_setting,
    coerce_setting,
    enforce_constraints,
    format_setting_value,
    format_time,
    sanitize_settings,
    settings_rows,
    validate_key_binding,
)

# --- game over --------------------------------------------------------------


def draw_high_scores(
    screen: Screen, styles: Styles, y: int, board: ScoreBoard, scores: List[Tuple]
) -> int:
    """Draws a titled, centred list. Returns how many rows it used."""
    screen.center(y, board.title, styles.underline)
    if not scores:
        screen.center(y + 1, "No scores yet!")
        return 2
    for i, row in enumerate(scores):
        name, values = row[-1], row[:-1]
        screen.center(
            y + 1 + i,
            f"{i + 1}. {name:<{SETTINGS['MAX_NAME_LENGTH']}} - {board.fmt(values)}",
        )
    return len(scores) + 1


def prompt_for_name(
    term: Terminal, screen: Screen, styles: Styles, board: ScoreBoard, game: Game
) -> str:
    max_len = SETTINGS["MAX_NAME_LENGTH"]
    name = ""
    while True:
        screen.begin()
        top = max(0, screen.height // 2 - 3)
        screen.center(top, board.banner, styles.bold)
        screen.center(top + 1, board.record_line(game))
        screen.center(top + 2, f"Enter your name ({max_len} chars):")
        screen.center(top + 3, f" {name.ljust(max_len, '_')} ", styles.reverse)
        screen.flush()

        key = term.inkey(timeout=0.1)
        if not key:
            continue
        pressed = key_name(key)
        if is_enter(pressed) and name:
            return name
        if pressed == "KEY_BACKSPACE":
            name = name[:-1]
        elif not key.is_sequence and key.isalnum() and len(name) < max_len:
            name += str(key).upper()


def show_results(
    term: Terminal, screen: Screen, styles: Styles, board: ScoreBoard, game: Game
) -> bool:
    """Final screen. Returns True for the main menu, False to quit."""
    scores = load_high_scores(board)
    summary = board.summary(game)
    while True:
        screen.begin()
        top = max(0, screen.height // 2 - 8)
        screen.center(top, board.heading(game), styles.bold)
        for i, line in enumerate(summary):
            screen.center(top + 1 + i, line)
        draw_high_scores(screen, styles, top + len(summary) + 3, board, scores)
        screen.center(
            screen.height - 3, "Press SPACE or ENTER for Main Menu or 'q' to Quit"
        )
        screen.flush()

        key = term.inkey(timeout=0.1)
        if not key:
            continue
        pressed = key_name(key)
        if pressed == " " or is_enter(pressed):
            return True
        if pressed.lower() == "q":
            return False


def handle_game_over(
    term: Terminal, screen: Screen, styles: Styles, game: Game
) -> bool:
    """Name entry (if it's a record) and the results screen. True = main menu, False = quit."""
    board = SCOREBOARDS.get(game.gamemode, SCOREBOARDS["standard"])
    if is_new_record(board, game):
        name = prompt_for_name(term, screen, styles, board, game)
        add_high_score(board, board.row_from_game(game), name)
    return show_results(term, screen, styles, board, game)


# --- main menu --------------------------------------------------------------


def load_menu_quote() -> str:
    try:
        with open(QUOTES_FILE, "r") as f:
            quotes = [line.strip() for line in f if line.strip()]
    except OSError:
        return "menu_quotes.txt not found!"
    return random.choice(quotes) if quotes else ""


def show_main_menu(
    term: Terminal, screen: Screen, styles: Styles
) -> Tuple[Optional[str], Optional[int]]:
    """Returns (gamemode, start_level), ("RESUME", None) or (None, None) to quit."""
    quote = load_menu_quote()
    quote_visible, last_blink = True, time.time()
    selected = 0

    levels = {mode: SETTINGS["MIN_LEVEL"] for mode in MODE_OPTIONS.values()}
    levels["sprint"] = SETTINGS["SPRINT_DEFAULT_LEVEL"]

    def refresh():
        """Database reads happen here, once - never inside the draw loop."""
        scores = {mode: load_high_scores(SCOREBOARDS[mode]) for mode in BOARD_ORDER}
        options = (
            (["Resume"] if has_save_state() else [])
            + list(MODE_OPTIONS)
            + ["Settings", "Quit"]
        )
        return scores, options

    scores, options = refresh()

    while True:
        now = time.time()
        if now - last_blink > 1.0:
            quote_visible, last_blink = not quote_visible, now

        screen.begin()
        screen.center(1, "Terminal Tetris", styles.bold)
        if quote_visible:
            screen.center(3, quote)

        # High-score lists first, as many as fit; the menu follows them and the help sits at the bottom.
        top = 5
        room = (
            screen.height - top - (len(options) + 2) - 3
        )  # rows left once the menu block and help are reserved
        y = top
        for mode in BOARD_ORDER:
            rows_needed = 1 + max(1, len(scores[mode]))
            if (y - top) + rows_needed > room:
                break
            draw_high_scores(screen, styles, y, SCOREBOARDS[mode], scores[mode])
            y += rows_needed + 1
        menu_y = y

        for i, option in enumerate(options):
            screen.center(
                menu_y + i, f" {option} ", styles.reverse if i == selected else ""
            )
        current_mode = MODE_OPTIONS.get(options[selected])
        if current_mode:
            screen.center(
                menu_y + len(options) + 1, f"< Starting Level {levels[current_mode]} >"
            )

        help_lines = (
            "Use ↑/↓ to navigate.",
            "Use ←/→ to change values.",
            "Press SPACE or ENTER to Select. 'q' to Quit.",
        )
        for i, line in enumerate(help_lines):
            screen.center(screen.height - 3 + i, line)
        screen.flush()

        key = term.inkey(timeout=0.1)
        if not key:
            continue
        pressed = key_name(key)

        if pressed == "KEY_UP":
            selected = (selected - 1) % len(options)
        elif pressed == "KEY_DOWN":
            selected = (selected + 1) % len(options)
        elif pressed in ("KEY_LEFT", "KEY_RIGHT") and current_mode:
            step = -1 if pressed == "KEY_LEFT" else 1
            levels[current_mode] = min(
                SETTINGS["MAX_LEVEL"],
                max(SETTINGS["MIN_LEVEL"], levels[current_mode] + step),
            )
        elif is_enter(pressed) or pressed == " ":
            choice = options[selected]
            if choice == "Settings":
                show_settings(term, screen, styles)
                scores, options = refresh()
                selected = min(selected, len(options) - 1)
                for mode in levels:  # the level limits may have changed
                    levels[mode] = min(
                        SETTINGS["MAX_LEVEL"], max(SETTINGS["MIN_LEVEL"], levels[mode])
                    )
            elif choice == "Resume":
                return "RESUME", None
            elif choice == "Quit":
                return None, None
            else:
                mode = MODE_OPTIONS[choice]
                return mode, levels[mode]
        elif pressed.lower() == "q":
            return None, None


# --- settings ---------------------------------------------------------------


def format_setting_value(spec: SettingSpec, value: Any) -> str:
    if spec.kind == "toggle":
        return "Enabled" if value else "Disabled"
    if spec.kind == "dict":
        return "[Enter to edit]"
    if spec.kind == "float":
        return f"{value:.{spec.decimals}f}"
    if spec.kind == "key":
        from .input import get_key_display_name

        return get_key_display_name(value)
    return str(value)


def adjust_setting(spec: SettingSpec, value: Any, direction: int) -> Any:
    """One step left (-1) or right (+1), kept inside the setting's range."""
    if spec.kind == "toggle":
        return 1 - value
    if spec.kind in ("int", "float"):
        new_value = min(spec.high, max(spec.low, value + direction * spec.step))
        return int(round(new_value)) if spec.kind == "int" else round(new_value, 4)
    return value


def validate_key_binding(
    settings: dict, spec: SettingSpec, bound: str
) -> Optional[str]:
    """Returns why `bound` can't be used for `spec`, or None if it's fine."""
    if not bound:
        return "That key can't be used."
    if len(bound) == 1 and bound.lower() in RESERVED_KEYS:
        return f"'{bound.upper()}' is reserved for pause/quit."
    for other in KEY_SETTINGS:
        if other != spec.key and key_matches(bound, settings[other]):
            return f"Already used for '{SPEC_BY_KEY[other].label}'."
    return None


def settings_rows() -> List[Tuple[str, Any]]:
    """The menu as a flat list of ('header', title) and ('item', spec) rows."""
    rows: List[Tuple[str, Any]] = []
    section = None
    for spec in SETTING_SPECS:
        if spec.section != section:
            section = spec.section
            rows.append(("header", section))
        rows.append(("item", spec))
    return rows


def show_settings(term: Terminal, screen: Screen, styles: Styles) -> None:
    """Scrollable settings editor. Edits a copy; 's' saves it, 'q' throws it away."""
    working = copy.deepcopy(SETTINGS)
    rows = settings_rows()
    selectable = [i for i, (kind, _) in enumerate(rows) if kind == "item"]
    cursor, top = 0, 0
    mode = "browse"  # 'browse' | 'rebind' | 'confirm_reset'
    status, status_style = "", ""

    while True:
        selected_row = selectable[cursor]
        spec: SettingSpec = rows[selected_row][1]

        screen.begin()
        w, h = screen.width, screen.height
        list_top = 3
        visible = max(1, h - list_top - 5)

        # Scroll so the selected row (and the heading above it) stays on screen.
        first_wanted = (
            selected_row - 1 if rows[selected_row - 1][0] == "header" else selected_row
        )
        if first_wanted < top:
            top = first_wanted
        if selected_row >= top + visible:
            top = selected_row - visible + 1
        top = max(0, min(top, len(rows) - visible))

        screen.center(1, "--- Game Settings ---", styles.bold)
        inner_w = max(10, w - 4)
        for offset in range(min(visible, len(rows) - top)):
            idx = top + offset
            kind, payload = rows[idx]
            y = list_top + offset
            if kind == "header":
                screen.put(2, y, f"[ {payload} ]", styles.bold)
                continue
            if mode == "rebind" and idx == selected_row:
                value_text = "press a key..."
            else:
                value_text = format_setting_value(payload, working[payload.key])
            gap = max(1, inner_w - 2 - len(payload.label) - len(value_text))
            line = f"  {payload.label}{'.' * gap}{value_text}"[:inner_w].ljust(inner_w)
            screen.put(2, y, line, styles.reverse if idx == selected_row else "")
        if top > 0:
            screen.put(w - 2, list_top, "▲")
        if top + visible < len(rows):
            screen.put(w - 2, list_top + visible - 1, "▼")

        if mode == "rebind":
            screen.center(
                h - 4,
                f" Press the new key for '{spec.label}'  (Esc cancels) ",
                styles.prompt,
            )
        elif mode == "confirm_reset":
            screen.center(
                h - 4, " Restore ALL settings to defaults?  (y/n) ", styles.alert
            )
        elif status:
            screen.center(h - 4, f" {status} ", status_style)
        screen.center(h - 3, "↑/↓ select    ←/→ change    ENTER edit / rebind")
        screen.center(h - 2, "S save & exit    Q discard & exit    R restore defaults")
        screen.flush()

        key = term.inkey(timeout=0.1)
        if not key:
            continue
        pressed = key_name(key)

        if mode == "rebind":
            mode = "browse"
            if pressed != "KEY_ESCAPE":
                bound = pressed.lower() if len(pressed) == 1 else pressed
                error = validate_key_binding(working, spec, bound)
                if error:
                    status, status_style = error, styles.alert
                else:
                    working[spec.key], status = bound, ""
            continue

        if mode == "confirm_reset":
            mode = "browse"
            if pressed.lower() == "y":
                working = sanitize_settings({})
                status, status_style = (
                    "Defaults restored - press S to keep them",
                    styles.ok,
                )
            continue

        status = ""
        if pressed == "KEY_UP":
            cursor = (cursor - 1) % len(selectable)
        elif pressed == "KEY_DOWN":
            cursor = (cursor + 1) % len(selectable)
        elif pressed in ("KEY_LEFT", "KEY_RIGHT"):
            working[spec.key] = adjust_setting(
                spec, working[spec.key], 1 if pressed == "KEY_RIGHT" else -1
            )
            enforce_constraints(working)
        elif is_enter(pressed) or pressed == " ":
            if spec.kind == "toggle":
                working[spec.key] = adjust_setting(spec, working[spec.key], 1)
            elif spec.kind == "key":
                mode = "rebind"
            elif spec.kind == "dict":
                edited = show_score_editor(term, screen, styles, working[spec.key])
                if edited is not None:
                    working[spec.key] = edited
        elif pressed.lower() == "r":
            mode = "confirm_reset"
        elif pressed.lower() == "s":
            save_settings(working)
            load_settings()
            return
        elif pressed.lower() == "q":
            return


def show_score_editor(
    term: Terminal, screen: Screen, styles: Styles, score_values: dict
) -> Optional[dict]:
    """Edits the SCORE_VALUES dictionary. Returns the edited copy, or None if discarded."""
    working = copy.deepcopy(score_values)
    names = list(working)
    cursor, top = 0, 0

    while True:
        screen.begin()
        w, h = screen.width, screen.height
        list_top = 5
        visible = max(1, h - list_top - 5)
        if cursor < top:
            top = cursor
        if cursor >= top + visible:
            top = cursor - visible + 1

        screen.center(2, "--- Score Value Editor ---", styles.bold)
        line_w = 44
        x = max(0, (w - line_w) // 2)
        for offset in range(min(visible, len(names) - top)):
            idx = top + offset
            value = working[names[idx]]
            shown = f"{value:.2f}" if isinstance(value, float) else str(value)
            screen.put(
                x,
                list_top + offset,
                f"{names[idx]:.<35} {shown:>8}",
                styles.reverse if idx == cursor else "",
            )
        if top > 0:
            screen.put(x + line_w + 1, list_top, "▲")
        if top + visible < len(names):
            screen.put(x + line_w + 1, list_top + visible - 1, "▼")

        screen.center(h - 4, "↑/↓ select    ←/→ change value")
        screen.center(h - 3, "ENTER or S: save & exit    Q: discard & exit")
        screen.flush()

        key = term.inkey(timeout=0.1)
        if not key:
            continue
        pressed = key_name(key)

        if pressed == "KEY_UP":
            cursor = (cursor - 1) % len(names)
        elif pressed == "KEY_DOWN":
            cursor = (cursor + 1) % len(names)
        elif pressed in ("KEY_LEFT", "KEY_RIGHT"):
            direction = 1 if pressed == "KEY_RIGHT" else -1
            name = names[cursor]
            value = working[name]
            if isinstance(value, float):
                working[name] = round(max(0.0, value + direction * 0.1), 2)
            else:
                working[name] = max(0, value + direction * 10)
        elif pressed.lower() == "s" or is_enter(pressed):
            return working
        elif pressed.lower() == "q":
            return None