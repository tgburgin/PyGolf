"""
CourseRenderer — draws the tile-based course map.

Three-layer render pipeline
────────────────────────────
  1. Ground layer  — opaque base tiles (fairway, rough, bunker, water, etc.)
  2. Detail layer  — RGBA transparent overlay tiles (trees, rocks, fences, etc.)
  3. Animated elements — flag wave drawn each frame on top

Terrain tiles are sourced from the PNG tilesets in assets/tilemaps/:
  Fairway / Green / Tee / Rough / Deep Rough → Hills.png  (grass tiles)
  Bunker                                      → Tilled_Dirt.png (sand tiles)
  Water                                       → Water.png
  Trees                                       → procedural (dark canopies)
  Detail objects                              → RGBA detail tilesets

If asset files are missing the renderer falls back to procedurally-
generated textures so the game always runs without assets.

Public interface
────────────────
  draw(surface, camera_x, camera_y, viewport_rect)
  draw_minimap(surface, dest_rect, ball_world_pos)
  get_pin_world_pos() / get_tee_world_pos() / world_size()
"""

import math
import os
import random
import pygame

from src.golf.terrain import Terrain, TERRAIN_PROPS
from src.utils.tileset import TilesetManager

TILE_SIZE = 16

# Must match tools/editor/canvas.py SOURCE_TILE so visual-layer extraction aligns
_SOURCE_TILE = 16

_ASSETS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..",
    "assets", "tilemaps",
)


# ─────────────────────────────────────────────────────────────────────────────
# Procedural fallback textures
# ─────────────────────────────────────────────────────────────────────────────

def _make_procedural_tile(terrain, tile_size, seed):
    ts  = tile_size
    rng = random.Random(seed)
    surf = pygame.Surface((ts, ts))

    if terrain == Terrain.FAIRWAY:
        _stripe(surf, ts, light=(82, 162, 78), dark=(68, 140, 64), width=8)
    elif terrain == Terrain.TEE:
        _stripe(surf, ts, light=(118, 215, 108), dark=(100, 192, 90), width=8)
    elif terrain == Terrain.GREEN:
        _stripe(surf, ts, light=(130, 232, 118), dark=(112, 208, 100), width=8)
    elif terrain == Terrain.ROUGH:
        _noisy_fill(surf, ts, rng, base=(44, 112, 42), spread=18)
        _grass_blades(surf, ts, rng, color=(62, 138, 58), count=5)
    elif terrain == Terrain.DEEP_ROUGH:
        _noisy_fill(surf, ts, rng, base=(26, 78, 26), spread=12)
        _grass_blades(surf, ts, rng, color=(38, 100, 36), count=9)
    elif terrain == Terrain.BUNKER:
        _bunker(surf, ts, rng)
    elif terrain == Terrain.WATER:
        _water(surf, ts, rng)
    elif terrain == Terrain.TREES:
        _trees(surf, ts, rng)
    else:
        surf.fill(TERRAIN_PROPS[terrain]['color'])

    return surf


def _stripe(surf, ts, light, dark, width):
    for x in range(ts):
        color = light if (x // width) % 2 == 0 else dark
        for y in range(ts):
            surf.set_at((x, y), color)


def _noisy_fill(surf, ts, rng, base, spread):
    for y in range(ts):
        for x in range(ts):
            v = rng.randint(-spread, spread)
            c = tuple(max(0, min(255, base[i] + v)) for i in range(3))
            surf.set_at((x, y), c)


def _grass_blades(surf, ts, rng, color, count):
    for _ in range(count):
        bx = rng.randint(1, ts - 2)
        by = rng.randint(3, ts - 1)
        h  = rng.randint(2, 4)
        lean = rng.randint(-1, 1)
        pygame.draw.line(surf, color, (bx, by), (bx + lean, by - h), 1)


def _bunker(surf, ts, rng):
    base = (212, 197, 146)
    for y in range(ts):
        for x in range(ts):
            v = rng.randint(-24, 24)
            c = tuple(max(150, min(245, base[i] + v)) for i in range(3))
            surf.set_at((x, y), c)
    for ry in range(4, ts, 5):
        pygame.draw.line(surf, (192, 176, 124), (1, ry),     (ts - 2, ry),     1)
        pygame.draw.line(surf, (228, 214, 162), (1, ry + 1), (ts - 2, ry + 1), 1)
    pygame.draw.rect(surf, (178, 162, 112), (0, 0, ts, ts), 1)


def _water(surf, ts, rng):
    base = (45, 100, 195)
    surf.fill(base)
    for ry in range(0, ts, 4):
        pygame.draw.line(surf, (70, 130, 218), (0, ry),     (ts, ry),     1)
        pygame.draw.line(surf, (30,  82, 168), (0, ry + 2), (ts, ry + 2), 1)
    for _ in range(3):
        sx = rng.randint(2, ts - 3)
        sy = rng.randint(2, ts - 3)
        surf.set_at((sx, sy),         (210, 232, 255))
        surf.set_at((sx + 1, sy),     (170, 205, 248))
        surf.set_at((sx,     sy + 1), (170, 205, 248))


def _trees(surf, ts, rng):
    surf.fill((10, 44, 10))
    n = rng.randint(1, 2)
    for _ in range(n):
        cx = rng.randint(ts // 4, 3 * ts // 4)
        cy = rng.randint(ts // 4, 3 * ts // 4)
        r  = rng.randint(5, 8)
        pygame.draw.circle(surf, (16,  60, 16), (cx, cy), r)
        pygame.draw.circle(surf, (26,  84, 22), (cx, cy), max(1, r - 2))
        pygame.draw.circle(surf, (44, 112, 38), (cx - 1, cy - 2), max(1, r - 4))


# ─────────────────────────────────────────────────────────────────────────────
# Tile builder — tileset first, procedural fallback
# ─────────────────────────────────────────────────────────────────────────────

def _make_tile(terrain, tile_size, seed, tileset: TilesetManager):
    if terrain == Terrain.TREES:
        return _make_procedural_tile(terrain, tile_size, seed)

    tile = tileset.get(terrain) if tileset.is_ready() else None

    if tile is not None:
        rng   = random.Random(seed)
        noise = rng.randint(-6, 6)
        result = tile.copy()
        if noise != 0:
            v    = abs(noise)
            flag = pygame.BLEND_RGB_ADD if noise > 0 else pygame.BLEND_RGB_SUB
            result.fill((v, v, v), special_flags=flag)
        return result

    return _make_procedural_tile(terrain, tile_size, seed)


# ─────────────────────────────────────────────────────────────────────────────
# Renderer class
# ─────────────────────────────────────────────────────────────────────────────

class CourseRenderer:
    """Pre-renders and draws the course tile map using a three-layer pipeline."""

    def __init__(self, hole):
        self.hole      = hole
        self.tile_size = TILE_SIZE

        self._tileset = TilesetManager.instance()
        if not self._tileset.is_ready():
            project_root = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", ".."))
            assets_dir = os.path.join(project_root, "assets", "tilemaps")
            self._tileset.load(assets_dir, tile_size=TILE_SIZE)

        self._course_surface = None
        self._visual_cache: dict = {}
        self._build_course_surface()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_course_surface(self):
        """
        Bake ground + detail layers into a single cached surface.

        Ground tiles are drawn opaque; detail tiles are blitted on top
        with full alpha compositing so transparent pixels show the ground.
        """
        width  = self.hole.cols * self.tile_size
        height = self.hole.rows * self.tile_size
        ts     = self.tile_size

        # ── Ground layer (opaque) ────────────────────────────────────────────
        ground_surf = pygame.Surface((width, height))
        has_ground  = (self.hole.ground_layer is not None
                       and self.hole.tilesets is not None)

        for row in range(self.hole.rows):
            for col in range(self.hole.cols):
                terrain = self.hole.get_terrain_at(col, row)
                seed    = col * 10007 + row * 37 + hash(terrain.value)

                tile = None
                if (has_ground
                        and row < len(self.hole.ground_layer)
                        and col < len(self.hole.ground_layer[row])):
                    cell = self.hole.ground_layer[row][col]
                    if cell is not None:
                        tile = self._get_visual_tile(cell, ts, alpha=False)

                if tile is None:
                    tile = _make_tile(terrain, ts, seed, self._tileset)

                ground_surf.blit(tile, (col * ts, row * ts))

        # ── Detail layer (RGBA transparent overlay) ──────────────────────────
        has_detail = (self.hole.detail_layer is not None
                      and self.hole.tilesets is not None)

        if has_detail:
            detail_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            detail_surf.fill((0, 0, 0, 0))

            for row in range(self.hole.rows):
                for col in range(self.hole.cols):
                    if row >= len(self.hole.detail_layer):
                        continue
                    cell = self.hole.detail_layer[row][col]
                    if cell is None:
                        continue
                    tile = self._get_visual_tile(cell, ts, alpha=True)
                    if tile is not None:
                        detail_surf.blit(tile, (col * ts, row * ts))

            ground_surf.blit(detail_surf, (0, 0))

        self._course_surface = ground_surf
        self._draw_border_shadows()
        self._draw_pin()
        self._draw_tee_marker()

    def _draw_border_shadows(self):
        """1-px dark edge on bunker/water tiles where they border different terrain."""
        ts        = self.tile_size
        shadow    = (0, 0, 0)
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for row in range(self.hole.rows):
            for col in range(self.hole.cols):
                terrain = self.hole.get_terrain_at(col, row)
                if terrain not in (Terrain.BUNKER, Terrain.WATER):
                    continue
                tx, ty = col * ts, row * ts
                for dr, dc in neighbors:
                    nbr = self.hole.get_terrain_at(col + dc, row + dr)
                    if nbr == terrain:
                        continue
                    if dr == -1:
                        pygame.draw.line(self._course_surface, shadow,
                                         (tx, ty), (tx + ts - 1, ty))
                    elif dr == 1:
                        pygame.draw.line(self._course_surface, shadow,
                                         (tx, ty + ts - 1), (tx + ts - 1, ty + ts - 1))
                    elif dc == -1:
                        pygame.draw.line(self._course_surface, shadow,
                                         (tx, ty), (tx, ty + ts - 1))
                    elif dc == 1:
                        pygame.draw.line(self._course_surface, shadow,
                                         (tx + ts - 1, ty), (tx + ts - 1, ty + ts - 1))

    def _draw_pin(self):
        col, row = self.hole.pin_pos
        cx = col * self.tile_size + self.tile_size // 2
        cy = row * self.tile_size + self.tile_size // 2

        pygame.draw.circle(self._course_surface, (255, 255, 255), (cx, cy), 7)
        pygame.draw.circle(self._course_surface, (0,   0,   0),   (cx, cy), 6)
        pygame.draw.line(self._course_surface, (220, 220, 220),
                         (cx, cy - 2), (cx, cy - 22), 2)

    def _draw_tee_marker(self):
        col, row = self.hole.tee_pos
        cx = col * self.tile_size + self.tile_size // 2
        cy = row * self.tile_size + self.tile_size // 2
        for ox in (-8, 8):
            pygame.draw.circle(self._course_surface, (255, 255, 255), (cx + ox, cy), 3)
            pygame.draw.circle(self._course_surface, (140, 180, 140), (cx + ox, cy), 3, 1)

    def _get_visual_tile(self, cell, display_px, alpha=False) -> pygame.Surface | None:
        """Extract and cache a tile from the hole's loaded tileset surfaces."""
        tid, sc, sr = cell
        sheet = self.hole.tilesets.get(tid)
        if sheet is None:
            return None
        key = (tid, sc, sr, display_px, alpha)
        if key not in self._visual_cache:
            src = pygame.Rect(sc * _SOURCE_TILE, sr * _SOURCE_TILE,
                              _SOURCE_TILE, _SOURCE_TILE)
            if src.right > sheet.get_width() or src.bottom > sheet.get_height():
                self._visual_cache[key] = None
            else:
                raw = sheet.subsurface(src)
                if display_px != _SOURCE_TILE:
                    scaled = pygame.transform.scale(raw, (display_px, display_px))
                else:
                    scaled = raw.copy()
                self._visual_cache[key] = (
                    scaled.convert_alpha() if alpha else scaled.convert()
                )
        return self._visual_cache[key]

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface, camera_x, camera_y, viewport_rect):
        source_area = pygame.Rect(
            int(camera_x), int(camera_y),
            viewport_rect.width, viewport_rect.height,
        )
        surface.blit(self._course_surface,
                     (viewport_rect.x, viewport_rect.y),
                     area=source_area)

    def draw_minimap(self, surface, dest_rect, ball_world_pos):
        ts   = self.tile_size
        cols = self.hole.cols
        rows = self.hole.rows

        scale = min(dest_rect.width  / (cols * ts),
                    dest_rect.height / (rows * ts))
        map_w = int(cols * ts * scale)
        map_h = int(rows * ts * scale)

        mini = pygame.Surface((map_w, map_h))

        mtw = max(1, int(ts * scale))
        mth = max(1, int(ts * scale))
        for row in range(rows):
            for col in range(cols):
                terrain = self.hole.get_terrain_at(col, row)
                color   = TERRAIN_PROPS[terrain]['color']
                mx = int(col * ts * scale)
                my = int(row * ts * scale)
                pygame.draw.rect(mini, color, (mx, my, mtw, mth))

        pc, pr  = self.hole.pin_pos
        pin_mx  = int((pc * ts + ts // 2) * scale)
        pin_my  = int((pr * ts + ts // 2) * scale)
        pygame.draw.circle(mini, (0,   0,   0),   (pin_mx, pin_my), 4)
        pygame.draw.circle(mini, (255, 255, 255), (pin_mx, pin_my), 3)
        pygame.draw.circle(mini, (210,  35,  35), (pin_mx, pin_my), 2)

        bx, by  = ball_world_pos
        ball_mx = int(bx * scale)
        ball_my = int(by * scale)
        ball_mx = max(2, min(map_w - 3, ball_mx))
        ball_my = max(2, min(map_h - 3, ball_my))
        pygame.draw.circle(mini, (0,   0,   0),   (ball_mx, ball_my), 4)
        pygame.draw.circle(mini, (255, 255, 255), (ball_mx, ball_my), 3)

        ox = dest_rect.x + (dest_rect.width  - map_w) // 2
        oy = dest_rect.y + (dest_rect.height - map_h) // 2
        surface.blit(mini, (ox, oy))
        pygame.draw.rect(surface, (90, 120, 90),
                         pygame.Rect(ox - 1, oy - 1, map_w + 2, map_h + 2), 1)

    def draw_animated_elements(self, surface, camera_x: float,
                               camera_y: float, elapsed: float) -> None:
        """Draw time-varying elements (animated flag) over the static course."""
        col, row = self.hole.pin_pos
        ts = self.tile_size
        wcx = col * ts + ts // 2
        wcy = row * ts + ts // 2
        scx = int(wcx - camera_x)
        scy = int(wcy - camera_y)

        wave     = math.sin(elapsed * 3.8) * 3.5
        wave2    = math.sin(elapsed * 3.8 + 1.2) * 2.0
        stick_top = (scx, scy - 22)
        flag_pts  = [
            stick_top,
            (scx + 13 + int(wave),  scy - 17 + int(wave2)),
            (scx +  2 + int(wave2), scy - 12),
        ]
        pygame.draw.polygon(surface, (210, 35, 35), flag_pts)
        pygame.draw.polygon(surface, (240, 60, 60), flag_pts, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def world_to_screen(self, world_x, world_y, camera_x, camera_y,
                        viewport_x=0, viewport_y=0):
        return (int(world_x - camera_x + viewport_x),
                int(world_y - camera_y + viewport_y))

    def get_pin_world_pos(self):
        col, row = self.hole.pin_pos
        return (col * self.tile_size + self.tile_size // 2,
                row * self.tile_size + self.tile_size // 2)

    def get_tee_world_pos(self):
        col, row = self.hole.tee_pos
        return (col * self.tile_size + self.tile_size // 2,
                row * self.tile_size + self.tile_size // 2)

    def world_size(self):
        return (self.hole.cols * self.tile_size,
                self.hole.rows * self.tile_size)
