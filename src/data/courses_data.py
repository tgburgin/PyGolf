"""
Course data — Greenfields Golf Club, Par 72.

All holes share the same grid dimensions: 48 cols × 36 rows at 20 px/tile
= 960 × 720 world pixels, which exactly fills the course viewport.

Helper
──────
_make_hole(number, par, yardage, tee_pos, pin_pos, fairway_segs, features)

  tee_pos / pin_pos  : (col, row) tile indices
  fairway_segs       : list of (r_start, r_end, c_start, c_end) inclusive ranges
  features           : list of ('type', r_start, r_end, c_start, c_end)
                       types: 'bunker' 'water' 'trees' 'deep_rough'

The grid is built in this order so later layers override earlier ones:
  1. Rough base
  2. Tree/OOB borders
  3. Fairway segments
  4. Features (water, bunkers, trees, deep_rough)
  5. Green  (overrides everything near pin)
  6. Tee    (overrides everything near tee)

Par breakdown  (total 72):
  Par 3 × 4  →  holes 3, 7, 11, 15
  Par 4 × 10 →  holes 1, 4, 5, 8, 9, 10, 13, 14, 16, 18
  Par 5 × 4  →  holes 2, 6, 12, 17
"""

from src.course.course    import Course
from src.data._hole_factory import build_hole as _make_hole   # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# 18-hole definitions
# ─────────────────────────────────────────────────────────────────────────────

def _hole_1():
    """Par 4, 310 yds — The Opening.
    Straight, water guards the green left and right, two bunker pairs."""
    return _make_hole(
        1, 4, 310,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 18, 27)],
        features=[
            ('water',  2,  6,  2, 16),   # water left of green
            ('water',  2,  6, 30, 45),   # water right of green
            ('bunker', 6,  8, 14, 17),   # bunker left approach
            ('bunker', 6,  8, 28, 31),   # bunker right approach
            ('bunker',19, 21, 14, 17),   # bunker left mid
            ('bunker',26, 28, 28, 31),   # bunker right mid
        ],
    )


def _hole_2():
    """Par 5, 390 yds — The Long Straight.
    Wide fairway with two landing-zone bunker pairs to reward accuracy."""
    return _make_hole(
        2, 5, 390,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 15, 30)],   # wide fairway
        features=[
            ('bunker',14, 17, 11, 14),
            ('bunker',14, 17, 32, 35),
            ('bunker', 6,  9, 12, 14),
            ('bunker', 6,  9, 32, 34),
        ],
    )


def _hole_3():
    """Par 3, 175 yds — The Fort.
    Short hole, green ringed by bunkers. Accuracy over distance."""
    return _make_hole(
        3, 3, 175,
        tee_pos=(23, 27), pin_pos=(23, 6),
        fairway_segs=[(8, 26, 20, 26)],
        features=[
            ('bunker', 3,  9, 14, 19),   # bunker left
            ('bunker', 3,  9, 27, 32),   # bunker right
            ('bunker',10, 12, 20, 26),   # bunker front
        ],
    )


def _hole_4():
    """Par 4, 330 yds — The Corridor.
    Tight tree-lined fairway, deep rough either side punishes wayward shots."""
    return _make_hole(
        4, 4, 330,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 20, 26)],   # narrow
        features=[
            ('deep_rough', 5, 32, 17, 19),
            ('deep_rough', 5, 32, 27, 29),
            ('trees',      5, 32, 14, 16),
            ('trees',      5, 32, 30, 32),
            ('bunker',     6,  9, 21, 25),  # front-right bunker
        ],
    )


def _hole_5():
    """Par 4, 340 yds — The Water Crossing.
    A water hazard cuts across the full width of the fairway around 180 yds.
    Lay up short or carry it — your choice."""
    return _make_hole(
        5, 4, 340,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[
            ( 5, 16, 18, 27),   # upper fairway (past the water)
            (20, 32, 18, 27),   # lower fairway (before the water)
        ],
        features=[
            ('water', 17, 19, 10, 37),   # water crossing full width
            ('bunker', 7,  9, 14, 17),
            ('bunker', 7,  9, 28, 31),
        ],
    )


def _hole_6():
    """Par 5, 380 yds — The Dogleg Left.
    Drive up the right side, then work a draw around the corner."""
    return _make_hole(
        6, 5, 380,
        tee_pos=(34, 33), pin_pos=(10, 3),
        fairway_segs=[
            (18, 32, 29, 38),   # lower vertical (tee side)
            ( 5, 20,  7, 32),   # upper left (pin side)
        ],
        features=[
            ('bunker', 16, 21, 25, 29),   # corner bunker
            ('bunker',  6,  9,  4,  6),   # bunker left of green
            ('bunker',  6,  9, 26, 30),   # bunker right of pin approach
            ('water',   2,  6,  2,  7),   # water left of green
        ],
    )


def _hole_7():
    """Par 3, 160 yds — The Island Green.
    Water surrounds the green. Pure carry required — no fairway to land on."""
    return _make_hole(
        7, 3, 160,
        tee_pos=(23, 24), pin_pos=(23, 7),
        fairway_segs=[],   # no fairway — all carry
        features=[
            ('water',  2, 22,  2, 17),   # water left
            ('water',  2, 22, 29, 45),   # water right
            ('water',  2, 11, 18, 28),   # water above green
            # Green (rows 4-10, cols 19-27) will override this water
        ],
    )


def _hole_8():
    """Par 4, 345 yds — The Gauntlet.
    Bunkers line both sides of the fairway all the way to the green."""
    return _make_hole(
        8, 4, 345,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 19, 27)],
        features=[
            ('bunker',  6, 10, 14, 18),
            ('bunker',  6, 10, 28, 32),
            ('bunker', 12, 16, 14, 18),
            ('bunker', 12, 16, 28, 32),
            ('bunker', 19, 23, 14, 18),
            ('bunker', 19, 23, 28, 32),
            ('bunker', 25, 29, 14, 18),
            ('bunker', 25, 29, 28, 32),
        ],
    )


def _hole_9():
    """Par 4, 360 yds — Turn For Home.
    Water hugs the left of the approach; deep rough right. Respect both."""
    return _make_hole(
        9, 4, 360,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 19, 27)],
        features=[
            ('water',       4, 14,  2, 16),
            ('bunker',      5,  9, 28, 33),
            ('deep_rough',  5, 32, 16, 18),
            ('deep_rough',  5, 32, 28, 30),
        ],
    )


def _hole_10():
    """Par 4, 325 yds — Start of the Back Nine.
    Water runs the full length on the right. Anything right means trouble."""
    return _make_hole(
        10, 4, 325,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 18, 26)],
        features=[
            ('water',   5, 32, 30, 45),   # water right throughout
            ('bunker',  6,  9, 13, 17),   # bunker left approach
        ],
    )


def _hole_11():
    """Par 3, 145 yds — The Short Iron.
    Compact hole, but bunkers front, left and right demand a precise ball flight."""
    return _make_hole(
        11, 3, 145,
        tee_pos=(23, 24), pin_pos=(23, 8),
        fairway_segs=[(9, 23, 20, 26)],
        features=[
            ('bunker',  5, 11, 15, 19),
            ('bunker',  5, 11, 27, 31),
            ('bunker',  3,  7, 20, 26),   # front bunker
        ],
    )


def _hole_12():
    """Par 5, 400 yds — Split Decision.
    A central bunker divides the landing zone. Go left, go right — but not through it."""
    return _make_hole(
        12, 5, 400,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 14, 32)],   # very wide
        features=[
            ('bunker', 17, 23, 20, 26),   # central hazard
            ('bunker',  6,  9, 11, 13),   # left of green
            ('bunker',  6,  9, 33, 35),   # right of green
        ],
    )


def _hole_13():
    """Par 4, 340 yds — The Right Hook.
    Classic dogleg right: drive straight, then a long approach bending right."""
    return _make_hole(
        13, 4, 340,
        tee_pos=(10, 33), pin_pos=(36, 3),
        fairway_segs=[
            (18, 32,  6, 15),   # lower vertical (tee side)
            ( 5, 20, 12, 38),   # upper horizontal (bends right to pin)
        ],
        features=[
            ('bunker', 16, 22, 16, 20),   # corner bunker
            ('bunker',  6,  9, 33, 37),   # bunker near green
            ('trees',  18, 32, 16, 20),   # trees at the inside of the dogleg
        ],
    )


def _hole_14():
    """Par 4, 335 yds — The Straight Shooter.
    Deep rough squeezes in close; only the fairway is safe."""
    return _make_hole(
        14, 4, 335,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 20, 26)],   # narrow
        features=[
            ('deep_rough', 5, 32, 16, 19),
            ('deep_rough', 5, 32, 27, 30),
            ('bunker',     6,  9, 14, 19),
            ('bunker',     6,  9, 27, 32),
        ],
    )


def _hole_15():
    """Par 3, 190 yds — The Long Iron.
    Longest par 3 on the course. Large green, bunker guards the left entrance."""
    return _make_hole(
        15, 3, 190,
        tee_pos=(23, 30), pin_pos=(23, 6),
        fairway_segs=[(8, 29, 18, 28)],   # wider corridor
        features=[
            ('bunker',  3,  9, 13, 17),   # bunker left
            ('bunker',  3,  9, 29, 33),   # bunker right
        ],
    )


def _hole_16():
    """Par 4, 355 yds — The Ditch.
    Water guards the left side of the green. Miss right and face a tough bunker lie."""
    return _make_hole(
        16, 4, 355,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 18, 27)],
        features=[
            ('water',   3, 10,  2, 15),   # water left of green
            ('bunker',  6,  9, 28, 33),   # bunker right
            ('bunker', 16, 19, 14, 17),   # mid-fairway left bunker
        ],
    )


def _hole_17():
    """Par 5, 405 yds — The Diagonal.
    Tee is far left, pin is far right. The fairway sweeps in a wide arc."""
    return _make_hole(
        17, 5, 405,
        tee_pos=(8, 33), pin_pos=(38, 3),
        fairway_segs=[
            (22, 32,  5, 16),   # lower-left (from tee)
            ( 8, 24, 12, 30),   # diagonal mid-section
            ( 5, 10, 26, 42),   # upper-right (to pin)
        ],
        features=[
            ('bunker', 19, 24, 17, 22),   # mid corner bunker
            ('bunker',  3,  9, 39, 43),   # bunker near pin
            ('water',   2,  8,  2,  5),   # water far left
        ],
    )


def _hole_18():
    """Par 4, 375 yds — The Finisher.
    Water both sides of the green approach. A dramatic closing hole."""
    return _make_hole(
        18, 4, 375,
        tee_pos=(23, 33), pin_pos=(23, 3),
        fairway_segs=[(5, 32, 18, 27)],
        features=[
            ('water',   2,  8,  2, 15),   # water left of green
            ('water',   2,  8, 31, 45),   # water right of green
            ('bunker',  9, 13, 14, 17),   # bunker left approach
            ('bunker',  9, 13, 28, 31),   # bunker right approach
            ('bunker', 20, 23, 14, 17),   # bunker left mid-fairway
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public factory
# ─────────────────────────────────────────────────────────────────────────────

def make_greenfields_course():
    """
    Return a fully-populated Course object for Greenfields Golf Club.

    Par 72  (4×par3, 10×par4, 4×par5)
    """
    holes = [
        _hole_1(),   # par 4
        _hole_2(),   # par 5
        _hole_3(),   # par 3
        _hole_4(),   # par 4
        _hole_5(),   # par 4
        _hole_6(),   # par 5
        _hole_7(),   # par 3
        _hole_8(),   # par 4
        _hole_9(),   # par 4
        _hole_10(),  # par 4
        _hole_11(),  # par 3
        _hole_12(),  # par 5
        _hole_13(),  # par 4
        _hole_14(),  # par 4
        _hole_15(),  # par 3
        _hole_16(),  # par 4
        _hole_17(),  # par 5
        _hole_18(),  # par 4
    ]
    return Course("Greenfields Golf Club", holes)
