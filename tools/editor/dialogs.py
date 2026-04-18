"""
dialogs.py — file open/save wrappers and course JSON helpers.

Three-layer model (v3 format)
──────────────────────────────
  ground    : list[list[None|(id,col,row)]]  — opaque base tiles
  detail    : list[list[None|(id,col,row)]]  — transparent overlay tiles
  logic     : list[list[str]]               — terrain code chars

On disk the tile grids are encoded as:
  None  → null (JSON) for ground, "" for detail
  tuple → "id:col:row" string

v2 files (visual + attributes) are auto-migrated on load:
  visual      → ground
  empty grid  → detail
  attributes  → logic
"""

import copy
import json
import os

import tkinter as tk
from tkinter import filedialog


# ── File dialogs ──────────────────────────────────────────────────────────────

def ask_open_png(initial_dir="assets/tilemaps"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        parent=root,
        initialdir=initial_dir,
        title="Import Tileset PNG",
        filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


def ask_open_file(initial_dir="data/courses"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        parent=root,
        initialdir=initial_dir,
        title="Open Course",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


def ask_save_file(initial_dir="data/courses"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        parent=root,
        initialdir=initial_dir,
        title="Save Course",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


# ── Course data helpers ───────────────────────────────────────────────────────

def make_empty_hole(cols: int = 48, rows: int = 36, number: int = 1) -> dict:
    """Return a blank hole dict in v3 format."""
    return {
        "number":       number,
        "par":          4,
        "yardage":      0,
        "stroke_index": number,
        "tee":          [cols // 2, rows - 3],
        "pin":          [cols // 2, 3],
        "grid_cols":    cols,
        "grid_rows":    rows,
        "ground":       [[None] * cols for _ in range(rows)],
        "detail":       [[None] * cols for _ in range(rows)],
        "logic":        [["R"]  * cols for _ in range(rows)],
    }


def make_empty_course(rows: int = 36, cols: int = 48) -> dict:
    """Return a fresh course dict in v3 format with one blank hole."""
    return {
        "version": 3,
        "course": {
            "name": "Untitled",
            "tour": "development",
            "par":  72,
        },
        "tilesets": [],
        "holes": [make_empty_hole(cols, rows, 1)],
    }


def flush_hole_to_course(course_data: dict, hole_index: int,
                          ground_grid, detail_grid, logic_grid,
                          tee_pos, pin_pos,
                          par: int, yds: int, si: int) -> None:
    """
    Write canvas state into course_data["holes"][hole_index].

    ground_grid : list[list[(id,col,row)|None]]
    detail_grid : list[list[(id,col,row)|None]]
    logic_grid  : list[list[str]]
    tee_pos / pin_pos : (col, row) | None
    """
    holes = course_data["holes"]
    rows  = len(ground_grid)
    cols  = len(ground_grid[0]) if ground_grid else 0

    while len(holes) <= hole_index:
        holes.append(make_empty_hole(cols, rows, len(holes) + 1))

    h = holes[hole_index]
    h["ground"]       = ground_grid
    h["detail"]       = detail_grid
    h["logic"]        = logic_grid
    h["tee"]          = list(tee_pos) if tee_pos else h.get("tee", [cols // 2, rows - 3])
    h["pin"]          = list(pin_pos) if pin_pos else h.get("pin", [cols // 2, 3])
    h["par"]          = par
    h["yardage"]      = yds
    h["stroke_index"] = si
    h["grid_rows"]    = rows
    h["grid_cols"]    = cols
    # Remove any legacy v2 keys
    h.pop("visual",      None)
    h.pop("attributes",  None)


def load_hole_from_course(course_data: dict, hole_index: int):
    """
    Extract hole canvas state from course_data.

    Returns (ground_grid, detail_grid, logic_grid, tee_pos, pin_pos, cols, rows).
    Grid cells are Python tuples (None or (id, col, row)).
    Auto-migrates v2 holes (visual/attributes) to v3 (ground/detail/logic).
    """
    holes = course_data.get("holes", [])
    if hole_index >= len(holes):
        rows, cols = 36, 48
        return (
            [[None] * cols for _ in range(rows)],
            [[None] * cols for _ in range(rows)],
            [["R"]  * cols for _ in range(rows)],
            None, None, cols, rows,
        )

    h    = holes[hole_index]
    rows = h.get("grid_rows", 36)
    cols = h.get("grid_cols", 48)

    # Detect v2 vs v3
    if "ground" in h or "logic" in h:
        ground = h.get("ground") or [[None] * cols for _ in range(rows)]
        detail = h.get("detail") or [[None] * cols for _ in range(rows)]
        logic  = h.get("logic")  or [["R"]  * cols for _ in range(rows)]
    else:
        # v2 migration
        ground = h.get("visual")     or [[None] * cols for _ in range(rows)]
        detail = [[None] * cols for _ in range(rows)]
        logic  = h.get("attributes") or [["R"]  * cols for _ in range(rows)]

    tee = tuple(h["tee"]) if h.get("tee") else None
    pin = tuple(h["pin"]) if h.get("pin") else None

    return ground, detail, logic, tee, pin, cols, rows


def save_course(course_data: dict, path: str,
                tileset_registry: dict,
                transparent_tilesets: set | None = None) -> None:
    """
    Encode all holes to string format and write JSON v3 to disk.

    tileset_registry     : dict {id: filepath}
    transparent_tilesets : set of tileset IDs that are RGBA detail sheets
    """
    transparent_tilesets = transparent_tilesets or set()
    data = copy.deepcopy(course_data)
    data["version"] = 3

    used_ids: set[str] = set()

    for hole in data["holes"]:
        # Encode ground layer
        if "ground" in hole:
            hole["ground"] = _tile_grid_to_json(hole["ground"], empty_val=None)
        elif "visual" in hole:
            # Migrate legacy key
            hole["ground"] = _tile_grid_to_json(hole.pop("visual"), empty_val=None)

        # Encode detail layer
        if "detail" in hole:
            hole["detail"] = _tile_grid_to_json(hole["detail"], empty_val="")
        else:
            rows = hole.get("grid_rows", 36)
            cols = hole.get("grid_cols", 48)
            hole["detail"] = [[""] * cols for _ in range(rows)]

        # Encode logic layer
        if "logic" not in hole and "attributes" in hole:
            hole["logic"] = hole.pop("attributes")

        # Collect referenced tileset IDs
        for grid_key in ("ground", "detail"):
            for row in hole.get(grid_key, []):
                for cell in row:
                    if isinstance(cell, str) and ":" in cell:
                        used_ids.add(cell.split(":")[0])

    # Rebuild tilesets list from actually-used IDs
    data["tilesets"] = [
        {
            "id":          tid,
            "path":        tileset_registry[tid],
            "transparent": tid in transparent_tilesets,
        }
        for tid in sorted(used_ids)
        if tid in tileset_registry
    ]

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_course(path: str):
    """
    Load a course JSON file (v2 or v3).

    Returns (course_data, tileset_specs).
    All hole tile grids are decoded to Python tuples (None or (id, col, row)).
    v2 files are migrated in-memory but not written back.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for hole in data.get("holes", []):
        rows = hole.get("grid_rows", 36)
        cols = hole.get("grid_cols", 48)

        if "ground" in hole or "logic" in hole:
            # v3 format
            if "ground" in hole:
                hole["ground"] = _json_to_tile_grid(hole["ground"])
            else:
                hole["ground"] = [[None] * cols for _ in range(rows)]

            if "detail" in hole:
                hole["detail"] = _json_to_tile_grid(hole["detail"])
            else:
                hole["detail"] = [[None] * cols for _ in range(rows)]
        else:
            # v2 migration
            raw_visual = hole.get("visual")
            hole["ground"] = _json_to_tile_grid(raw_visual) if raw_visual else \
                             [[None] * cols for _ in range(rows)]
            hole["detail"] = [[None] * cols for _ in range(rows)]
            if "attributes" in hole:
                hole["logic"] = hole.pop("attributes")

    return data, data.get("tilesets", [])


def validate_course(course_data: dict,
                    tileset_registry: dict | None = None,
                    transparent_ids: set | None = None) -> list[tuple[str, str]]:
    """
    Validate course_data. Returns list of (level, message) tuples.
    Errors block saving; warnings do not.
    """
    issues: list[tuple[str, str]] = []
    holes = course_data.get("holes", [])

    if tileset_registry is not None:
        missing: set[str] = set()
        for hole in holes:
            for grid_key in ("ground", "detail", "visual"):
                for row in hole.get(grid_key, []):
                    for cell in row:
                        if cell is not None and isinstance(cell, (tuple, list)):
                            tid = cell[0]
                            if tid not in tileset_registry:
                                missing.add(tid)
                        elif isinstance(cell, str) and ":" in cell:
                            tid = cell.split(":")[0]
                            if tid not in tileset_registry:
                                missing.add(tid)
        for tid in sorted(missing):
            issues.append(("error", f"Tileset '{tid}' is used but not loaded."))

    # Warn if detail layer references non-transparent tilesets, or is out of bounds
    for i, hole in enumerate(holes):
        n        = hole.get("number", i + 1)
        h_rows   = hole.get("grid_rows", 36)
        h_cols   = hole.get("grid_cols", 48)
        bad_opaque   = False
        bad_boundary = False

        detail = hole.get("detail", [])
        for r, row in enumerate(detail):
            for c, cell in enumerate(row):
                tid = None
                if isinstance(cell, (tuple, list)) and len(cell) >= 1:
                    tid = cell[0]
                elif isinstance(cell, str) and ":" in cell:
                    tid = cell.split(":")[0]
                if tid is None:
                    continue
                # Boundary check
                if r >= h_rows or c >= h_cols:
                    bad_boundary = True
                # Non-transparent tileset check
                if transparent_ids is not None and tid not in transparent_ids:
                    bad_opaque = True

        if bad_opaque:
            issues.append(("warning",
                           f"Hole {n}: detail layer references a non-transparent tileset."))
        if bad_boundary:
            issues.append(("warning",
                           f"Hole {n}: detail tile placed outside the course boundary."))

    if not holes:
        issues.append(("error", "Course has no holes."))
        return issues

    for i, hole in enumerate(holes):
        n = hole.get("number", i + 1)

        if not hole.get("tee"):
            issues.append(("error", f"Hole {n}: tee position not set."))
        if not hole.get("pin"):
            issues.append(("error", f"Hole {n}: pin position not set."))

        tee = hole.get("tee")
        if tee:
            tc, tr = tee
            logic = hole.get("logic") or hole.get("attributes", [])
            if (logic and 0 <= tr < len(logic)
                    and 0 <= tc < len(logic[tr])
                    and logic[tr][tc] != "X"):
                issues.append(("warning",
                                f"Hole {n}: tee marker is not on a Tee Box tile."))

        pin = hole.get("pin")
        if pin:
            pc, pr = pin
            logic = hole.get("logic") or hole.get("attributes", [])
            if (logic and 0 <= pr < len(logic)
                    and 0 <= pc < len(logic[pr])
                    and logic[pr][pc] != "G"):
                issues.append(("warning",
                                f"Hole {n}: pin marker is not on a Green tile."))

        par = hole.get("par", 0)
        if not (3 <= par <= 6):
            issues.append(("warning", f"Hole {n}: unusual par value ({par})."))

        yds = hole.get("yardage", 0)
        if yds <= 0:
            issues.append(("warning", f"Hole {n}: yardage not set."))

        si = hole.get("stroke_index", 0)
        if not (1 <= si <= 18):
            issues.append(("warning",
                            f"Hole {n}: stroke index out of range ({si})."))

    if len(holes) == 18:
        si_vals = [h.get("stroke_index") for h in holes]
        if len(set(si_vals)) != 18:
            issues.append(("warning",
                            "Stroke indices are not all unique across 18 holes."))

    return issues


# ── Internal encoding helpers ─────────────────────────────────────────────────

def _tile_grid_to_json(grid, empty_val=None) -> list:
    """Convert tile grid (None|(id,col,row) tuples) to JSON-serialisable form."""
    result = []
    for row in grid:
        json_row = []
        for cell in row:
            if cell is None:
                json_row.append(empty_val)
            elif isinstance(cell, (tuple, list)):
                tid, sc, sr = cell
                json_row.append(f"{tid}:{sc}:{sr}")
            else:
                json_row.append(cell)
        result.append(json_row)
    return result


def _json_to_tile_grid(json_grid) -> list:
    """Decode JSON grid (null/""/  "id:col:row" strings) back to tuples."""
    result = []
    for row in json_grid:
        decoded = []
        for cell in row:
            if cell is None or cell == "":
                decoded.append(None)
            elif isinstance(cell, str) and ":" in cell:
                parts = cell.split(":")
                decoded.append((parts[0], int(parts[1]), int(parts[2]))
                               if len(parts) == 3 else None)
            else:
                decoded.append(None)
        result.append(decoded)
    return result
