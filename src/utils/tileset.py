"""
TilesetManager — loads tileset PNGs from assets/tilemaps/ and extracts
individual tiles for use in the course renderer.

Terrain tilesets (Hills, Tilled_Dirt, Water) use 32×32 source tiles and are
always opaque.  Detail tilesets (RGBA PNGs with transparent backgrounds) are
tracked separately; when loaded they are kept as convert_alpha() surfaces so
the alpha channel is preserved for compositing.

Usage
─────
    from src.utils.tileset import TilesetManager
    mgr = TilesetManager()
    surf = mgr.get(terrain)          # returns a scaled terrain tile
    mgr.load_extra("Details", path, transparent=True)
"""

import os
import pygame
from src.golf.terrain import Terrain

# Source tile size in the terrain PNG sheets (Hills / Tilled_Dirt / Water)
SOURCE_TILE = 32

# Map: terrain → (sheet_filename_stem, col, row, brightness_delta)
_TILE_SPEC = {
    Terrain.FAIRWAY:    ("Hills",          4,  5,  0),
    Terrain.ROUGH:      ("Hills",          3,  5,  0),
    Terrain.DEEP_ROUGH: ("Hills",          3,  5, -42),
    Terrain.BUNKER:     ("Tilled_Dirt",    1,  5,  0),
    Terrain.WATER:      ("Water",          1,  0,  0),
    Terrain.GREEN:      ("Hills",          4,  5, +30),
    Terrain.TEE:        ("Hills",          4,  5, +12),
    # TREES uses a procedural tile — handled by CourseRenderer directly
}


class TilesetManager:
    """Loads tileset sheets once and caches scaled terrain tiles."""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._sheets:           dict[str, pygame.Surface] = {}
        self._tiles:            dict[Terrain, pygame.Surface] = {}
        self._transparent_ids:  set[str] = set()   # sheets loaded with alpha
        self._ready = False

    def load(self, assets_dir: str, tile_size: int = 16):
        """
        Load all terrain sheets and pre-extract terrain tiles.

        assets_dir : path to the directory containing the tileset PNGs
        tile_size  : target tile size in pixels (matches TILE_SIZE in renderer)
        """
        sheets_needed = {"Hills", "Tilled_Dirt", "Water"}
        for stem in sheets_needed:
            path = os.path.join(assets_dir, f"{stem}.png")
            if not os.path.exists(path):
                alt = os.path.join(assets_dir, f"{stem.replace('_', ' ')}.png")
                if os.path.exists(alt):
                    path = alt
            if os.path.exists(path):
                self._sheets[stem] = pygame.image.load(path).convert_alpha()

        for terrain, (stem, col, row, delta) in _TILE_SPEC.items():
            if stem not in self._sheets:
                continue
            surf = self._extract(stem, col, row, tile_size, transparent=False)
            if surf is not None:
                self._apply_brightness(surf, delta)
                self._tiles[terrain] = surf

        self._ready = True

    def load_extra(self, stem: str, path: str, transparent: bool = False) -> bool:
        """
        Load an additional sheet (e.g. a detail/RGBA tileset) by path.

        transparent=True preserves the alpha channel (convert_alpha instead of convert).
        Returns True on success.
        """
        if not os.path.exists(path):
            return False
        try:
            surf = pygame.image.load(path).convert_alpha()
            self._sheets[stem] = surf
            if transparent:
                self._transparent_ids.add(stem)
            return True
        except Exception:
            return False

    def is_transparent(self, stem: str) -> bool:
        """Return True if this sheet was loaded as a transparent/RGBA tileset."""
        return stem in self._transparent_ids

    # ── Tile access ───────────────────────────────────────────────────────────

    def get(self, terrain: Terrain) -> pygame.Surface | None:
        return self._tiles.get(terrain)

    def get_sheet(self, stem: str) -> pygame.Surface | None:
        return self._sheets.get(stem)

    def is_ready(self) -> bool:
        return self._ready and bool(self._tiles)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract(self, stem: str, col: int, row: int,
                 tile_size: int, transparent: bool = False) -> pygame.Surface | None:
        sheet = self._sheets.get(stem)
        if sheet is None:
            return None

        src_rect = pygame.Rect(col * SOURCE_TILE, row * SOURCE_TILE,
                               SOURCE_TILE, SOURCE_TILE)
        if (src_rect.right  > sheet.get_width() or
                src_rect.bottom > sheet.get_height()):
            return None

        raw    = pygame.Surface((SOURCE_TILE, SOURCE_TILE), pygame.SRCALPHA)
        raw.blit(sheet, (0, 0), area=src_rect)
        scaled = pygame.transform.scale(raw, (tile_size, tile_size))

        # Keep alpha for transparent detail sheets; drop it for opaque terrain tiles
        return scaled.convert_alpha() if transparent else scaled.convert()

    @staticmethod
    def _apply_brightness(surf: pygame.Surface, delta: int):
        if delta == 0:
            return
        v      = abs(delta)
        colour = (v, v, v)
        flag   = pygame.BLEND_RGB_ADD if delta > 0 else pygame.BLEND_RGB_SUB
        surf.fill(colour, special_flags=flag)
