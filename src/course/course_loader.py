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

from src.constants import SOURCE_TILE as _SOURCE_TILE   # noqa: F401


class CourseValidationError(ValueError):
    """Raised when a course JSON is structurally invalid."""


def load_course(path: str) -> Course:
    """
    Load a JSON course file and return a fully populated Course object.

    Tileset PNGs referenced in the file are loaded automatically.
    Missing tileset files are silently skipped — the renderer falls back
    to procedural textures for those tiles.

    Raises CourseValidationError if the file is structurally invalid
    (missing logic layer, tee/pin outside the grid, no tee or no green,
    or ground/logic dimension mismatch).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    validate_course(data, source=path)

    course_meta = data.get("course", {})
    name = course_meta.get("name", "Unnamed Course")

    project_root = _find_project_root(path)
    tilesets, transparent_ids = _load_tilesets(data.get("tilesets", []), project_root)

    holes = [_build_hole(h, tilesets, transparent_ids) for h in data.get("holes", [])]
    return Course(name=name, holes=holes)


def validate_course(data: dict, source: str = "<dict>") -> None:
    """Raise CourseValidationError with a clear message if the course is malformed.

    Checks applied to every hole:
      - a logic layer (or legacy 'attributes' layer) exists
      - the logic grid has the declared row count and every row has the
        declared column count
      - if a ground layer is present, its dimensions match the logic layer
      - tee and pin coordinates are inside the grid
      - the logic grid contains at least one tee ('X') and one green ('G')
    """
    holes = data.get("holes", [])
    if not holes:
        raise CourseValidationError(f"{source}: course contains no holes")

    for idx, h in enumerate(holes, start=1):
        number = h.get("number", idx)
        rows = int(h.get("grid_rows", 36))
        cols = int(h.get("grid_cols", 48))
        raw_logic  = h.get("logic") or h.get("attributes")
        raw_ground = h.get("ground") or h.get("visual")

        def err(msg: str):
            raise CourseValidationError(f"{source}: hole {number}: {msg}")

        if raw_logic is None:
            err("missing logic layer (no 'logic' or 'attributes' key)")
        if len(raw_logic) != rows:
            err(f"logic layer has {len(raw_logic)} rows, expected {rows}")
        for ri, row in enumerate(raw_logic):
            if len(row) != cols:
                err(f"logic row {ri} has {len(row)} cols, expected {cols}")

        if raw_ground is not None:
            if len(raw_ground) != rows:
                err(f"ground layer rows {len(raw_ground)} != logic rows {rows}")
            for ri, row in enumerate(raw_ground):
                if len(row) != cols:
                    err(f"ground row {ri} has {len(row)} cols, expected {cols}")

        tee = h.get("tee")
        pin = h.get("pin")
        if tee is not None:
            tc, tr = tee
            if not (0 <= tc < cols and 0 <= tr < rows):
                err(f"tee {tee} is outside the {cols}x{rows} grid")
        if pin is not None:
            pc, pr = pin
            if not (0 <= pc < cols and 0 <= pr < rows):
                err(f"pin {pin} is outside the {cols}x{rows} grid")

        flat = "".join(str(c) for row in raw_logic for c in row)
        if "X" not in flat:
            err("logic grid has no tee tile ('X')")
        if "G" not in flat:
            err("logic grid has no green tile ('G')")


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
