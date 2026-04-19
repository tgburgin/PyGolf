"""
tileset_panel.py — tileset palette for the course editor.

Draws the left-side panel showing tiles from the currently active tileset
PNG.  The user clicks a tile to select it as the active paint brush.

Single-tile mode  : left-click  → selected_tile = (id, sc, sr)
Multi-tile stamp  : left-drag   → selected_stamp = list[list[(id,sc,sr)]]
  (stamp is a 2-D list; [0][0] is top-left.  Only available on the Detail layer.)

Public interface
────────────────
  draw(surface, tilesets, active_brush, active_layer, transparent_tilesets)
  handle_event(event, tilesets, active_layer, transparent_tilesets) → bool
  add_tileset(id, sheet)
  selected_tile   — None or (id, src_col, src_row), read and cleared by EditorApp
  selected_stamp  — None or list[list[(id,sc,sr)]], read and cleared by EditorApp
"""

import pygame

from src.constants import SOURCE_TILE   # shared with game loader/renderer

DISPLAY_TILE = 32   # displayed tile size in the panel
TILE_GAP     = 1    # 1-px gap between tiles
MARGIN_X     = 6    # horizontal inner margin
HEADER_H     = 56   # height reserved for header (label + prev/next buttons)
SCROLL_STEP  = 40   # pixels per scroll-wheel click


class TilesetPanel:
    """Left-side tileset palette — click a tile to select it as the paint brush."""

    def __init__(self, rect):
        self.rect = rect
        self._current_id: str | None = None
        self._tile_order: list[str]  = []
        self._scroll_y   = 0
        self._hovered_tile = None          # (sc, sr) under cursor
        self.selected_tile  = None         # (id, sc, sr) — set on click, read externally
        self.selected_stamp = None         # list[list[(id,sc,sr)]] — set on drag, read externally

        self._btn_prev = pygame.Rect(0, 0, 0, 0)
        self._btn_next = pygame.Rect(0, 0, 0, 0)

        # Drag-select for multi-tile stamp
        self._drag_start: tuple | None = None   # (sc, sr) where drag began
        self._drag_end:   tuple | None = None   # (sc, sr) current drag end
        self._dragging    = False

        # Scaled tile cache: (id, sc, sr) → Surface at DISPLAY_TILE
        self._tile_cache: dict = {}

        self._font      = pygame.font.SysFont("monospace", 13)
        self._font_sm   = pygame.font.SysFont("monospace", 11)

    # ── Public interface ──────────────────────────────────────────────────────

    def add_tileset(self, tileset_id: str, sheet: pygame.Surface):
        """Register a tileset and make it active."""
        if tileset_id not in self._tile_order:
            self._tile_order.append(tileset_id)
        self._current_id = tileset_id
        self._scroll_y   = 0

    def clear(self):
        self._current_id = None
        self._tile_order.clear()
        self._tile_cache.clear()
        self._scroll_y      = 0
        self.selected_tile  = None
        self.selected_stamp = None
        self._drag_start    = None
        self._drag_end      = None
        self._dragging      = False

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event, tilesets,
                     active_layer: str = "ground",
                     transparent_tilesets: set | None = None) -> bool:
        """Process pygame event. Returns True if consumed."""
        if active_layer == "logic":
            return False   # Logic layer has no tile palette

        visible = self._visible_ids(active_layer, transparent_tilesets)
        if not visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self._hovered_tile = self._pos_to_tile(event.pos, tilesets)
                if self._dragging and self._hovered_tile is not None:
                    self._drag_end = self._hovered_tile
            else:
                self._hovered_tile = None
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(event.pos):
                return False
            if event.button == 4:
                self._scroll_y = max(0, self._scroll_y - SCROLL_STEP)
                return True
            if event.button == 5:
                self._scroll_y += SCROLL_STEP
                return True
            if event.button == 1:
                if self._btn_prev.collidepoint(event.pos):
                    self._navigate(-1, visible)
                    return True
                if self._btn_next.collidepoint(event.pos):
                    self._navigate(+1, visible)
                    return True
                tile = self._pos_to_tile(event.pos, tilesets)
                if tile is not None:
                    self._dragging   = True
                    self._drag_start = tile
                    self._drag_end   = tile
                    return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                if self._drag_start is not None and self._drag_end is not None:
                    sc0, sr0 = self._drag_start
                    sc1, sr1 = self._drag_end
                    c_min, c_max = min(sc0, sc1), max(sc0, sc1)
                    r_min, r_max = min(sr0, sr1), max(sr0, sr1)
                    if c_min == c_max and r_min == r_max:
                        # Single tile — use selected_tile path
                        self.selected_tile  = (self._current_id, c_min, r_min)
                        self.selected_stamp = None
                    else:
                        # Multi-tile stamp
                        stamp = [
                            [(self._current_id, sc, sr)
                             for sc in range(c_min, c_max + 1)]
                            for sr in range(r_min, r_max + 1)
                        ]
                        self.selected_stamp = stamp
                        self.selected_tile  = None
                    self._drag_start = None
                    self._drag_end   = None
                return True

        return False

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surface, tilesets, active_brush=None,
             active_layer: str = "ground",
             transparent_tilesets: set | None = None):
        """Render the panel. active_brush is (id, sc, sr) or None for highlight."""
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)

        pygame.draw.rect(surface, (42, 42, 42), self.rect)
        pygame.draw.line(surface, (70, 70, 70),
                         (self.rect.right - 1, self.rect.top),
                         (self.rect.right - 1, self.rect.bottom))

        if active_layer == "logic":
            self._draw_logic_message(surface)
            surface.set_clip(old_clip)
            return

        visible = self._visible_ids(active_layer, transparent_tilesets)

        # If current tileset is not in the visible list, auto-switch
        if self._current_id not in visible and visible:
            self._current_id = visible[0]
            self._scroll_y   = 0

        self._draw_header(surface, visible)

        if self._current_id and self._current_id in tilesets:
            self._draw_tiles(surface, tilesets, active_brush, active_layer)
        else:
            if active_layer == "detail" and not visible:
                lines = ["No transparent", "tilesets loaded.", "Import an RGBA PNG."]
            else:
                lines = ["No tileset loaded."]
            for i, line in enumerate(lines):
                msg = self._font_sm.render(line, True, (110, 110, 110))
                mx  = self.rect.x + (self.rect.width - msg.get_width()) // 2
                surface.blit(msg, (mx, self.rect.y + HEADER_H + 20 + i * 16))

        surface.set_clip(old_clip)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _visible_ids(self, active_layer: str,
                     transparent_tilesets: set | None) -> list[str]:
        """Return the subset of _tile_order valid for the given layer."""
        transparent = transparent_tilesets or set()
        if active_layer == "detail":
            return [tid for tid in self._tile_order if tid in transparent]
        else:  # ground — all tilesets are available
            return list(self._tile_order)

    def _draw_logic_message(self, surface):
        """Show a placeholder message when the logic layer is active."""
        pygame.draw.rect(surface, (42, 42, 42), self.rect)
        pygame.draw.line(surface, (70, 70, 70),
                         (self.rect.right - 1, self.rect.top),
                         (self.rect.right - 1, self.rect.bottom))
        lines  = ["Logic Layer", "", "Use the Attribute", "panel below to", "paint terrain codes."]
        colors = [(220, 160, 60), (0, 0, 0), (150, 150, 150), (150, 150, 150), (150, 150, 150)]
        y = self.rect.y + HEADER_H + 20
        for line, color in zip(lines, colors):
            if not line:
                y += 8
                continue
            msg = self._font_sm.render(line, True, color)
            mx  = self.rect.x + (self.rect.width - msg.get_width()) // 2
            surface.blit(msg, (mx, y))
            y += 16

    def _draw_header(self, surface, visible: list[str] | None = None):
        hx, hy, hw = self.rect.x, self.rect.y, self.rect.width
        pygame.draw.rect(surface, (52, 52, 52), (hx, hy, hw, HEADER_H))
        pygame.draw.line(surface, (70, 70, 70),
                         (hx, hy + HEADER_H - 1), (hx + hw, hy + HEADER_H - 1))

        name  = self._current_id or "No tileset"
        label = self._font.render(name, True, (200, 200, 200))
        surface.blit(label, (hx + MARGIN_X, hy + 8))

        # Hover / stamp-size coordinates
        if self._dragging and self._drag_start and self._drag_end:
            sc0, sr0 = self._drag_start
            sc1, sr1 = self._drag_end
            w = abs(sc1 - sc0) + 1
            h = abs(sr1 - sr0) + 1
            coord = self._font_sm.render(f"Stamp: {w}x{h}", True, (80, 220, 140))
            surface.blit(coord, (hx + MARGIN_X, hy + 24))
        elif self._hovered_tile is not None and self._current_id:
            sc, sr = self._hovered_tile
            coord = self._font_sm.render(
                f"{self._current_id}:{sc}:{sr}", True, (160, 200, 160))
            surface.blit(coord, (hx + MARGIN_X, hy + 24))

        ids = visible if visible is not None else self._tile_order
        if len(ids) > 1:
            bw, bh = 22, 18
            by = hy + 30
            self._btn_prev = pygame.Rect(hx + MARGIN_X, by, bw, bh)
            self._btn_next = pygame.Rect(hx + hw - MARGIN_X - bw, by, bw, bh)
            for btn, txt in ((self._btn_prev, "<"), (self._btn_next, ">")):
                pygame.draw.rect(surface, (62, 62, 62), btn)
                pygame.draw.rect(surface, (90, 90, 90), btn, 1)
                t = self._font_sm.render(txt, True, (200, 200, 200))
                surface.blit(t, (btn.x + (bw - t.get_width()) // 2,
                                 btn.y + (bh - t.get_height()) // 2))
            pos = ids.index(self._current_id) + 1 if self._current_id in ids else 0
            idx = f"{pos}/{len(ids)}"
            s = self._font_sm.render(idx, True, (150, 150, 150))
            surface.blit(s, (hx + (hw - s.get_width()) // 2, by + 2))
        else:
            self._btn_prev = pygame.Rect(0, 0, 0, 0)
            self._btn_next = pygame.Rect(0, 0, 0, 0)

    def _draw_tiles(self, surface, tilesets, active_brush, active_layer="ground"):
        sheet      = tilesets[self._current_id]
        sheet_cols = sheet.get_width()  // SOURCE_TILE
        sheet_rows = sheet.get_height() // SOURCE_TILE

        step          = DISPLAY_TILE + TILE_GAP
        tiles_per_row = max(1, (self.rect.width - MARGIN_X * 2) // step)
        grid_top      = self.rect.y + HEADER_H

        # Clamp scroll
        total_rows = (sheet_cols * sheet_rows + tiles_per_row - 1) // tiles_per_row
        max_scroll = max(0, total_rows * step - (self.rect.height - HEADER_H - 4))
        self._scroll_y = max(0, min(max_scroll, self._scroll_y))

        tile_clip = pygame.Rect(self.rect.x, grid_top,
                                self.rect.width, self.rect.height - HEADER_H)
        surface.set_clip(tile_clip)

        # Determine drag selection bounds for highlight
        drag_set: set[tuple[int, int]] = set()
        if self._dragging and self._drag_start and self._drag_end:
            sc0, sr0 = self._drag_start
            sc1, sr1 = self._drag_end
            for r in range(min(sr0, sr1), max(sr0, sr1) + 1):
                for c in range(min(sc0, sc1), max(sc0, sc1) + 1):
                    drag_set.add((c, r))

        for sr in range(sheet_rows):
            for sc in range(sheet_cols):
                idx       = sr * sheet_cols + sc
                tile_col  = idx % tiles_per_row
                tile_row  = idx // tiles_per_row
                tx = self.rect.x + MARGIN_X + tile_col * step
                ty = grid_top + tile_row * step - self._scroll_y

                if ty + DISPLAY_TILE < grid_top or ty > self.rect.bottom:
                    continue

                tile_surf = self._get_tile(self._current_id, sc, sr, sheet)
                if tile_surf is None:
                    continue
                surface.blit(tile_surf, (tx, ty))

                # Hover highlight
                if self._hovered_tile == (sc, sr) and not self._dragging:
                    hl = pygame.Surface((DISPLAY_TILE, DISPLAY_TILE), pygame.SRCALPHA)
                    hl.fill((255, 255, 255, 60))
                    surface.blit(hl, (tx, ty))

                # Drag-select highlight
                if (sc, sr) in drag_set:
                    hl = pygame.Surface((DISPLAY_TILE, DISPLAY_TILE), pygame.SRCALPHA)
                    hl.fill((80, 220, 140, 80))
                    surface.blit(hl, (tx, ty))

                # Single-tile selection outline
                if (active_brush is not None and
                        active_brush == (self._current_id, sc, sr)):
                    pygame.draw.rect(surface, (80, 160, 255),
                                     (tx - 1, ty - 1, DISPLAY_TILE + 2, DISPLAY_TILE + 2), 2)

        surface.set_clip(self.rect)

    def _get_tile(self, tid, sc, sr, sheet) -> pygame.Surface | None:
        key = (tid, sc, sr)
        if key not in self._tile_cache:
            src = pygame.Rect(sc * SOURCE_TILE, sr * SOURCE_TILE,
                              SOURCE_TILE, SOURCE_TILE)
            if src.right > sheet.get_width() or src.bottom > sheet.get_height():
                return None
            raw    = sheet.subsurface(src)
            scaled = pygame.transform.scale(raw, (DISPLAY_TILE, DISPLAY_TILE))
            # Preserve alpha for RGBA sheets (detail tilesets)
            self._tile_cache[key] = (scaled.convert_alpha()
                                     if sheet.get_flags() & pygame.SRCALPHA
                                     else scaled.convert())
        return self._tile_cache[key]

    def _pos_to_tile(self, pos, tilesets):
        """Map screen position to (sc, sr) in the current sheet, or None."""
        if self._current_id is None or self._current_id not in tilesets:
            return None
        sheet      = tilesets[self._current_id]
        sheet_cols = sheet.get_width()  // SOURCE_TILE
        sheet_rows = sheet.get_height() // SOURCE_TILE

        step          = DISPLAY_TILE + TILE_GAP
        tiles_per_row = max(1, (self.rect.width - MARGIN_X * 2) // step)
        grid_top      = self.rect.y + HEADER_H

        rel_x = pos[0] - (self.rect.x + MARGIN_X)
        rel_y = pos[1] - grid_top + self._scroll_y

        if rel_x < 0 or rel_y < 0:
            return None
        if rel_x % step >= DISPLAY_TILE or rel_y % step >= DISPLAY_TILE:
            return None   # gap between tiles

        tile_col = int(rel_x // step)
        tile_row = int(rel_y // step)
        if tile_col >= tiles_per_row:
            return None

        idx = tile_row * tiles_per_row + tile_col
        sc  = idx % sheet_cols
        sr  = idx // sheet_cols
        if sc >= sheet_cols or sr >= sheet_rows:
            return None
        return (sc, sr)

    def _navigate(self, direction: int, visible: list[str] | None = None):
        ids = visible if visible else self._tile_order
        if not ids or self._current_id not in ids:
            return
        i = (ids.index(self._current_id) + direction) % len(ids)
        self._current_id = ids[i]
        self._scroll_y   = 0
