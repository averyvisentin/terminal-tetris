"""
Settings management: definitions, validation, database load/save.
"""

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import get_default_settings, RESERVED_KEYS


@dataclass(frozen=True)
class SettingSpec:
    """Describes one row of the settings menu: how it is shown, stepped and bounded."""

    key: str  # key in SETTINGS / the database
    label: str  # what the menu shows
    kind: str  # 'int' | 'float' | 'toggle' | 'key' | 'dict'
    step: float = 1
    low: float = 0
    high: float = 0
    decimals: int = 2  # display precision for floats
    section: str = ""


SETTING_SPECS: List[SettingSpec] = [
    SettingSpec(
        "BOARD_WIDTH", "Board width", "int", 1, 6, 99, section="Board & Display"
    ),
    SettingSpec(
        "BOARD_HEIGHT", "Board height", "int", 1, 15, 99, section="Board & Display"
    ),
    SettingSpec(
        "PLAYFIELD_Y_OFFSET",
        "Playfield top offset",
        "int",
        1,
        2,
        6,
        section="Board & Display",
    ),
    SettingSpec(
        "MAX_SCORES",
        "High scores kept per mode",
        "int",
        1,
        1,
        10,
        section="High Scores",
    ),
    SettingSpec(
        "MAX_NAME_LENGTH", "Name length", "int", 1, 1, 8, section="High Scores"
    ),
    SettingSpec(
        "INITIAL_GRAVITY_INTERVAL",
        "Starting fall interval (s)",
        "float",
        0.05,
        0.1,
        3.0,
        section="Timing",
    ),
    SettingSpec(
        "GRAVITY_LEVEL_MULTIPLIER",
        "Fall speed-up per level (s)",
        "float",
        0.01,
        0.0,
        0.2,
        section="Timing",
    ),
    SettingSpec(
        "MIN_GRAVITY_INTERVAL",
        "Fastest fall interval (s)",
        "float",
        0.01,
        0.01,
        1.0,
        section="Timing",
    ),
    SettingSpec(
        "Lock Delay (s)", "Lock delay (s)", "float", 0.05, 0.05, 2.0, section="Timing"
    ),
    SettingSpec(
        "FLASH_DURATION",
        "Line-clear flash (s)",
        "float",
        0.05,
        0.0,
        1.0,
        section="Timing",
    ),
    SettingSpec(
        "INPUT_TIMEOUT",
        "Input poll interval (s)",
        "float",
        0.005,
        0.001,
        0.1,
        decimals=3,
        section="Timing",
    ),
    SettingSpec(
        "RENDER_THROTTLE_MS",
        "Min. milliseconds per frame",
        "int",
        2,
        4,
        100,
        section="Timing",
    ),
    SettingSpec(
        "TIMED_MODE_DURATION_S",
        "Timed mode length (s)",
        "int",
        5,
        30,
        600,
        section="Timing",
    ),
    SettingSpec(
        "GARBAGE_INTERVAL_S",
        "Garbage row every (s)",
        "int",
        5,
        5,
        120,
        section="Timing",
    ),
    SettingSpec("MIN_LEVEL", "Lowest start level", "int", 1, 1, 30, section="Gameplay"),
    SettingSpec(
        "MAX_LEVEL", "Highest start level", "int", 1, 1, 30, section="Gameplay"
    ),
    SettingSpec(
        "SPRINT_DEFAULT_LEVEL",
        "Sprint default level",
        "int",
        1,
        1,
        30,
        section="Gameplay",
    ),
    SettingSpec("GHOST_PIECE_ENABLED", "Ghost piece", "toggle", section="Gameplay"),
    SettingSpec("SCORE_VALUES", "Score values", "dict", section="Scoring"),
    SettingSpec("Key: Left", "Move left", "key", section="Controls"),
    SettingSpec("Key: Right", "Move right", "key", section="Controls"),
    SettingSpec("Key: Rotate", "Rotate", "key", section="Controls"),
    SettingSpec("Key: Soft Drop", "Soft drop", "key", section="Controls"),
    SettingSpec("Key: Hard Drop", "Hard drop", "key", section="Controls"),
    SettingSpec("Key: Hold", "Hold", "key", section="Controls"),
]

SPEC_BY_KEY: Dict[str, SettingSpec] = {spec.key: spec for spec in SETTING_SPECS}
KEY_SETTINGS: List[str] = [spec.key for spec in SETTING_SPECS if spec.kind == "key"]

# Global settings dict, populated by load_settings()
SETTINGS: Dict[str, Any] = {}


def coerce_setting(spec: SettingSpec, raw: Any, default: Any) -> Any:
    """Converts a raw stored value to the setting's type and clamps it to its range.
    Falls back to `default` if the stored value is unusable."""
    try:
        if spec.kind == "dict":
            data = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(data, dict):
                return copy.deepcopy(default)
            merged = copy.deepcopy(default)  # keeps any key missing from an older save
            for name, fallback in default.items():
                value = data.get(name, fallback)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                merged[name] = (
                    float(value) if isinstance(fallback, float) else int(value)
                )
            return merged
        if spec.kind == "key":
            text = str(raw)
            return text if text != "" else default
        if spec.kind == "toggle":
            return 1 if int(float(raw)) else 0
        number = min(spec.high, max(spec.low, float(raw)))
        return int(round(number)) if spec.kind == "int" else round(number, 4)
    except (ValueError, TypeError):  # JSONDecodeError is a ValueError
        return copy.deepcopy(default)


def enforce_constraints(settings: dict) -> None:
    """Keeps settings that depend on each other consistent."""
    settings["MAX_LEVEL"] = max(settings["MAX_LEVEL"], settings["MIN_LEVEL"])
    settings["SPRINT_DEFAULT_LEVEL"] = min(
        settings["MAX_LEVEL"],
        max(settings["MIN_LEVEL"], settings["SPRINT_DEFAULT_LEVEL"]),
    )


def sanitize_settings(raw: dict) -> dict:
    """Returns a complete, type-correct, in-range settings dict built from `raw`."""
    defaults = get_default_settings()
    clean = {}
    for key, default in defaults.items():
        spec = SPEC_BY_KEY[key]
        clean[key] = coerce_setting(spec, raw.get(key, default), default)
    enforce_constraints(clean)
    return clean


def format_time(seconds: float) -> str:
    """Formats seconds into a MM:SS.ss string."""
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02}:{remaining_seconds:05.2f}"


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