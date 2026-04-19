"""
save_system.py — JSON save/load for the player's career.

Save files live in  saves/<player_name>.json  (auto-created).
"""

import json
import os
import re

from src.career.player import Player

SAVE_DIR    = "saves"
SAVE_FORMAT = 1


class SaveVersionError(Exception):
    """Raised when a save file's version is incompatible with this build."""


class SaveCorruptError(Exception):
    """Raised when a save file cannot be parsed as a valid save."""


def _safe_filename(name: str) -> str:
    """Convert a player name to a safe filename (strip non-alphanumeric)."""
    safe = re.sub(r"[^\w\s-]", "", name).strip()
    safe = re.sub(r"\s+", "_", safe)
    return safe or "player"


def save_path_for(player_name: str) -> str:
    return os.path.join(SAVE_DIR, f"{_safe_filename(player_name)}.json")


def save_game(player: Player, tournament=None, round_state: dict | None = None) -> str:
    """Serialise the player (and optional active tournament and in-progress
    round state) to JSON.

    ``round_state`` captures the mid-round state needed to resume: hole index,
    strokes, hole scores so far, ball position, wind, last-safe position.
    Pass ``None`` when the player is not currently on a hole.
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    path = save_path_for(player.name)
    data = {
        "save_format": SAVE_FORMAT,
        "player":      player.to_dict(),
        "tournament":  tournament.to_dict() if tournament is not None else None,
        "round_state": round_state,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def load_game(path: str):
    """Load a save file; returns (Player, tournament_dict_or_None, round_state_or_None).

    Raises SaveCorruptError for unparseable files and SaveVersionError for
    files written by an incompatible build.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveCorruptError(f"Could not read save: {exc}") from exc

    version = data.get("save_format", 0)
    if version != SAVE_FORMAT:
        raise SaveVersionError(
            f"Save format v{version} is not compatible with this build (v{SAVE_FORMAT})."
        )

    try:
        player = Player.from_dict(data["player"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveCorruptError(f"Save is missing required player data: {exc}") from exc

    return player, data.get("tournament"), data.get("round_state")


def list_saves() -> list[str]:
    """Return all .json paths in SAVE_DIR, newest first."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    paths = [
        os.path.join(SAVE_DIR, f)
        for f in os.listdir(SAVE_DIR)
        if f.endswith(".json")
    ]
    paths.sort(key=os.path.getmtime, reverse=True)
    return paths


def get_save_preview(path: str) -> dict:
    """Return a lightweight summary dict for displaying on the load screen.

    If the file is unreadable or from an incompatible version, the returned
    dict sets `corrupt=True` and `error` to a human-readable reason so the
    UI can show a "(corrupt)" tag and disable Load for that slot.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "name":    os.path.basename(path),
            "path":    path,
            "corrupt": True,
            "error":   f"Unreadable: {exc}",
        }

    version = data.get("save_format", 0)
    if version != SAVE_FORMAT:
        return {
            "name":    os.path.basename(path),
            "path":    path,
            "corrupt": True,
            "error":   f"Incompatible save version (v{version}, expected v{SAVE_FORMAT})",
        }

    p = data.get("player", {})
    log = p.get("career_log", [])
    return {
        "name":          p.get("name", "Unknown"),
        "nationality":   p.get("nationality", ""),
        "tour_level":    p.get("tour_level", 1),
        "events_played": p.get("events_played", 0),
        "money":         p.get("money", 0),
        "last_round":    log[-1] if log else None,
        "path":          path,
        "corrupt":       False,
    }
