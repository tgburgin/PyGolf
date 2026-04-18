"""
tours_data.py — tour definitions and course discovery.

Tours
─────
  amateur      Level 1 — local tournaments, earn a card to Challenger
  challenger   Level 2 — semi-pro tour A
  development  Level 3 — semi-pro tour B
  continental  Level 4 — professional tour
  world        Level 5 — professional tour (elite)
  grand        Level 6 — "The Grand Tour" (PGA equivalent)

Courses
───────
JSON-built courses live in  data/courses/<tour>/*.json
Python-built courses live in src/data/courses_data.py  (legacy fallback)

Use  get_courses_for_tour(tour_id)  to get a list of Course objects.
Use  list_tour_ids()  to get all tour names in progression order.
"""

import os
import glob as _glob

from src.course.course import Course

# Tour IDs in progression order
TOUR_ORDER = [
    "amateur",
    "challenger",
    "development",
    "continental",
    "world",
    "grand",
]

TOUR_DISPLAY_NAMES = {
    "amateur":     "Amateur Tour",
    "challenger":  "Challenger Tour",
    "development": "Development Tour",
    "continental": "Continental Tour",
    "world":       "World Tour",
    "grand":       "The Grand Tour",
}

# Project root is two levels above this file: src/data/ → src/ → project root
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_COURSES_DIR  = os.path.join(_PROJECT_ROOT, "data", "courses")


def list_tour_ids() -> list[str]:
    """Return all tour IDs in career-progression order."""
    return list(TOUR_ORDER)


def get_courses_for_tour(tour_id: str) -> list[Course]:
    """
    Return all Course objects for *tour_id*.

    JSON courses in data/courses/<tour_id>/ are loaded first via
    course_loader.  If none exist the legacy Python-built courses are
    returned as a fallback (amateur tour only).
    """
    courses = _load_json_courses(tour_id)
    if not courses:
        from src.data.courses_library import python_courses_for_tour
        courses = python_courses_for_tour(tour_id)
    return courses


def discover_course_paths(tour_id: str) -> list[str]:
    """Return sorted list of JSON file paths for the given tour."""
    tour_dir = os.path.join(_COURSES_DIR, tour_id)
    if not os.path.isdir(tour_dir):
        return []
    return sorted(_glob.glob(os.path.join(tour_dir, "*.json")))


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_json_courses(tour_id: str) -> list[Course]:
    from src.course.course_loader import load_course as _load_json
    courses = []
    for path in discover_course_paths(tour_id):
        try:
            courses.append(_load_json(path))
        except Exception as exc:
            print(f"[tours_data] Failed to load {path}: {exc}")
    return courses


def _load_legacy_courses() -> list[Course]:
    from src.data.courses_data import make_greenfields_course
    return [make_greenfields_course()]
