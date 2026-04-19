"""
_hole_factory.build_hole — shared declarative hole builder.

Both `courses_data.py` and `courses_library.py` used to carry near-identical
copies of this helper. It lives here so balance tweaks (e.g. widening every
green, shifting the OOB border) only need to land in one place.

Grid is built in this order so later layers override earlier ones:
  1. Rough base
  2. Tree / OOB borders (2-tile perimeter)
  3. Fairway segments
  4. Features (water, bunkers, trees, deep_rough)
  5. Green   (overrides features around pin)
  6. Tee box (overrides features around tee)
"""

from src.course.hole import Hole

_DEFAULT_ROWS = 36
_DEFAULT_COLS = 48

_CHAR = {
    'bunker':     'B',
    'water':      'W',
    'trees':      'T',
    'deep_rough': 'D',
}


def build_hole(number: int, par: int, yardage: int,
               tee_pos: tuple[int, int], pin_pos: tuple[int, int],
               fairway_segs: list | None = None,
               features: list | None = None,
               rows: int = _DEFAULT_ROWS,
               cols: int = _DEFAULT_COLS) -> Hole:
    """Build a Hole from declarative specs. See module docstring for layer order.

    `fairway_segs` items: (r1, r2, c1, c2) inclusive tile ranges.
    `features`     items: ('type', r1, r2, c1, c2) where type is one of
                           bunker / water / trees / deep_rough.
    """
    tc, tr = tee_pos
    pc, pr = pin_pos

    grid = [['R'] * cols for _ in range(rows)]

    # Tree / OOB borders: 2-tile perimeter
    for c in range(cols):
        grid[0][c] = grid[1][c] = grid[rows - 1][c] = 'T'
    for r in range(rows):
        grid[r][0] = grid[r][1] = grid[r][cols - 1] = grid[r][cols - 2] = 'T'

    for r1, r2, c1, c2 in (fairway_segs or []):
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if 2 <= r < rows - 1 and 2 <= c < cols - 2:
                    grid[r][c] = 'F'

    for ftype, r1, r2, c1, c2 in (features or []):
        ch = _CHAR[ftype]
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if 0 <= r < rows and 0 <= c < cols:
                    grid[r][c] = ch

    # Green: 3 rows × 9 cols centred on pin
    for r in range(max(2, pr - 1), min(rows - 1, pr + 3)):
        for c in range(max(2, pc - 4), min(cols - 2, pc + 5)):
            grid[r][c] = 'G'

    # Tee box: 2 rows × 6 cols centred on tee
    for r in range(max(2, tr - 1), min(rows - 1, tr + 1)):
        for c in range(max(2, tc - 3), min(cols - 2, tc + 3)):
            grid[r][c] = 'X'

    return Hole(
        number  = number,
        par     = par,
        yardage = yardage,
        tee_pos = tee_pos,
        pin_pos = pin_pos,
        grid    = [''.join(row) for row in grid],
    )
