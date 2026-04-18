"""
tileset_panel.py — tileset palette for the course editor.

Draws the left-side panel showing tiles from the currently active tileset
PNG.  The user clicks a tile to select it as the active paint brush.

Public interface
────────────────
  draw(surface, tilesets, active_brush)
  handle_event(event, tilesets) → bool
  add_tileset(id, sheet)
  selected_tile   — None or (id, src_col, src_row), read and cleared by EditorApp
"""

import pygame

SOURCE_TILE  = 16   # source tile size in PNG sheets
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
        self.selected_tile = None          # (id, sc, sr) — set on click, read externally

        self._btn_prev = pygame.Rect(0, 0, 0, 0)
        self._btn_next = pygame.Rect(0, 0, 0, 0)

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
        self._scroll_y   = 0
        self.selected_tile = None

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event, tilesets) -> bool:
        """Process pygame event. Returns True if consumed."""
        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self._hovered_tile = self._pos_to_tile(event.pos, tilesets)
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
                    self._navigate(-1)
                    return True
                if self._btn_next.collidepoint(event.pos):
                    self._navigate(+1)
                    return True
                tile = self._pos_to_tile(event.pos, tilesets)
                if tile is not None:
                    sc, sr = tile
                    self.selected_tile = (self._current_id, sc, sr)
                    return True

        return False

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surface, tilesets, active_brush=None):
        """Render the panel. active_brush is (id, sc, sr) or None for highlight."""
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)

        pygame.draw.rect(surface, (42, 42, 42), self.rect)
        pygame.draw.line(surface, (70, 70, 70),
                         (self.rect.right - 1, self.rect.top),
                         (self.rect.right - 1, self.rect.bottom))

        self._draw_header(surface)

        if self._current_id and self._current_id in tilesets:
            self._draw_tiles(surface, tilesets, active_brush)
        else:
            msg = self._font_sm.render("No tileset loaded.", True, (110, 110, 110))
            mx  = self.rect.x + (self.rect.width - msg.get_width()) // 2
            surface.blit(msg, (mx, self.rect.y + HEADER_H + 20))

        surface.set_clip(old_clip)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _draw_header(self, surface):
        hx, hy, hw = self.rect.x, self.rect.y, self.rect.width
        pygame.draw.rect(surface, (52, 52, 52), (hx, hy, hw, HEADER_H))
        pygame.draw.line(surface, (70, 70, 70),
                         (hx, hy + HEADER_H - 1), (hx + hw, hy + HEADER_H - 1))

        name  = self._current_id or "No tileset"
        label = self._font.render(name, True, (200, 200, 200))
        surface.blit(label, (hx + MARGIN_X, hy + 8))

        # Hover coordinates
        if self._hovered_tile is not None and self._current_id:
            sc, sr = self._hovered_tile
            coord = self._font_sm.render(
                f"{self._current_id}:{sc}:{sr}", True, (160, 200, 160))
            surface.blit(coord, (hx + MARGIN_X, hy + 24))

        if len(self._tile_order) > 1:
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
            idx = (f"{self._tile_order.index(self._current_id) + 1}"
                   f"/{len(self._tile_order)}")
            s = self._font_sm.render(idx, True, (150, 150, 150))
            surface.blit(s, (hx + (hw - s.get_width()) // 2, by + 2))
        else:
            self._btn_prev = pygame.Rect(0, 0, 0, 0)
            self._btn_next = pygame.Rect(0, 0, 0, 0)

    def _draw_tiles(self, surface, tilesets, active_brush):
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
                if self._hovered_tile == (sc, sr):
                    hl = pygame.Surface((DISPLAY_TILE, DISPLAY_TILE), pygame.SRCALPHA)
                    hl.fill((255, 255, 255, 60))
                    surface.blit(hl, (tx, ty))

                # Selection outline
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
            self._tile_cache[key] = scaled.convert()
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

    def _navigate(self, direction: int):
        if not self._tile_order or self._current_id not in self._tile_order:
            return
        i = (self._tile_order.index(self._current_id) + direction) % len(self._tile_order)
        self._current_id = self._tile_order[i]
        self._scroll_y   = 0
