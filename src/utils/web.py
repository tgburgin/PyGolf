"""
web.py — small helpers for the pygbag / Emscripten build target.

All helpers are safe to call on desktop: `IS_WEB` is False there and every
function returns a sensible default (None, False, empty list, etc.) without
touching the browser APIs. This lets the rest of the code call into them
unconditionally rather than branching on platform each time.

Nothing in here is critical-path: every browser call is wrapped in a broad
`except Exception` so a hostile or restricted environment (private browsing,
disabled localStorage, older browser missing screen.orientation) degrades
to a no-op rather than crashing the game.
"""

import sys

IS_WEB = sys.platform == "emscripten"


def _window():
    """Return the browser window proxy, or None if not running under pygbag."""
    if not IS_WEB:
        return None
    try:
        import platform
        return platform.window
    except Exception:
        return None


# ── Orientation & fullscreen ─────────────────────────────────────────────────

def try_lock_landscape() -> None:
    """Best-effort request to pin the device to landscape.

    Most mobile browsers only honour this while the page is in fullscreen and
    the call originated from a user gesture, so we retry after the first tap
    (see main.py). If the request fails it's silently ignored.
    """
    win = _window()
    if win is None:
        return
    try:
        promise = win.screen.orientation.lock("landscape")
        # The promise may reject on unsupported browsers; swallow the rejection
        # so it doesn't show up as an uncaught error in the console.
        try:
            promise.catch(lambda _e: None)
        except Exception:
            pass
    except Exception:
        pass


def try_enter_fullscreen() -> None:
    """Ask the browser to go fullscreen. Only works inside a user gesture."""
    win = _window()
    if win is None:
        return
    try:
        win.document.documentElement.requestFullscreen()
    except Exception:
        pass


def is_portrait() -> bool:
    """True if the browser viewport is taller than it is wide."""
    win = _window()
    if win is None:
        return False
    try:
        return int(win.innerHeight) > int(win.innerWidth)
    except Exception:
        return False


# ── localStorage (UTF-8 string blobs, keyed) ─────────────────────────────────

def ls_get(key: str) -> str | None:
    win = _window()
    if win is None:
        return None
    try:
        v = win.localStorage.getItem(key)
        return None if v is None else str(v)
    except Exception:
        return None


def ls_set(key: str, value: str) -> bool:
    """Return True on success, False if the browser rejected the write
    (quota exceeded, localStorage disabled in private mode, etc.)."""
    win = _window()
    if win is None:
        return False
    try:
        win.localStorage.setItem(key, value)
        return True
    except Exception:
        return False


def ls_remove(key: str) -> None:
    win = _window()
    if win is None:
        return
    try:
        win.localStorage.removeItem(key)
    except Exception:
        pass


def ls_keys_with_prefix(prefix: str) -> list[str]:
    win = _window()
    if win is None:
        return []
    try:
        out: list[str] = []
        ls = win.localStorage
        n = int(ls.length)
        for i in range(n):
            k = ls.key(i)
            if k is None:
                continue
            ks = str(k)
            if ks.startswith(prefix):
                out.append(ks)
        return out
    except Exception:
        return []
