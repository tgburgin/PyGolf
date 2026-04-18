"""
course_loader.py — load JSON courses produced by the editor into Course/Hole objects.

Supports both v2 (visual + attributes) and v3 (ground + detail + logic) formats.
v2 files are silently migrated: visual→ground, empty detail, attributes→logic.

Usage
─────
    from src.course.course_loader import load_course
    course = load_course("data/courses/amateur/greenfields.json")
"""

import json
import os
import pygame

from src.course.course import Course
from src.course.hole   import Hole

# Must match tools/editor/canvas.py SOURCE_TILE
_SOURCE_TILE = 16


def load_course(path: str) -> Course:
    """
    Load a JSON course file and return a fully populated Course object.

    Tileset PNGs referenced in the file are loaded automatically.
    Missing tileset files are silently skipped — the renderer falls back
    to procedural textures for those tiles.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    course_meta = data.get("course", {})
    name = course_meta.get("name", "Unnamed Course")

    project_root = _find_project_root(path)
    tilesets, transparent_ids = _load_tilesets(data.get("tilesets", []), project_root)

    holes = [_build_hole(h, tilesets, transparent_ids) for h in data.get("holes", [])]
    return Course(name=name, holes=holes)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_hole(h: dict, tilesets: dict, transparent_ids: set) -> Hole:
    """Convert a JSON hole dict into a Hole object. Handles v2 and v3 formats."""
    rows = h.get("grid_rows", 36)
    cols = h.get("grid_cols", 48)

    # ── Detect format version ────────────────────────────────────────────────
    is_v3 = "ground" in h or "logic" in h

    if is_v3:
        # v3 format: ground / detail / logic
        raw_logic = h.get("logic") or h.get("attributes")
        raw_ground = h.get("ground") or h.get("visual")
        raw_detail = h.get("detail")
    else:
        # v2 format: visual / attributes — migrate on the fly
        raw_logic  = h.get("attributes")
        raw_ground = h.get("visual")
        raw_detail = None

    # Logic layer → list[str] (one string per row, chars are terrain codes)
    if raw_logic and len(raw_logic) == rows:
        grid = ["".join(str(c) for c in row[:cols]) for row in raw_logic]
    else:
        grid = ["R" * cols for _ in range(rows)]

    tee = tuple(h["tee"]) if h.get("tee") else (cols // 2, rows - 3)
    pin = tuple(h["pin"]) if h.get("pin") else (cols // 2, 3)

    ground_layer = _decode_tile_grid(raw_ground) if raw_ground else None
    detail_layer = _decode_tile_grid(raw_detail) if raw_detail else None

    return Hole(
        number       = h.get("number", 1),
        par          = h.get("par", 4),
        yardage      = h.get("yardage", 0),
        tee_pos      = tee,
        pin_pos      = pin,
        grid         = grid,
        ground_layer = ground_layer,
        detail_layer = detail_layer,
        tilesets     = tilesets if (ground_layer or detail_layer) else None,
    )


def _decode_tile_grid(json_grid: list) -> list:
    """Decode a JSON tile grid (None | "" | "id:col:row" strings) to (id,col,row) tuples."""
    result = []
    for row in json_grid:
        decoded_row = []
        for cell in row:
            if cell is None or cell == "":
                decoded_row.append(None)
            elif isinstance(cell, str):
                parts = cell.split(":")
                decoded_row.append(
                    (parts[0], int(parts[1]), int(parts[2]))
                    if len(parts) == 3 else None
                )
            else:
                decoded_row.append(None)
        result.append(decoded_row)
    return result


def _load_tilesets(specs: list, project_root: str) -> tuple[dict, set]:
    """
    Load each tileset PNG and return ({id: Surface}, {transparent_id, ...}).
    Transparent tilesets are loaded with convert_alpha(); opaque use convert_alpha()
    as well so the renderer can handle both uniformly.
    """
    sheets: dict[str, pygame.Surface] = {}
    transparent_ids: set[str] = set()

    if not pygame.get_init():
        return sheets, transparent_ids

    for spec in specs:
        tid   = spec.get("id", "")
        tpath = spec.get("path", "")
        is_transparent = spec.get("transparent", False)

        abs_path = (
            os.path.normpath(os.path.join(project_root, tpath))
            if not os.path.isabs(tpath) else tpath
        )
        if os.path.exists(abs_path):
            try:
                sheets[tid] = pygame.image.load(abs_path).convert_alpha()
                if is_transparent:
                    transparent_ids.add(tid)
            except Exception:
                pass

    return sheets, transparent_ids


def _find_project_root(json_path: str) -> str:
    """Walk up from the JSON file until we find a directory containing main.py."""
    d = os.path.dirname(os.path.abspath(json_path))
    for _ in range(10):
        if os.path.exists(os.path.join(d, "main.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()
