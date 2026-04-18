"""
Hole — stores the layout of a single golf hole as a 2-D terrain grid.

Grid format
-----------
The grid is a list of strings, one per row (row 0 = top of the screen = near pin).
Each character maps to a Terrain via CHAR_TO_TERRAIN:
    X = Tee box       F = Fairway      R = Rough        D = Deep rough
    B = Bunker        W = Water        T = Trees/OOB    G = Green

Three layers
------------
  ground_layer  : list[list[(id,col,row)|None]]  — opaque base tiles
  detail_layer  : list[list[(id,col,row)|None]]  — transparent overlay sprites
  logic_layer   : list[str]                       — terrain codes (same as grid)

Scale: each tile represents 10 yards.
       tile_size pixels per tile is set in the renderer (default 16 px).

Positions are stored as (col, row) tile indices.
"""

from src.golf.terrain import Terrain, CHAR_TO_TERRAIN


class Hole:
    """A single golf hole."""

    def __init__(self, number, par, yardage, tee_pos, pin_pos, grid,
                 visual_grid=None, tilesets=None,
                 ground_layer=None, detail_layer=None):
        self.number   = number
        self.par      = par
        self.yardage  = yardage
        self.tee_pos  = tee_pos
        self.pin_pos  = pin_pos
        self.grid     = grid          # list[str] — terrain codes (logic layer)
        self.rows     = len(grid)
        self.cols     = len(grid[0]) if grid else 0
        self.tilesets = tilesets      # dict {id: pygame.Surface} or None

        # Three-layer model.
        # ground_layer / visual_grid are synonyms — prefer ground_layer going forward.
        self.ground_layer = ground_layer if ground_layer is not None else visual_grid
        self.detail_layer = detail_layer   # RGBA overlay tiles; None = no detail

        # Legacy alias kept for code that still reads hole.visual_grid
        self.visual_grid = self.ground_layer

    def get_terrain_at(self, col, row):
        """
        Return the Terrain enum for tile (col, row).
        Out-of-bounds positions are treated as TREES (unplayable).
        """
        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            return Terrain.TREES
        char = self.grid[row][col]
        return CHAR_TO_TERRAIN.get(char, Terrain.ROUGH)

    def get_terrain_at_pixel(self, px, py, tile_size):
        """Return terrain at a world-pixel position given the tile size."""
        col = int(px // tile_size)
        row = int(py // tile_size)
        return self.get_terrain_at(col, row)


# ─────────────────────────────────────────────────────────────────────────────
# Hole definitions
# ─────────────────────────────────────────────────────────────────────────────

def make_hole_1():
    """
    Hole 1 — Par 4, 310 yards, Greenfields Golf Club.

    A straightforward opening hole to learn the controls.
    The fairway runs dead straight from tee to green.
    Water guards the green left and right.
    Two bunkers flank the fairway at the approach.
    Two more bunkers sit mid-fairway to punish offline drives.

    Grid: 48 cols × 36 rows, each tile = 10 yards = 16 screen pixels.

    Tile positions
    ──────────────
    Tee centre : col 23, row 33   → world pixel (470, 670)
    Pin centre : col 23, row  3   → world pixel (470,  70)
    Fairway    : cols 18-27, rows 5-32
    Green      : cols 19-27, rows 2-5
    """

    rows, cols = 36, 48

    # Start with rough everywhere
    grid = [['R'] * cols for _ in range(rows)]

    # ── Borders: trees / out-of-bounds ──────────────────────────────────────
    for c in range(cols):
        grid[0][c]      = 'T'
        grid[1][c]      = 'T'
        grid[rows-1][c] = 'T'
    for r in range(rows):
        grid[r][0]      = 'T'
        grid[r][1]      = 'T'
        grid[r][cols-1] = 'T'
        grid[r][cols-2] = 'T'

    # ── Main fairway corridor ────────────────────────────────────────────────
    for r in range(5, 33):
        for c in range(18, 28):
            grid[r][c] = 'F'

    # ── Green ────────────────────────────────────────────────────────────────
    for r in range(2, 6):
        for c in range(18, 28):
            grid[r][c] = 'G'

    # ── Tee box ──────────────────────────────────────────────────────────────
    for r in range(33, 35):
        for c in range(20, 26):
            grid[r][c] = 'X'

    # ── Water hazard left (flanks approach to green) ─────────────────────────
    for r in range(2, 7):
        for c in range(2, 16):
            grid[r][c] = 'W'

    # ── Water hazard right ───────────────────────────────────────────────────
    for r in range(2, 7):
        for c in range(30, 46):
            grid[r][c] = 'W'

    # ── Bunkers flanking the approach (near green) ───────────────────────────
    for r in range(6, 9):
        for c in range(14, 18):     # left bunker
            grid[r][c] = 'B'
    for r in range(6, 9):
        for c in range(28, 32):     # right bunker
            grid[r][c] = 'B'

    # ── Mid-fairway bunker (left) — punishes a pulled drive ──────────────────
    for r in range(19, 22):
        for c in range(14, 18):
            grid[r][c] = 'B'

    # ── Mid-fairway bunker (right) — punishes a pushed drive ─────────────────
    for r in range(26, 29):
        for c in range(28, 32):
            grid[r][c] = 'B'

    return Hole(
        number   = 1,
        par      = 4,
        yardage  = 310,
        tee_pos  = (23, 33),
        pin_pos  = (23,  3),
        grid     = [''.join(row) for row in grid],
    )
