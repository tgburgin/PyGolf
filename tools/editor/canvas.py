"""
canvas.py — zoomable, pannable two-layer course painting canvas.

Layers
──────
  visual_grid[row][col]    : (tileset_id, src_col, src_row) | None
  attribute_grid[row][col] : Terrain char value ('F', 'R', 'B', …)

View modes
──────────
  'visual'     — draw visual tiles only
  'attributes' — draw solid attribute-colour blocks only
  'both'       — visual tiles with a semi-transparent attribute overlay

Controls
────────
  Left-click / drag          → paint active visual brush
  A + left-click / drag      → paint active attribute brush
  Shift + left-drag          → rectangle fill (visual; Shift+A = attribute)
  F + left-click             → flood fill (A held = attribute layer)
  Right-click                → eyedropper (samples visual or attribute)
  Ctrl+Z                     → undo (up to 50 steps)
  Ctrl+Y / Ctrl+Shift+Z      → redo
  Middle-click / Space+drag  → pan
  Scroll wheel               → zoom
"""

import math
import pygame
from collections import deque
from copy import deepcopy

from src.golf.terrain import Terrain, TERRAIN_PROPS, CHAR_TO_TERRAIN
from tools.editor.auto_derive import derive as _auto_derive

SOURCE_TILE        = 16
BASE_TILE          = 16

ZOOM_LEVELS        = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
DEFAULT_ZOOM_INDEX = 3

OVERLAY_ALPHA = 110
MAX_UNDO      = 50

_MINI_MAX_W  = 200
_MINI_MAX_H  = 150
_MINI_MARGIN = 8


class CourseCanvas:
    """
    Renders and handles interaction for the two-layer tile-painting canvas.

    Coordinate systems
    ──────────────────
    World  : 0 → cols*BASE_TILE  /  0 → rows*BASE_TILE  (pixels)
    Camera : (self._ox, self._oy) = world point at canvas top-left
    Screen : rect.x + (world_x - _ox) * zoom
    """

    def __init__(self, rect: pygame.Rect, rows: int = 36, cols: int = 48):
        self.rect = rect
        self.rows = rows
        self.cols = cols

        self._zoom_index = DEFAULT_ZOOM_INDEX
        self._ox = 0.0
        self._oy = 0.0

        # ── Two-layer grids ───────────────────────────────────────────────────
        self.visual_grid    = [[None] * cols for _ in range(rows)]
        self.attribute_grid = [["R"]  * cols for _ in range(rows)]

        # ── Active brushes ────────────────────────────────────────────────────
        self.active_brush     = None
        self.active_attribute = Terrain.ROUGH

        # ── Display options ───────────────────────────────────────────────────
        self.show_grid           = True
        self.view_mode           = "both"
        self.auto_derive_enabled = True

        # ── Caches ────────────────────────────────────────────────────────────
        self._tile_cache: dict = {}
        self._overlay_surf     = None

        # ── Tee / Pin ─────────────────────────────────────────────────────────
        self.tee_pos: tuple[int, int] | None = None
        self.pin_pos: tuple[int, int] | None = None
        self._set_mode: str | None  = None
        self._marker_font           = None

        # ── Undo / Redo ───────────────────────────────────────────────────────
        self._undo_stack: deque          = deque()
        self._redo_stack: deque          = deque()
        self._stroke_snapshot_taken: bool = False

        # ── Rect selection (Shift+drag) ────────────────────────────────────────
        self._rect_start: tuple[int, int] | None = None
        self._rect_end:   tuple[int, int] | None = None
        self._rect_attr:  bool = False

        # ── Ruler tool ───────────────────────────────────────────────────────
        self.ruler_mode          = False
        self._ruler_start: tuple | None = None  # world-pixel coords
        self._ruler_end:   tuple | None = None
        self._ruler_dragging     = False
        self._ruler_font         = None

        # ── Interaction state ─────────────────────────────────────────────────
        self.hovered_tile        = None
        self._painting           = False
        self._painting_attribute = False
        self._erasing            = False
        self._panning            = False
        self._pan_start_mouse    = (0, 0)
        self._pan_start_offset   = (0.0, 0.0)

        self._center_on_world()

    # ── Public helpers ────────────────────────────────────────────────────────

    @property
    def zoom(self) -> float:
        return ZOOM_LEVELS[self._zoom_index]

    def zoom_in(self):
        if self._zoom_index < len(ZOOM_LEVELS) - 1:
            self._zoom_at_screen_centre(self._zoom_index + 1)

    def zoom_out(self):
        if self._zoom_index > 0:
            self._zoom_at_screen_centre(self._zoom_index - 1)

    @property
    def set_mode(self) -> str | None:
        return self._set_mode

    def enter_set_mode(self, mode: str) -> None:
        self._set_mode = mode

    def clear_set_mode(self) -> None:
        self._set_mode = None

    @property
    def tee_pin_yards(self) -> int | None:
        """Straight-line tee→pin distance in yards (1 tile = 10 yds), or None."""
        if self.tee_pos is None or self.pin_pos is None:
            return None
        tc, tr = self.tee_pos
        pc, pr = self.pin_pos
        dx = (pc - tc) * BASE_TILE
        dy = (pr - tr) * BASE_TILE
        return round(math.sqrt(dx * dx + dy * dy) / BASE_TILE * 10)

    @property
    def ruler_yards(self) -> float | None:
        """Current ruler measurement in yards, or None if no ruler drawn."""
        if self._ruler_start is None or self._ruler_end is None:
            return None
        dx = self._ruler_end[0] - self._ruler_start[0]
        dy = self._ruler_end[1] - self._ruler_start[1]
        return math.sqrt(dx * dx + dy * dy) / BASE_TILE * 10

    def reset(self, rows: int = 36, cols: int = 48):
        self.rows = rows
        self.cols = cols
        self.visual_grid    = [[None] * cols for _ in range(rows)]
        self.attribute_grid = [["R"]  * cols for _ in range(rows)]
        self.tee_pos        = None
        self.pin_pos        = None
        self._set_mode      = None
        self._tile_cache.clear()
        self._overlay_surf  = None
        self._zoom_index    = DEFAULT_ZOOM_INDEX
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._stroke_snapshot_taken = False
        self._rect_start = None
        self._rect_end   = None
        self._erasing    = False
        self._ruler_start    = None
        self._ruler_end      = None
        self._ruler_dragging = False
        self._center_on_world()

    def load_grids(self, visual_grid, attribute_grid=None):
        self.rows        = len(visual_grid)
        self.cols        = len(visual_grid[0]) if visual_grid else 0
        self.visual_grid = visual_grid

        if attribute_grid and len(attribute_grid) == self.rows:
            valid = set(CHAR_TO_TERRAIN.keys())
            self.attribute_grid = [
                [c if c in valid else "R" for c in row]
                for row in attribute_grid
            ]
        else:
            self.attribute_grid = [["R"] * self.cols for _ in range(self.rows)]

        self._tile_cache.clear()
        self._overlay_surf = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._stroke_snapshot_taken = False

    def load_visual_grid(self, visual_grid):
        self.load_grids(visual_grid)

    def resize(self, new_cols: int, new_rows: int):
        """Resize the canvas grids, preserving existing content (top-left anchored)."""
        self.push_undo()
        new_visual = [[None] * new_cols for _ in range(new_rows)]
        new_attrs  = [["R"]  * new_cols for _ in range(new_rows)]
        copy_rows  = min(self.rows, new_rows)
        copy_cols  = min(self.cols, new_cols)
        for r in range(copy_rows):
            for c in range(copy_cols):
                new_visual[r][c] = self.visual_grid[r][c]
                new_attrs[r][c]  = self.attribute_grid[r][c]
        self.rows           = new_rows
        self.cols           = new_cols
        self.visual_grid    = new_visual
        self.attribute_grid = new_attrs
        # Clamp markers that would fall outside the new bounds
        if self.tee_pos and (self.tee_pos[0] >= new_cols or self.tee_pos[1] >= new_rows):
            self.tee_pos = None
        if self.pin_pos and (self.pin_pos[0] >= new_cols or self.pin_pos[1] >= new_rows):
            self.pin_pos = None
        self._tile_cache.clear()
        self._overlay_surf = None
        self._clamp_offset()

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def push_undo(self):
        """Save current state to undo stack (max MAX_UNDO entries)."""
        snapshot = (
            deepcopy(self.visual_grid),
            deepcopy(self.attribute_grid),
            self.tee_pos,
            self.pin_pos,
        )
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.popleft()
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append((
            deepcopy(self.visual_grid),
            deepcopy(self.attribute_grid),
            self.tee_pos,
            self.pin_pos,
        ))
        vg, ag, tee, pin = self._undo_stack.pop()
        self.visual_grid    = vg
        self.attribute_grid = ag
        self.tee_pos = tee
        self.pin_pos = pin
        self._tile_cache.clear()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append((
            deepcopy(self.visual_grid),
            deepcopy(self.attribute_grid),
            self.tee_pos,
            self.pin_pos,
        ))
        vg, ag, tee, pin = self._redo_stack.pop()
        self.visual_grid    = vg
        self.attribute_grid = ag
        self.tee_pos = tee
        self.pin_pos = pin
        self._tile_cache.clear()
        return True

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event, tilesets) -> bool:
        """Process a pygame event. Returns True if consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(event.pos):
                return False

            keys = pygame.key.get_pressed()

            if event.button == 4:
                self._zoom_at_cursor(self._zoom_index + 1, event.pos)
                return True
            if event.button == 5:
                self._zoom_at_cursor(self._zoom_index - 1, event.pos)
                return True
            if event.button == 2 or (event.button == 1 and keys[pygame.K_SPACE]):
                self._panning          = True
                self._pan_start_mouse  = event.pos
                self._pan_start_offset = (self._ox, self._oy)
                return True

            if event.button == 1:
                if self.ruler_mode and not self._set_mode and not keys[pygame.K_SPACE]:
                    wx, wy = self._screen_to_world(event.pos)
                    self._ruler_start    = (wx, wy)
                    self._ruler_end      = (wx, wy)
                    self._ruler_dragging = True
                    return True

                if self._set_mode:
                    tile = self._screen_to_tile(event.pos)
                    if tile:
                        self.push_undo()
                        if self._set_mode == "tee":
                            self.tee_pos = tile
                        else:
                            self.pin_pos = tile
                        self._set_mode = None
                    return True

                shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                if shift:
                    tile = self._screen_to_tile(event.pos)
                    if tile:
                        self._rect_start = tile
                        self._rect_end   = tile
                        self._rect_attr  = bool(keys[pygame.K_a])
                elif keys[pygame.K_f]:
                    tile = self._screen_to_tile(event.pos)
                    if tile:
                        self.push_undo()
                        self._flood_fill(tile[0], tile[1],
                                         use_attribute=keys[pygame.K_a])
                elif keys[pygame.K_e]:
                    self._painting              = True
                    self._erasing               = True
                    self._painting_attribute    = False
                    self._stroke_snapshot_taken = False
                    self._paint_at(event.pos)
                else:
                    self._painting               = True
                    self._painting_attribute     = keys[pygame.K_a]
                    self._erasing                = False
                    self._stroke_snapshot_taken  = False
                    self._paint_at(event.pos)
                return True

            if event.button == 3:
                self._eyedrop_at(event.pos)
                return True

        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.hovered_tile = self._screen_to_tile(event.pos)
            else:
                self.hovered_tile = None

            if self._ruler_dragging:
                wx, wy = self._screen_to_world(event.pos)
                self._ruler_end = (wx, wy)
                return True

            if self._panning:
                dx = event.pos[0] - self._pan_start_mouse[0]
                dy = event.pos[1] - self._pan_start_mouse[1]
                z  = self.zoom
                self._ox = self._pan_start_offset[0] - dx / z
                self._oy = self._pan_start_offset[1] - dy / z
                self._clamp_offset()
                return True

            if self._rect_start is not None:
                tile = self._screen_to_tile(event.pos)
                if tile:
                    self._rect_end = tile
                return True

            if self._painting and self.rect.collidepoint(event.pos):
                self._paint_at(event.pos)
                return True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._ruler_dragging = False
                if self._rect_start is not None and self._rect_end is not None:
                    self.push_undo()
                    self._fill_rect(self._rect_start, self._rect_end, self._rect_attr)
                self._rect_start            = None
                self._rect_end              = None
                self._painting              = False
                self._erasing               = False
                self._stroke_snapshot_taken = False
            if event.button in (1, 2):
                self._panning = False

        return False

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, tilesets: dict):
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)

        pygame.draw.rect(surface, (22, 22, 22), self.rect)

        z          = self.zoom
        display_px = max(1, int(BASE_TILE * z))

        if self.view_mode == "both":
            if (self._overlay_surf is None or
                    self._overlay_surf.get_width() != display_px):
                self._overlay_surf = pygame.Surface(
                    (display_px, display_px), pygame.SRCALPHA)

        col_min = max(0, int(self._ox // BASE_TILE))
        col_max = min(self.cols,
                      int((self._ox + self.rect.width  / z) // BASE_TILE) + 2)
        row_min = max(0, int(self._oy // BASE_TILE))
        row_max = min(self.rows,
                      int((self._oy + self.rect.height / z) // BASE_TILE) + 2)

        for row in range(row_min, row_max):
            for col in range(col_min, col_max):
                sx = self.rect.x + int((col * BASE_TILE - self._ox) * z)
                sy = self.rect.y + int((row * BASE_TILE - self._oy) * z)

                cell       = self.visual_grid[row][col]
                attr_char  = self.attribute_grid[row][col]
                attr_terr  = CHAR_TO_TERRAIN.get(attr_char, Terrain.ROUGH)
                attr_color = TERRAIN_PROPS[attr_terr]["color"]

                if self.view_mode == "visual":
                    self._draw_visual_tile(surface, cell, sx, sy, display_px, tilesets)
                elif self.view_mode == "attributes":
                    pygame.draw.rect(surface, attr_color,
                                     (sx, sy, display_px, display_px))
                else:
                    self._draw_visual_tile(surface, cell, sx, sy, display_px, tilesets)
                    self._overlay_surf.fill((*attr_color, OVERLAY_ALPHA))
                    surface.blit(self._overlay_surf, (sx, sy))

        # World boundary outline
        bx = self.rect.x + int(-self._ox * z)
        by = self.rect.y + int(-self._oy * z)
        bw = int(self.cols * BASE_TILE * z)
        bh = int(self.rows * BASE_TILE * z)
        pygame.draw.rect(surface, (70, 70, 70), (bx, by, bw, bh), 1)

        if self.show_grid and z >= 0.75:
            self._draw_grid(surface, z, col_min, col_max, row_min, row_max)

        # Hover highlight
        if self.hovered_tile is not None:
            hc, hr = self.hovered_tile
            hx = self.rect.x + int((hc * BASE_TILE - self._ox) * z)
            hy = self.rect.y + int((hr * BASE_TILE - self._oy) * z)
            hl = pygame.Surface((display_px, display_px), pygame.SRCALPHA)
            hl.fill((255, 255, 255, 50))
            surface.blit(hl, (hx, hy))

        # Rect-fill selection preview
        if self._rect_start is not None and self._rect_end is not None:
            self._draw_rect_selection(surface, z, display_px)

        # Tee / pin markers
        if self.tee_pos is not None:
            tc, tr = self.tee_pos
            if 0 <= tc < self.cols and 0 <= tr < self.rows:
                sx = self.rect.x + int((tc * BASE_TILE - self._ox) * z)
                sy = self.rect.y + int((tr * BASE_TILE - self._oy) * z)
                self._draw_marker(surface, sx, sy, display_px, (30, 190, 30), "T")

        if self.pin_pos is not None:
            pc, pr = self.pin_pos
            if 0 <= pc < self.cols and 0 <= pr < self.rows:
                sx = self.rect.x + int((pc * BASE_TILE - self._ox) * z)
                sy = self.rect.y + int((pr * BASE_TILE - self._oy) * z)
                self._draw_marker(surface, sx, sy, display_px, (210, 40, 40), "P")

        # Ruler overlay
        if self.ruler_mode and self._ruler_start and self._ruler_end:
            self._draw_ruler(surface, z)

        # Minimap
        self._draw_minimap(surface)

        surface.set_clip(old_clip)

    # ── Internal draw helpers ─────────────────────────────────────────────────

    def _draw_visual_tile(self, surface, cell, sx, sy, display_px, tilesets):
        if cell is not None:
            tile_surf = self._get_tile(cell, display_px, tilesets)
            if tile_surf is not None:
                surface.blit(tile_surf, (sx, sy))
            else:
                pygame.draw.rect(surface, (160, 40, 160),
                                 (sx, sy, display_px, display_px))
        else:
            pygame.draw.rect(surface, (35, 35, 35),
                             (sx, sy, display_px, display_px))

    def _draw_marker(self, surface, sx, sy, display_px, color, label):
        size = max(4, min(display_px, 16))
        mx   = sx + (display_px - size) // 2
        my   = sy + (display_px - size) // 2
        pygame.draw.rect(surface, color, (mx, my, size, size))
        pygame.draw.rect(surface, (0, 0, 0), (mx, my, size, size), 1)
        if size >= 10:
            if self._marker_font is None:
                self._marker_font = pygame.font.SysFont("monospace", 10, bold=True)
            ts = self._marker_font.render(label, True, (0, 0, 0))
            surface.blit(ts, (
                mx + (size - ts.get_width())  // 2,
                my + (size - ts.get_height()) // 2,
            ))

    def _draw_grid(self, surface, z, col_min, col_max, row_min, row_max):
        color = (55, 55, 55)
        for col in range(col_min, col_max + 1):
            x = self.rect.x + int((col * BASE_TILE - self._ox) * z)
            pygame.draw.line(surface, color, (x, self.rect.top), (x, self.rect.bottom))
        for row in range(row_min, row_max + 1):
            y = self.rect.y + int((row * BASE_TILE - self._oy) * z)
            pygame.draw.line(surface, color, (self.rect.left, y), (self.rect.right, y))

    def _draw_rect_selection(self, surface, z, display_px):
        c0, r0 = self._rect_start
        c1, r1 = self._rect_end
        col_min, col_max = min(c0, c1), max(c0, c1)
        row_min, row_max = min(r0, r1), max(r0, r1)

        sx = self.rect.x + int((col_min * BASE_TILE - self._ox) * z)
        sy = self.rect.y + int((row_min * BASE_TILE - self._oy) * z)
        sw = int((col_max - col_min + 1) * BASE_TILE * z)
        sh = int((row_max - row_min + 1) * BASE_TILE * z)

        color = (80, 140, 255) if not self._rect_attr else (255, 180, 60)
        overlay = pygame.Surface((max(1, sw), max(1, sh)), pygame.SRCALPHA)
        overlay.fill((*color, 45))
        surface.blit(overlay, (sx, sy))
        pygame.draw.rect(surface, color, (sx, sy, sw, sh), 2)

        if self._marker_font is None:
            self._marker_font = pygame.font.SysFont("monospace", 10, bold=True)
        w_count = col_max - col_min + 1
        h_count = row_max - row_min + 1
        lbl = self._marker_font.render(f"{w_count}×{h_count}", True, color)
        surface.blit(lbl, (sx + 3, sy + 3))

    def _draw_ruler(self, surface: pygame.Surface, z: float):
        """Draw the ruler line with distance label."""
        sx1 = self.rect.x + int((self._ruler_start[0] - self._ox) * z)
        sy1 = self.rect.y + int((self._ruler_start[1] - self._oy) * z)
        sx2 = self.rect.x + int((self._ruler_end[0]   - self._ox) * z)
        sy2 = self.rect.y + int((self._ruler_end[1]   - self._oy) * z)

        C_RULER = (255, 220, 0)
        pygame.draw.line(surface, C_RULER, (sx1, sy1), (sx2, sy2), 2)
        pygame.draw.circle(surface, C_RULER, (sx1, sy1), 5)
        pygame.draw.circle(surface, C_RULER, (sx2, sy2), 5)

        yds = self.ruler_yards
        if yds is not None and yds > 0.5:
            mx = (sx1 + sx2) // 2
            my = (sy1 + sy2) // 2
            if self._ruler_font is None:
                self._ruler_font = pygame.font.SysFont("monospace", 13, bold=True)
            label = f"{round(yds)} yds"
            ts    = self._ruler_font.render(label, True, C_RULER)
            bg    = pygame.Rect(mx - ts.get_width() // 2 - 4,
                                my - ts.get_height() // 2 - 2,
                                ts.get_width() + 8, ts.get_height() + 4)
            pygame.draw.rect(surface, (20, 20, 20), bg, border_radius=3)
            pygame.draw.rect(surface, C_RULER, bg, 1, border_radius=3)
            surface.blit(ts, (bg.x + 4, bg.y + 2))

    def _draw_minimap(self, surface: pygame.Surface):
        if self.rows == 0 or self.cols == 0:
            return

        scale  = min(_MINI_MAX_W / (self.cols * BASE_TILE),
                     _MINI_MAX_H / (self.rows * BASE_TILE))
        map_w  = max(1, int(self.cols * BASE_TILE * scale))
        map_h  = max(1, int(self.rows * BASE_TILE * scale))
        tile_w = max(1, int(BASE_TILE * scale))
        tile_h = max(1, int(BASE_TILE * scale))

        mini = pygame.Surface((map_w, map_h))
        mini.fill((20, 20, 20))

        for row in range(self.rows):
            for col in range(self.cols):
                char  = self.attribute_grid[row][col]
                terr  = CHAR_TO_TERRAIN.get(char, Terrain.ROUGH)
                color = TERRAIN_PROPS[terr]["color"]
                mx    = int(col * BASE_TILE * scale)
                my    = int(row * BASE_TILE * scale)
                pygame.draw.rect(mini, color, (mx, my, tile_w, tile_h))

        # Tee marker
        if self.tee_pos is not None:
            tc, tr = self.tee_pos
            mx = max(2, min(map_w - 3, int((tc * BASE_TILE + BASE_TILE // 2) * scale)))
            my = max(2, min(map_h - 3, int((tr * BASE_TILE + BASE_TILE // 2) * scale)))
            pygame.draw.circle(mini, (0, 0, 0),    (mx, my), 4)
            pygame.draw.circle(mini, (40, 220, 40), (mx, my), 3)

        # Pin marker
        if self.pin_pos is not None:
            pc, pr = self.pin_pos
            mx = max(2, min(map_w - 3, int((pc * BASE_TILE + BASE_TILE // 2) * scale)))
            my = max(2, min(map_h - 3, int((pr * BASE_TILE + BASE_TILE // 2) * scale)))
            pygame.draw.circle(mini, (0, 0, 0),    (mx, my), 4)
            pygame.draw.circle(mini, (220, 40, 40), (mx, my), 3)

        # Viewport box
        vp_x = max(0, int(self._ox * scale))
        vp_y = max(0, int(self._oy * scale))
        vp_w = max(2, min(map_w - vp_x, int((self.rect.width  / self.zoom) * scale)))
        vp_h = max(2, min(map_h - vp_y, int((self.rect.height / self.zoom) * scale)))
        pygame.draw.rect(mini, (200, 200, 200), (vp_x, vp_y, vp_w, vp_h), 1)

        dest_x = self.rect.right  - map_w - _MINI_MARGIN
        dest_y = self.rect.bottom - map_h - _MINI_MARGIN
        surface.blit(mini, (dest_x, dest_y))
        pygame.draw.rect(surface, (90, 90, 90),
                         pygame.Rect(dest_x - 1, dest_y - 1, map_w + 2, map_h + 2), 1)

    # ── Tile cache ────────────────────────────────────────────────────────────

    def _get_tile(self, cell, display_px, tilesets) -> pygame.Surface | None:
        tid, sc, sr = cell
        key = (tid, sc, sr, display_px)
        if key not in self._tile_cache:
            sheet = tilesets.get(tid)
            if sheet is None:
                return None
            src = pygame.Rect(sc * SOURCE_TILE, sr * SOURCE_TILE,
                              SOURCE_TILE, SOURCE_TILE)
            if src.right > sheet.get_width() or src.bottom > sheet.get_height():
                return None
            raw    = sheet.subsurface(src)
            scaled = pygame.transform.scale(raw, (display_px, display_px))
            self._tile_cache[key] = scaled.convert()
        return self._tile_cache[key]

    # ── Coordinate helpers ────────────────────────────────────────────────────

    def _screen_to_world(self, pos) -> tuple[float, float]:
        z = self.zoom
        return ((pos[0] - self.rect.x) / z + self._ox,
                (pos[1] - self.rect.y) / z + self._oy)

    def _screen_to_tile(self, pos) -> tuple[int, int] | None:
        z   = self.zoom
        wx  = (pos[0] - self.rect.x) / z + self._ox
        wy  = (pos[1] - self.rect.y) / z + self._oy
        col = int(wx // BASE_TILE)
        row = int(wy // BASE_TILE)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return (col, row)
        return None

    # ── Painting ──────────────────────────────────────────────────────────────

    def _paint_at(self, pos):
        tile = self._screen_to_tile(pos)
        if tile is None:
            return
        col, row = tile

        if not self._stroke_snapshot_taken:
            self.push_undo()
            self._stroke_snapshot_taken = True

        if self._erasing:
            self.visual_grid[row][col]    = None
            self.attribute_grid[row][col] = "R"
        elif self._painting_attribute:
            self.attribute_grid[row][col] = self.active_attribute.value
        else:
            if self.active_brush is not None:
                self.visual_grid[row][col] = self.active_brush
                if self.auto_derive_enabled:
                    tid, sc, sr = self.active_brush
                    terrain = _auto_derive(tid, sc, sr)
                    if terrain is not None:
                        self.attribute_grid[row][col] = terrain.value

    def _eyedrop_at(self, pos):
        tile = self._screen_to_tile(pos)
        if tile is None:
            return
        col, row = tile
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            char = self.attribute_grid[row][col]
            terrain = CHAR_TO_TERRAIN.get(char)
            if terrain:
                self.active_attribute = terrain
        else:
            self.active_brush = self.visual_grid[row][col]

    def _fill_rect(self, start: tuple, end: tuple, use_attribute: bool):
        c0, r0 = start
        c1, r1 = end
        col_min, col_max = min(c0, c1), max(c0, c1)
        row_min, row_max = min(r0, r1), max(r0, r1)
        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):
                if use_attribute:
                    self.attribute_grid[row][col] = self.active_attribute.value
                else:
                    if self.active_brush is not None:
                        self.visual_grid[row][col] = self.active_brush
                        if self.auto_derive_enabled:
                            tid, sc, sr = self.active_brush
                            terrain = _auto_derive(tid, sc, sr)
                            if terrain is not None:
                                self.attribute_grid[row][col] = terrain.value

    def _flood_fill(self, col: int, row: int, use_attribute: bool):
        if use_attribute:
            grid     = self.attribute_grid
            target   = grid[row][col]
            fill_val = self.active_attribute.value
        else:
            grid     = self.visual_grid
            target   = grid[row][col]
            fill_val = self.active_brush

        if fill_val is None or fill_val == target:
            return

        queue   = deque([(col, row)])
        visited = set()

        while queue:
            c, r = queue.popleft()
            if (c, r) in visited:
                continue
            if not (0 <= c < self.cols and 0 <= r < self.rows):
                continue
            if grid[r][c] != target:
                continue
            visited.add((c, r))
            grid[r][c] = fill_val
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if (nc, nr) not in visited:
                    queue.append((nc, nr))

    # ── Zoom helpers ──────────────────────────────────────────────────────────

    def _zoom_at_screen_centre(self, new_index: int):
        cx = self.rect.x + self.rect.width  // 2
        cy = self.rect.y + self.rect.height // 2
        self._zoom_at_cursor(new_index, (cx, cy))

    def _zoom_at_cursor(self, new_index: int, cursor_pos):
        new_index = max(0, min(len(ZOOM_LEVELS) - 1, new_index))
        if new_index == self._zoom_index:
            return
        old_z = self.zoom
        wx    = (cursor_pos[0] - self.rect.x) / old_z + self._ox
        wy    = (cursor_pos[1] - self.rect.y) / old_z + self._oy
        self._zoom_index = new_index
        new_z = self.zoom
        self._ox = wx - (cursor_pos[0] - self.rect.x) / new_z
        self._oy = wy - (cursor_pos[1] - self.rect.y) / new_z
        self._clamp_offset()

    def _clamp_offset(self):
        z         = self.zoom
        world_w   = self.cols * BASE_TILE
        world_h   = self.rows * BASE_TILE
        visible_w = self.rect.width  / z
        visible_h = self.rect.height / z
        self._ox  = max(-visible_w * 0.9, min(world_w - visible_w * 0.1, self._ox))
        self._oy  = max(-visible_h * 0.9, min(world_h - visible_h * 0.1, self._oy))

    def _center_on_world(self):
        z         = self.zoom
        world_w   = self.cols * BASE_TILE
        world_h   = self.rows * BASE_TILE
        visible_w = self.rect.width  / z
        visible_h = self.rect.height / z
        self._ox  = (world_w - visible_w) / 2.0
        self._oy  = (world_h - visible_h) / 2.0
