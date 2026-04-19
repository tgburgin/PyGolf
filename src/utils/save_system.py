"""
save_system.py — JSON save/load for the player's career.

On desktop the save lives on disk at  saves/<player_name>.json  (auto-created).
On the web (pygbag/Android browser) the same logical path is used as a
`localStorage` key — the browser then persists the bytes across sessions for
as long as the user doesn't clear site data.

The public API (`save_game`, `load_game`, `list_saves`, `get_save_preview`,
`delete_save`) returns and accepts "paths" that look like  saves/Foo.json
regardless of platform; callers don't have to branch on where the bytes
actually live.
"""

import json
import os
import re
import time

from src.career.player import Player
from src.utils import web

SAVE_DIR    = "saves"
SAVE_FORMAT = 1

# localStorage key prefix — namespaces our saves so we don't collide with
# anything else on the same origin (e.g. if hosted alongside other apps).
_LS_PREFIX = "pygolf::save::"


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


# ── Storage-agnostic primitives ──────────────────────────────────────────────
# On desktop a "path" is a filesystem path. On the web it's still a path-like
# string (e.g. "saves/Bob.json"), but the bytes live in localStorage under
# _LS_PREFIX + path. The rest of save_system doesn't have to know which.

def _read(path: str) -> str:
    if web.IS_WEB:
        v = web.ls_get(_LS_PREFIX + path)
        if v is None:
            raise FileNotFoundError(path)
        return v
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write(path: str, content: str) -> None:
    if web.IS_WEB:
        if not web.ls_set(_LS_PREFIX + path, content):
            raise OSError(
                "Could not write save to browser storage "
                "(quota exceeded or storage disabled)")
        return
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _remove(path: str) -> None:
    if web.IS_WEB:
        web.ls_remove(_LS_PREFIX + path)
        return
    os.remove(path)


def _list_save_paths() -> list[str]:
    if web.IS_WEB:
        return [k[len(_LS_PREFIX):] for k in web.ls_keys_with_prefix(_LS_PREFIX)]
    os.makedirs(SAVE_DIR, exist_ok=True)
    return [
        os.path.join(SAVE_DIR, f)
        for f in os.listdir(SAVE_DIR)
        if f.endswith(".json")
    ]


def _mtime(path: str) -> float:
    """Newest-first ordering key. On the web we store the write time inside
    the JSON payload (localStorage has no native mtime); on desktop we use
    the filesystem mtime."""
    if web.IS_WEB:
        try:
            return float(json.loads(_read(path)).get("saved_at", 0.0))
        except Exception:
            return 0.0
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


# ── Public API ───────────────────────────────────────────────────────────────

def save_game(player: Player, tournament=None, round_state: dict | None = None) -> str:
    """Serialise the player (and optional active tournament and in-progress
    round state) to JSON.

    ``round_state`` captures the mid-round state needed to resume: hole index,
    strokes, hole scores so far, ball position, wind, last-safe position.
    Pass ``None`` when the player is not currently on a hole.
    """
    path = save_path_for(player.name)
    data = {
        "save_format": SAVE_FORMAT,
        "player":      player.to_dict(),
        "tournament":  tournament.to_dict() if tournament is not None else None,
        "round_state": round_state,
        "saved_at":    time.time(),
    }
    _write(path, json.dumps(data, indent=2))
    return path


def load_game(path: str):
    """Load a save; returns (Player, tournament_dict_or_None, round_state_or_None).

    Raises SaveCorruptError for unparseable saves and SaveVersionError for
    saves written by an incompatible build.
    """
    try:
        data = json.loads(_read(path))
    except (OSError, FileNotFoundError, json.JSONDecodeError) as exc:
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
    """Return all save paths, newest first."""
    paths = _list_save_paths()
    paths.sort(key=_mtime, reverse=True)
    return paths


def delete_save(path: str) -> None:
    """Remove a save. Silently ignores missing saves."""
    try:
        _remove(path)
    except FileNotFoundError:
        pass


def get_save_preview(path: str) -> dict:
    """Return a lightweight summary dict for displaying on the load screen.

    If the save is unreadable or from an incompatible version, the returned
    dict sets `corrupt=True` and `error` to a human-readable reason so the
    UI can show a "(corrupt)" tag and disable Load for that slot.
    """
    try:
        data = json.loads(_read(path))
    except (OSError, FileNotFoundError, json.JSONDecodeError) as exc:
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
