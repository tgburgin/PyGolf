"""
editor_app.py — top-level editor application loop (Phase E5).

Layout (1440 × 900)
────────────────────
  Toolbar        : y=0,    h=48
  Left panel     : x=0,    y=48,   w=240, h=828
    Tileset panel:                         h=480
    Attribute panel:                       h=348
  Canvas         : x=240,  y=48,   w=980, h=828
  Right panel    : x=1220, y=48,   w=220, h=828
    Hole info    :                         (par, yds, SI, set tee/pin)
    Course info  :                         (name, tour, holes list)
  Status bar     : y=876,  h=24

Controls
────────
  Left-click / drag         → paint visual tile
  A + left-click / drag     → paint attribute brush
  Shift + left-drag         → rectangle fill (Shift+A = attribute)
  F + left-click            → flood fill (A held = attribute layer)
  Right-click               → eyedropper
  Space/Middle + drag       → pan
  Scroll wheel              → zoom
  After [Set Tee]/[Set Pin] → next canvas click places marker

Keyboard shortcuts
──────────────────
  Ctrl+Z          → Undo
  Ctrl+Y / Ctrl+Shift+Z → Redo
  Ctrl+S          → Save
  Ctrl+O          → Open
  Ctrl+N          → New
  Ctrl+E          → Export
  Ctrl+R          → Recent files
  G               → Toggle grid
  +/-             → Zoom in/out
  Tab             → Cycle view mode (V/A/B)
  P               → Preview
  M               → Toggle ruler (drag to measure yards between two points)
"""

import json as _json
import os
import sys

import pygame
import pygame_gui

_RECENT_PATH = os.path.join(os.path.dirname(__file__), ".recent_files.json")
_RECENT_MAX  = 5

from tools.editor.canvas          import CourseCanvas
from tools.editor.tileset_panel   import TilesetPanel
from tools.editor.attribute_panel import AttributePanel
from tools.editor.hole_panel      import HolePanel
from tools.editor.dialogs import (
    ask_open_png, ask_open_file, ask_save_file,
    make_empty_course, make_empty_hole,
    flush_hole_to_course, load_hole_from_course,
    save_course, load_course, validate_course,
)

# ── Layout constants ──────────────────────────────────────────────────────────
SCREEN_W       = 1440
SCREEN_H       = 900
TOOLBAR_H      = 48
STATUS_H       = 24
LEFT_PANEL_W   = 240
RIGHT_PANEL_W  = 220
CANVAS_W       = SCREEN_W - LEFT_PANEL_W - RIGHT_PANEL_W   # 980
CANVAS_H       = SCREEN_H - TOOLBAR_H - STATUS_H            # 828
TILESET_H      = 480
ATTR_H         = CANVAS_H - TILESET_H                       # 348

CANVAS_RECT      = pygame.Rect(LEFT_PANEL_W,  TOOLBAR_H, CANVAS_W, CANVAS_H)
TILESET_RECT     = pygame.Rect(0,             TOOLBAR_H, LEFT_PANEL_W, TILESET_H)
ATTR_RECT        = pygame.Rect(0,             TOOLBAR_H + TILESET_H, LEFT_PANEL_W, ATTR_H)
RIGHT_PANEL_RECT = pygame.Rect(SCREEN_W - RIGHT_PANEL_W, TOOLBAR_H, RIGHT_PANEL_W, CANVAS_H)

# Colours
C_BG        = (30,  30,  30)
C_TOOLBAR   = (45,  45,  45)
C_STATUS_BG = (38,  38,  38)
C_STATUS_FG = (180, 180, 180)
C_BORDER    = (65,  65,  65)


class EditorApp:
    """Main course editor application."""

    def __init__(self):
        pygame.display.set_caption("Golf Course Editor")
        self._screen  = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self._clock   = pygame.time.Clock()
        self._running = True

        theme_path = os.path.join(os.path.dirname(__file__), "editor_theme.json")
        self._ui = pygame_gui.UIManager(
            (SCREEN_W, SCREEN_H),
            theme_path if os.path.exists(theme_path) else None,
        )

        # Tilesets: id → pygame.Surface
        self._tilesets: dict[str, pygame.Surface] = {}
        self._tileset_paths: dict[str, str]       = {}

        # Course state
        self._course        = make_empty_course()
        self._filepath: str | None = None
        self._dirty         = False
        self._current_hole  = 0

        # Sub-components
        self._canvas  = CourseCanvas(CANVAS_RECT)
        self._tileset = TilesetPanel(TILESET_RECT)
        self._attr    = AttributePanel(ATTR_RECT)
        self._hole_panel = HolePanel(RIGHT_PANEL_RECT, self._ui)

        # Sync canvas defaults
        self._canvas.active_attribute    = self._attr.selected
        self._canvas.auto_derive_enabled = self._attr.auto_derive

        # Load hole 0 into canvas
        self._load_hole(0)

        # Fonts / message overlay
        self._status_font = pygame.font.SysFont("monospace", 13)
        self._msg_font    = pygame.font.SysFont("monospace", 14)
        self._status_msg  = ""
        self._msg_timer   = 0.0

        # Recent files
        self._recent_files: list[str] = self._load_recent_files()

        self._setup_toolbar()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        bh = 30
        by = (TOOLBAR_H - bh) // 2

        def btn(label, x, w):
            return pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(x, by, w, bh),
                text=label,
                manager=self._ui,
            )

        self._btn_new    = btn("New",        8,   60)
        self._btn_open   = btn("Open",       72,  60)
        self._btn_save   = btn("Save",       136, 60)
        self._btn_export = btn("Export",     200, 70)
        self._btn_import = btn("Import PNG", 288, 110)
        self._btn_grid   = btn("Grid",       420, 56)
        self._btn_zoom_m = btn("Zoom -",     480, 64)
        self._btn_zoom_p = btn("Zoom +",     548, 64)
        self._btn_view_v = btn("V",          640, 32)
        self._btn_view_a = btn("A",          676, 32)
        self._btn_view_b = btn("B",          712, 32)
        self._btn_undo    = btn("Undo",       760, 56)
        self._btn_redo    = btn("Redo",       820, 56)
        self._btn_preview = btn("Preview",   884, 80)
        self._btn_recent  = btn("Recent",    972, 76)
        self._btn_ruler   = btn("Ruler",    1056, 76)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while self._running:
            dt = self._clock.tick(60) / 1000.0
            self._msg_timer = max(0.0, self._msg_timer - dt)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    continue

                self._ui.process_events(event)

                if event.type == pygame.KEYDOWN:
                    if self._handle_keydown(event):
                        continue

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    self._on_button(event.ui_element)
                    continue

                # Hole panel (right)
                action = self._hole_panel.handle_event(event)
                if action:
                    self._on_hole_action(action)
                    continue

                # Attribute panel (bottom-left)
                if self._attr.handle_event(event):
                    self._canvas.active_attribute    = self._attr.selected
                    self._canvas.auto_derive_enabled = self._attr.auto_derive
                    continue

                # Tileset panel (top-left)
                if self._tileset.handle_event(event, self._tilesets):
                    if self._tileset.selected_tile is not None:
                        self._canvas.active_brush   = self._tileset.selected_tile
                        self._tileset.selected_tile = None
                    continue

                # Canvas
                prev_set_mode = self._canvas.set_mode
                consumed = self._canvas.handle_event(event, self._tilesets)
                if consumed and event.type == pygame.MOUSEBUTTONDOWN:
                    self._dirty = True
                # Auto-calc yardage when tee or pin is placed
                if (prev_set_mode in ("tee", "pin")
                        and self._canvas.set_mode is None):
                    self._auto_update_yardage()

            self._ui.update(dt)
            self._draw()

        pygame.quit()
        sys.exit()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self._screen.fill(C_BG)

        pygame.draw.rect(self._screen, C_TOOLBAR,
                         pygame.Rect(0, 0, SCREEN_W, TOOLBAR_H))
        pygame.draw.line(self._screen, C_BORDER,
                         (0, TOOLBAR_H - 1), (SCREEN_W, TOOLBAR_H - 1))

        self._tint_view_buttons()
        self._tint_ruler_button()

        self._canvas.draw(self._screen, self._tilesets)

        self._tileset.draw(self._screen, self._tilesets,
                           active_brush=self._canvas.active_brush)
        self._attr.draw(self._screen)

        # Right panel
        self._hole_panel.draw(self._screen, set_mode=self._canvas.set_mode)

        self._draw_status()
        self._ui.draw_ui(self._screen)
        pygame.display.flip()

    def _tint_ruler_button(self):
        r = self._btn_ruler.rect
        active = self._canvas.ruler_mode
        pygame.draw.rect(
            self._screen,
            (255, 220, 0) if active else (60, 60, 60),
            (r.x, r.bottom + 1, r.width, 3),
        )

    def _tint_view_buttons(self):
        mapping = {
            "visual":     self._btn_view_v,
            "attributes": self._btn_view_a,
            "both":       self._btn_view_b,
        }
        for mode, btn in mapping.items():
            r      = btn.rect
            active = (mode == self._canvas.view_mode)
            pygame.draw.rect(
                self._screen,
                (80, 160, 255) if active else (60, 60, 60),
                (r.x, r.bottom + 1, r.width, 3),
            )

    def _draw_status(self):
        sy = SCREEN_H - STATUS_H
        pygame.draw.rect(self._screen, C_STATUS_BG,
                         pygame.Rect(0, sy, SCREEN_W, STATUS_H))
        pygame.draw.line(self._screen, C_BORDER, (0, sy), (SCREEN_W, sy))

        tile_txt = ""
        if self._canvas.hovered_tile is not None:
            c, r = self._canvas.hovered_tile
            attr_char = self._canvas.attribute_grid[r][c]
            from src.golf.terrain import CHAR_TO_TERRAIN, TERRAIN_PROPS
            terr  = CHAR_TO_TERRAIN.get(attr_char)
            tname = TERRAIN_PROPS[terr]["name"] if terr else "?"
            tile_txt = f"({c},{r})  {tname}"

        brush_txt = ""
        if self._canvas.active_brush:
            tid, sc, sr = self._canvas.active_brush
            brush_txt = f"Tile:{tid}({sc},{sr})"

        attr_txt  = f"Attr:{self._canvas.active_attribute.name}"
        zoom_txt  = f"{self._canvas.zoom:.1f}×"
        mode_txt  = self._canvas.view_mode.upper()
        hole_txt  = f"H{self._current_hole + 1}/{len(self._course['holes'])}"
        file_name = os.path.basename(self._filepath) if self._filepath else "Untitled"
        dirty_sfx = " *" if self._dirty else ""

        set_mode_txt = ""
        if self._canvas.set_mode:
            set_mode_txt = f"[PLACE {self._canvas.set_mode.upper()}]"

        ruler_txt = ""
        if self._canvas.ruler_mode:
            yds = self._canvas.ruler_yards
            ruler_txt = f"RULER: {round(yds)} yds" if yds and yds > 0.5 else "RULER (drag to measure)"

        parts = [p for p in [tile_txt, brush_txt, attr_txt, zoom_txt,
                              mode_txt, hole_txt, set_mode_txt, ruler_txt,
                              file_name + dirty_sfx] if p]
        status = "  |  ".join(parts)

        surf = self._status_font.render(status, True, C_STATUS_FG)
        self._screen.blit(surf, (8, sy + (STATUS_H - surf.get_height()) // 2))

        if self._msg_timer > 0:
            msg = self._msg_font.render(self._status_msg, True, (120, 220, 120))
            self._screen.blit(msg, (SCREEN_W - msg.get_width() - 16,
                                    sy + (STATUS_H - msg.get_height()) // 2))

    # ── Button handling ───────────────────────────────────────────────────────

    def _on_button(self, element):
        if element == self._btn_new:
            self._cmd_new()
        elif element == self._btn_open:
            self._cmd_open()
        elif element == self._btn_save:
            self._cmd_save()
        elif element == self._btn_export:
            self._cmd_export()
        elif element == self._btn_import:
            self._cmd_import()
        elif element == self._btn_grid:
            self._canvas.show_grid = not self._canvas.show_grid
        elif element == self._btn_zoom_m:
            self._canvas.zoom_out()
        elif element == self._btn_zoom_p:
            self._canvas.zoom_in()
        elif element == self._btn_view_v:
            self._canvas.view_mode = "visual"
        elif element == self._btn_view_a:
            self._canvas.view_mode = "attributes"
        elif element == self._btn_view_b:
            self._canvas.view_mode = "both"
        elif element == self._btn_undo:
            self._cmd_undo()
        elif element == self._btn_redo:
            self._cmd_redo()
        elif element == self._btn_preview:
            self._run_preview()
        elif element == self._btn_recent:
            self._run_recent_overlay()
        elif element == self._btn_ruler:
            self._toggle_ruler()

    # ── Hole-panel action routing ─────────────────────────────────────────────

    def _on_hole_action(self, action: str):
        if action == "prev_hole":
            self._switch_hole(self._current_hole - 1)
        elif action == "next_hole":
            self._switch_hole(self._current_hole + 1)
        elif action == "calc_yds":
            yds = self._canvas.tee_pin_yards
            if yds is not None:
                self._hole_panel._yds_entry.set_text(str(yds))
                self._dirty = True
                self._show_msg(f"Hole length: {yds} yds (tee → pin)")
            else:
                self._show_msg("Set both tee and pin first.")
        elif action == "arm_tee":
            self._canvas.enter_set_mode("tee")
        elif action == "arm_pin":
            self._canvas.enter_set_mode("pin")
        elif action == "add_hole":
            self._add_hole()
        elif action == "del_hole":
            self._del_hole()
        elif action == "copy_hole":
            self._run_copy_hole_overlay()
        elif action == "resize_grid":
            self._cmd_resize_grid()
        elif action.startswith("go_hole:"):
            idx = int(action.split(":")[1])
            self._switch_hole(idx)

    # ── Hole management ───────────────────────────────────────────────────────

    def _cmd_resize_grid(self):
        cols, rows = self._hole_panel.get_grid_size()
        if cols == self._canvas.cols and rows == self._canvas.rows:
            self._show_msg("Grid is already that size.")
            return
        self._canvas.resize(cols, rows)
        self._dirty = True
        self._show_msg(f"Grid resized to {cols}×{rows}.")

    def _run_copy_hole_overlay(self):
        """Modal overlay: pick a destination slot to copy the current hole into."""
        total  = len(self._course["holes"])
        src    = self._current_hole
        font_h = pygame.font.SysFont("monospace", 14, bold=True)
        font   = pygame.font.SysFont("monospace", 13)
        hint_f = pygame.font.SysFont("monospace", 12)

        bw, bh = 36, 28
        gx, gy = 4, 4
        cols   = 6
        rows   = 3
        pad    = 14
        panel_w = cols * (bw + gx) - gx + pad * 2
        panel_h = pad + 22 + pad // 2 + rows * (bh + gy) - gy + pad
        panel_x = (SCREEN_W - panel_w) // 2
        panel_y = (SCREEN_H - panel_h) // 2

        btn_rects = []
        for i in range(18):
            c = i % cols
            r = i // cols
            btn_rects.append(pygame.Rect(
                panel_x + pad + c * (bw + gx),
                panel_y + pad + 22 + pad // 2 + r * (bh + gy),
                bw, bh,
            ))

        dim   = pygame.Surface((SCREEN_W, SCREEN_H))
        dim.set_alpha(160)
        dim.fill((0, 0, 0))
        hint  = hint_f.render("Click a slot to copy into it  |  Esc to cancel",
                               True, (130, 130, 130))

        running = True
        chosen  = None
        while running:
            mx, my = pygame.mouse.get_pos()
            hovered = next((i for i, r in enumerate(btn_rects)
                            if r.collidepoint(mx, my)), -1)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if hovered >= 0 and hovered != src:
                        chosen = hovered
                    running = False

            self._draw()
            self._screen.blit(dim, (0, 0))
            pygame.draw.rect(self._screen, (48, 48, 48),
                             (panel_x, panel_y, panel_w, panel_h))
            pygame.draw.rect(self._screen, (90, 90, 90),
                             (panel_x, panel_y, panel_w, panel_h), 1)
            hdr = font_h.render(f"Copy Hole {src + 1} to…", True, (200, 200, 200))
            self._screen.blit(hdr, (panel_x + pad, panel_y + pad))

            for i, r in enumerate(btn_rects):
                is_src = (i == src)
                is_hov = (i == hovered and i != src)
                bg = (80, 50, 50) if is_src else ((65, 95, 130) if is_hov else (55, 55, 55))
                pygame.draw.rect(self._screen, bg, r, border_radius=3)
                t = font.render(str(i + 1), True,
                                (140, 140, 140) if is_src else (210, 210, 210))
                self._screen.blit(t, (r.x + (bw - t.get_width()) // 2,
                                      r.y + (bh - t.get_height()) // 2))

            self._screen.blit(hint, (panel_x + panel_w - hint.get_width() - pad,
                                     panel_y + panel_h - hint.get_height() - 6))
            pygame.display.flip()
            self._clock.tick(30)

        if chosen is None:
            return

        self._flush_current_hole()
        import copy as _copy
        src_data = _copy.deepcopy(self._course["holes"][src])

        # Extend holes list if copying to a slot beyond current count
        while len(self._course["holes"]) <= chosen:
            n = len(self._course["holes"]) + 1
            from tools.editor.dialogs import make_empty_hole
            self._course["holes"].append(
                make_empty_hole(self._canvas.cols, self._canvas.rows, n))

        src_data["number"] = chosen + 1
        self._course["holes"][chosen] = src_data
        self._dirty = True
        self._show_msg(f"Hole {src + 1} copied to slot {chosen + 1}.")

    def _flush_current_hole(self):
        """Write canvas + panel state back into _course["holes"][_current_hole]."""
        par, yds, si = self._hole_panel.get_hole_meta()
        name, tour   = self._hole_panel.get_course_meta()
        flush_hole_to_course(
            self._course,
            self._current_hole,
            self._canvas.visual_grid,
            self._canvas.attribute_grid,
            self._canvas.tee_pos,
            self._canvas.pin_pos,
            par, yds, si,
        )
        self._course["course"]["name"] = name
        self._course["course"]["tour"] = tour

    def _load_hole(self, index: int):
        """Load hole data from _course into canvas and hole panel."""
        visual, attrs, tee, pin, cols, rows = load_hole_from_course(
            self._course, index)
        self._canvas.load_grids(visual, attrs)
        self._canvas.tee_pos = tee
        self._canvas.pin_pos = pin
        self._canvas.clear_set_mode()

        holes = self._course["holes"]
        self._hole_panel.populate_hole(holes[index] if index < len(holes) else {})
        self._hole_panel.set_current_hole(index, len(holes))

    def _switch_hole(self, new_index: int):
        total = len(self._course["holes"])
        if not (0 <= new_index < total):
            return
        if new_index == self._current_hole:
            return
        self._flush_current_hole()
        self._current_hole = new_index
        self._load_hole(new_index)
        self._dirty = True

    def _add_hole(self):
        if len(self._course["holes"]) >= 18:
            self._show_msg("Maximum of 18 holes.")
            return
        self._flush_current_hole()
        new_num = len(self._course["holes"]) + 1
        self._course["holes"].append(
            make_empty_hole(self._canvas.cols, self._canvas.rows, new_num))
        new_idx = len(self._course["holes"]) - 1
        self._current_hole = new_idx
        self._load_hole(new_idx)
        self._dirty = True
        self._show_msg(f"Added hole {new_num}.")

    def _del_hole(self):
        if len(self._course["holes"]) <= 1:
            self._show_msg("Cannot delete the last hole.")
            return
        self._course["holes"].pop(self._current_hole)
        new_idx = min(self._current_hole, len(self._course["holes"]) - 1)
        self._current_hole = new_idx
        self._load_hole(new_idx)
        self._dirty = True
        self._show_msg(f"Hole deleted — now on hole {new_idx + 1}.")

    # ── File commands ─────────────────────────────────────────────────────────

    def _cmd_new(self):
        self._course        = make_empty_course()
        self._filepath      = None
        self._dirty         = False
        self._current_hole  = 0
        self._canvas.reset()
        self._tileset.clear()
        self._tilesets.clear()
        self._tileset_paths.clear()
        self._load_hole(0)
        self._hole_panel.populate_course(
            self._course["course"], 1, 0)
        self._show_msg("New course created.")

    def _cmd_import(self):
        path = ask_open_png(initial_dir="assets/tilemaps")
        if not path:
            return
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            sheet = pygame.image.load(path).convert_alpha()
        except pygame.error as exc:
            self._show_msg(f"Load failed: {exc}")
            return
        try:
            rel = os.path.relpath(path).replace("\\", "/")
        except ValueError:
            rel = path.replace("\\", "/")
        self._tilesets[stem]      = sheet
        self._tileset_paths[stem] = rel
        self._tileset.add_tileset(stem, sheet)
        cols = sheet.get_width()  // 16
        rows = sheet.get_height() // 16
        self._show_msg(f"Loaded: {stem}  ({cols}×{rows} tiles)")

    def _cmd_save(self):
        # Flush current hole state into course dict
        self._flush_current_hole()

        # Validate
        issues = validate_course(self._course, self._tileset_paths)
        errors   = [m for lvl, m in issues if lvl == "error"]
        warnings = [m for lvl, m in issues if lvl == "warning"]

        if errors:
            for msg in errors:
                print(f"[ERROR] {msg}")
            self._show_msg(
                f"Save blocked — {len(errors)} error(s). See console.", 5.0)
            return

        if warnings:
            for msg in warnings:
                print(f"[WARNING] {msg}")
            self._show_msg(
                f"Saved with {len(warnings)} warning(s). See console.", 4.0)

        if not self._filepath:
            tour = self._course["course"].get("tour", "development")
            path = ask_save_file(
                initial_dir=os.path.join("data", "courses", tour))
            if not path:
                return
            self._filepath = path

        try:
            save_course(self._course, self._filepath, self._tileset_paths)
            self._dirty = False
            self._add_to_recent(self._filepath)
            if not warnings:
                self._show_msg("Saved.")
        except Exception as exc:
            self._show_msg(f"Save error: {exc}")

    def _cmd_export(self):
        """Export: validate, always prompt for path, write to data/courses/<tour>/."""
        self._flush_current_hole()

        issues  = validate_course(self._course, self._tileset_paths)
        errors  = [m for lvl, m in issues if lvl == "error"]
        warnings = [m for lvl, m in issues if lvl == "warning"]

        if errors:
            for msg in errors:
                print(f"[ERROR] {msg}")
            self._show_msg(f"Export blocked — {len(errors)} error(s). See console.", 5.0)
            return

        if warnings:
            for msg in warnings:
                print(f"[WARNING] {msg}")

        tour = self._course["course"].get("tour", "development")
        path = ask_save_file(initial_dir=os.path.join("data", "courses", tour))
        if not path:
            return

        try:
            save_course(self._course, path, self._tileset_paths)
            self._add_to_recent(path)
        except Exception as exc:
            self._show_msg(f"Export error: {exc}")
            return

        holes      = self._course.get("holes", [])
        course_par = sum(h.get("par", 0) for h in holes)
        name       = self._course["course"].get("name", "Untitled")
        print(f"[EXPORT] {name} | {tour} | {len(holes)} hole(s) | par {course_par}")
        print(f"[EXPORT] Written to: {path}")

        msg = f"Exported: {os.path.basename(path)}"
        if warnings:
            msg += f" ({len(warnings)} warning(s))"
        self._show_msg(msg, 4.0)

    def _cmd_open(self):
        path = ask_open_file(initial_dir="data/courses")
        if not path:
            return
        try:
            course_data, tileset_specs = load_course(path)
        except Exception as exc:
            self._show_msg(f"Load error: {exc}")
            return

        # Reload tilesets
        self._tilesets.clear()
        self._tileset_paths.clear()
        self._tileset.clear()
        for spec in tileset_specs:
            tid, tpath = spec["id"], spec["path"]
            if not os.path.exists(tpath):
                self._show_msg(f"Missing tileset: {tpath}")
                continue
            try:
                sheet = pygame.image.load(tpath).convert_alpha()
                self._tilesets[tid]      = sheet
                self._tileset_paths[tid] = tpath.replace("\\", "/")
                self._tileset.add_tileset(tid, sheet)
            except pygame.error as exc:
                self._show_msg(f"Tileset error: {exc}")

        self._course       = course_data
        self._filepath     = path
        self._dirty        = False
        self._current_hole = 0
        self._add_to_recent(path)

        self._load_hole(0)
        self._hole_panel.populate_course(
            course_data["course"],
            len(course_data.get("holes", [])),
            0,
        )
        self._show_msg(
            f"Opened: {os.path.basename(path)}  "
            f"({len(course_data.get('holes', []))} hole(s))")

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _handle_keydown(self, event) -> bool:
        """Handle global keyboard shortcuts. Returns True if consumed."""
        ctrl  = event.mod & pygame.KMOD_CTRL
        shift = event.mod & pygame.KMOD_SHIFT

        if ctrl:
            if event.key == pygame.K_z:
                if shift:
                    self._cmd_redo()
                else:
                    self._cmd_undo()
                return True
            if event.key == pygame.K_y:
                self._cmd_redo()
                return True
            if event.key == pygame.K_s:
                self._cmd_save()
                return True
            if event.key == pygame.K_o:
                self._cmd_open()
                return True
            if event.key == pygame.K_n:
                self._cmd_new()
                return True
            if event.key == pygame.K_e:
                self._cmd_export()
                return True
            if event.key == pygame.K_r:
                self._run_recent_overlay()
                return True
        else:
            if event.key == pygame.K_g:
                self._canvas.show_grid = not self._canvas.show_grid
                return True
            if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self._canvas.zoom_in()
                return True
            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._canvas.zoom_out()
                return True
            if event.key == pygame.K_p:
                self._run_preview()
                return True
            if event.key == pygame.K_TAB:
                modes = ["visual", "attributes", "both"]
                idx = modes.index(self._canvas.view_mode)
                self._canvas.view_mode = modes[(idx + 1) % 3]
                return True
            if event.key == pygame.K_m:
                self._toggle_ruler()
                return True
        return False

    def _cmd_undo(self):
        if self._canvas.undo():
            self._dirty = True
            self._show_msg("Undo.")
        else:
            self._show_msg("Nothing to undo.")

    def _cmd_redo(self):
        if self._canvas.redo():
            self._dirty = True
            self._show_msg("Redo.")
        else:
            self._show_msg("Nothing to redo.")

    # ── Recent files ──────────────────────────────────────────────────────────

    def _load_recent_files(self) -> list[str]:
        try:
            with open(_RECENT_PATH, "r", encoding="utf-8") as f:
                data = _json.load(f)
            return [p for p in data
                    if isinstance(p, str) and os.path.exists(p)][:_RECENT_MAX]
        except Exception:
            return []

    def _save_recent_files(self):
        try:
            with open(_RECENT_PATH, "w", encoding="utf-8") as f:
                _json.dump(self._recent_files, f, indent=2)
        except Exception:
            pass

    def _add_to_recent(self, path: str):
        path = os.path.abspath(path)
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:_RECENT_MAX]
        self._save_recent_files()

    def _run_recent_overlay(self):
        """Modal overlay listing recent files — click one to open it, Esc to close."""
        if not self._recent_files:
            self._show_msg("No recent files.")
            return

        font_hdr  = pygame.font.SysFont("monospace", 14, bold=True)
        font_item = pygame.font.SysFont("monospace", 13)
        hint_font = pygame.font.SysFont("monospace", 12)

        item_h   = 28
        padding  = 14
        panel_w  = 640
        panel_h  = padding + 24 + len(self._recent_files) * item_h + padding
        panel_x  = (SCREEN_W - panel_w) // 2
        panel_y  = (SCREEN_H - panel_h) // 2

        item_rects = [
            pygame.Rect(panel_x + padding,
                        panel_y + padding + 24 + i * item_h,
                        panel_w - padding * 2, item_h)
            for i in range(len(self._recent_files))
        ]

        dim = pygame.Surface((SCREEN_W, SCREEN_H))
        dim.set_alpha(160)
        dim.fill((0, 0, 0))
        hint = hint_font.render("Esc or click outside to close", True, (130, 130, 130))

        running   = True
        hovered   = -1
        chosen    = None

        while running:
            mx, my = pygame.mouse.get_pos()
            hovered = next((i for i, r in enumerate(item_rects)
                            if r.collidepoint(mx, my)), -1)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if hovered >= 0:
                        chosen = self._recent_files[hovered]
                    running = False

            self._draw()
            self._screen.blit(dim, (0, 0))

            pygame.draw.rect(self._screen, (48, 48, 48),
                             (panel_x, panel_y, panel_w, panel_h))
            pygame.draw.rect(self._screen, (90, 90, 90),
                             (panel_x, panel_y, panel_w, panel_h), 1)

            hdr = font_hdr.render("Recent Files", True, (200, 200, 200))
            self._screen.blit(hdr, (panel_x + padding, panel_y + padding))

            for i, (path, rect) in enumerate(
                    zip(self._recent_files, item_rects)):
                bg = (65, 95, 130) if i == hovered else (55, 55, 55)
                pygame.draw.rect(self._screen, bg, rect, border_radius=3)
                name = os.path.basename(path)
                tour_dir = os.path.basename(os.path.dirname(path))
                label = f"{name}  [{tour_dir}]"
                t = font_item.render(label, True, (210, 210, 210))
                self._screen.blit(t, (rect.x + 6,
                                      rect.y + (item_h - t.get_height()) // 2))

            self._screen.blit(hint,
                              (panel_x + panel_w - hint.get_width() - padding,
                               panel_y + panel_h - hint.get_height() - 6))
            pygame.display.flip()
            self._clock.tick(30)

        if chosen:
            self._open_course_from_path(chosen)

    def _open_course_from_path(self, path: str):
        """Open a course JSON file directly (no dialog), same logic as _cmd_open."""
        try:
            course_data, tileset_specs = load_course(path)
        except Exception as exc:
            self._show_msg(f"Load error: {exc}")
            return

        self._tilesets.clear()
        self._tileset_paths.clear()
        self._tileset.clear()
        for spec in tileset_specs:
            tid, tpath = spec["id"], spec["path"]
            if not os.path.exists(tpath):
                continue
            try:
                sheet = pygame.image.load(tpath).convert_alpha()
                self._tilesets[tid]      = sheet
                self._tileset_paths[tid] = tpath.replace("\\", "/")
                self._tileset.add_tileset(tid, sheet)
            except pygame.error:
                pass

        self._course       = course_data
        self._filepath     = path
        self._dirty        = False
        self._current_hole = 0
        self._add_to_recent(path)

        self._load_hole(0)
        self._hole_panel.populate_course(
            course_data["course"],
            len(course_data.get("holes", [])),
            0,
        )
        self._show_msg(
            f"Opened: {os.path.basename(path)}  "
            f"({len(course_data.get('holes', []))} hole(s))")

    # ── Preview ───────────────────────────────────────────────────────────────

    def _run_preview(self):
        """Modal overlay: render the current hole via CourseRenderer, Esc/click to close."""
        from src.course.hole     import Hole
        from src.course.renderer import CourseRenderer

        par, yds, _si = self._hole_panel.get_hole_meta()
        attr_grid = ["".join(row) for row in self._canvas.attribute_grid]
        tee = self._canvas.tee_pos or (self._canvas.cols // 2, self._canvas.rows - 3)
        pin = self._canvas.pin_pos or (self._canvas.cols // 2, 3)

        hole = Hole(
            number      = self._current_hole + 1,
            par         = par,
            yardage     = yds,
            tee_pos     = tee,
            pin_pos     = pin,
            grid        = attr_grid,
            visual_grid = self._canvas.visual_grid,
            tilesets    = self._tilesets if self._canvas.visual_grid else None,
        )

        try:
            renderer = CourseRenderer(hole)
        except Exception as exc:
            self._show_msg(f"Preview error: {exc}")
            return

        world_w, world_h = renderer.world_size()
        scale    = min(CANVAS_W / world_w, CANVAS_H / world_h)
        scaled_w = int(world_w * scale)
        scaled_h = int(world_h * scale)
        preview  = pygame.transform.smoothscale(
            renderer._course_surface, (scaled_w, scaled_h))

        ox = LEFT_PANEL_W + (CANVAS_W  - scaled_w) // 2
        oy = TOOLBAR_H    + (CANVAS_H  - scaled_h) // 2

        hint_font = pygame.font.SysFont("monospace", 14)
        hint = hint_font.render(
            "PREVIEW  —  Esc or click to close", True, (220, 220, 80))

        dim = pygame.Surface((SCREEN_W, SCREEN_H))
        dim.set_alpha(170)
        dim.fill((0, 0, 0))

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    running = False

            self._draw()
            self._screen.blit(dim, (0, 0))
            self._screen.blit(preview, (ox, oy))
            pygame.draw.rect(
                self._screen, (90, 160, 90),
                pygame.Rect(ox - 2, oy - 2, scaled_w + 4, scaled_h + 4), 2)
            self._screen.blit(
                hint, (LEFT_PANEL_W + (CANVAS_W - hint.get_width()) // 2,
                        TOOLBAR_H + 8))
            pygame.display.flip()
            self._clock.tick(30)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _toggle_ruler(self):
        self._canvas.ruler_mode = not self._canvas.ruler_mode
        if not self._canvas.ruler_mode:
            self._canvas._ruler_start    = None
            self._canvas._ruler_end      = None
            self._canvas._ruler_dragging = False
        self._show_msg("Ruler ON — drag to measure." if self._canvas.ruler_mode
                       else "Ruler OFF.")

    def _auto_update_yardage(self):
        """After tee/pin placement, recalculate and fill in yardage from tee→pin."""
        yds = self._canvas.tee_pin_yards
        if yds is not None:
            self._hole_panel._yds_entry.set_text(str(yds))
            self._dirty = True
            self._show_msg(f"Hole length: {yds} yds (tee → pin)")

    def _show_msg(self, text: str, duration: float = 3.0):
        self._status_msg = text
        self._msg_timer  = duration
