"""
flags.py — Draw simplified national flags as coloured pixel rectangles.

Usage:
    from src.ui.flags import draw_flag, FLAG_W, FLAG_H
    draw_flag(surface, "American", x, y)           # default 32×20
    draw_flag(surface, "French",   x, y, 48, 30)  # custom size

Designs are intentionally simplified — no text, minimal detail — so they
read clearly at small pixel-art sizes.  A thin 1px border is always drawn.
"""

import pygame

FLAG_W = 32
FLAG_H = 20


# ── Palette ───────────────────────────────────────────────────────────────────

_RED   = (204,   0,   0)
_WHITE = (255, 255, 255)
_BLUE  = ( 10,  60, 160)
_GOLD  = (255, 215,   0)
_BLACK = (  0,   0,   0)
_GREEN = (  0, 130,  65)

# Per-country colours that differ from the palette above
_US_BLUE  = ( 60,  59, 110)
_US_RED   = (178,  34,  52)
_SP_RED   = (198,  11,  30)
_SP_GOLD  = (250, 174,   0)
_DE_RED   = (221,   0,   0)
_DE_GOLD  = (255, 204,   0)
_SE_BLUE  = (  0, 106, 167)
_SE_GOLD  = (254, 204,   0)
_NO_RED   = (198,  12,  48)
_NO_BLUE  = (  0,  32, 128)
_DK_RED   = (198,  12,  48)
_FR_BLUE  = (  0,  35, 149)
_FR_RED   = (237,  41,  57)
_IT_GREEN = (  0, 146,  70)
_IT_RED   = (206,  43,  55)
_ZA_GREEN = (  0, 122,  77)
_ZA_GOLD  = (255, 184,  28)
_ZA_RED   = (222,  56,  49)
_ZA_BLUE  = (  0,  20, 137)
_ZA_BLACK = (  0,   0,   0)
_KO_RED   = (205,  46,  58)
_KO_BLUE  = (  0,  71, 160)
_AR_LBLUE = (116, 172, 223)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hstripes(s, r, colors):
    n  = len(colors)
    sh = r.height / n
    for i, c in enumerate(colors):
        top = r.y + round(i * sh)
        bot = r.y + round((i + 1) * sh)
        pygame.draw.rect(s, c, (r.x, top, r.width, bot - top))


def _vstripes(s, r, colors):
    n  = len(colors)
    sw = r.width / n
    for i, c in enumerate(colors):
        lft = r.x + round(i * sw)
        rgt = r.x + round((i + 1) * sw)
        pygame.draw.rect(s, c, (lft, r.y, rgt - lft, r.height))


def _cross(s, r, bg, fg, t=None):
    """Centered horizontal + vertical cross."""
    pygame.draw.rect(s, bg, r)
    t = t or max(2, r.height // 5)
    cx, cy = r.centerx, r.centery
    pygame.draw.rect(s, fg, (r.x, cy - t // 2, r.width, t))
    pygame.draw.rect(s, fg, (cx - t // 2, r.y, t, r.height))


def _nordic(s, r, bg, fg, inner=None):
    """Nordic off-centre cross (vertical bar at 1/3 from left)."""
    pygame.draw.rect(s, bg, r)
    vx = r.x + r.width // 3
    t  = max(2, r.height // 5)
    cy = r.centery
    pygame.draw.rect(s, fg, (r.x, cy - t // 2, r.width, t))
    pygame.draw.rect(s, fg, (vx - t // 2, r.y, t, r.height))
    if inner:
        ti = max(1, t - 2)
        pygame.draw.rect(s, inner, (r.x, cy - ti // 2, r.width, ti))
        pygame.draw.rect(s, inner, (vx - ti // 2, r.y, ti, r.height))


def _saltire(s, r, bg, fg, t=None):
    """Diagonal X cross (St Andrew's / Saltire)."""
    pygame.draw.rect(s, bg, r)
    t = t or max(2, r.height // 5)
    pygame.draw.line(s, fg, (r.x, r.y), (r.right, r.bottom), t)
    pygame.draw.line(s, fg, (r.right, r.y), (r.x, r.bottom), t)


def _union_jack(s, r):
    """Simplified Union Jack: blue field, white+red cross and diagonals."""
    pygame.draw.rect(s, _BLUE, r)
    # White saltire
    _saltire(s, r, _BLUE, _WHITE, t=max(3, r.height // 4))
    # Red saltire (thin, centred on white)
    _saltire(s, r, _BLUE, _RED,   t=max(1, r.height // 8))
    # White cross over everything
    cx, cy = r.centerx, r.centery
    cw = max(3, r.height // 4)
    cr = max(1, r.height // 8)
    pygame.draw.rect(s, _WHITE, (r.x, cy - cw // 2, r.width, cw))
    pygame.draw.rect(s, _WHITE, (cx - cw // 2, r.y, cw, r.height))
    pygame.draw.rect(s, _RED,   (r.x, cy - cr // 2, r.width, cr))
    pygame.draw.rect(s, _RED,   (cx - cr // 2, r.y, cr, r.height))


# ── Per-nationality draw functions ────────────────────────────────────────────

def _american(s, r):
    stripe_count = 5
    sh = r.height / stripe_count
    for i in range(stripe_count):
        c = _US_RED if i % 2 == 0 else _WHITE
        top = r.y + round(i * sh)
        bot = r.y + round((i + 1) * sh)
        pygame.draw.rect(s, c, (r.x, top, r.width, bot - top))
    # Blue canton (top-left third)
    canton_w = r.width * 2 // 5
    canton_h = r.height * 3 // 5
    pygame.draw.rect(s, _US_BLUE, (r.x, r.y, canton_w, canton_h))


def _english(s, r):
    _cross(s, r, _WHITE, _RED)


def _scottish(s, r):
    _saltire(s, r, _BLUE, _WHITE, t=max(2, r.height // 4))


def _irish(s, r):
    _vstripes(s, r, [_GREEN, _WHITE, (255, 130, 0)])


def _welsh(s, r):
    # Green bottom, white top; red dragon simplified to a red oval
    mid = r.y + r.height // 2
    pygame.draw.rect(s, _WHITE, (r.x, r.y, r.width, r.height // 2))
    pygame.draw.rect(s, _GREEN, (r.x, mid, r.width, r.height - r.height // 2))
    # Simple red dragon body suggestion
    pygame.draw.ellipse(s, _RED, (r.x + r.width // 4, r.y + r.height // 4,
                                   r.width // 2, r.height // 2))


def _australian(s, r):
    pygame.draw.rect(s, _BLUE, r)
    # Union Jack (top-left quadrant)
    uj = pygame.Rect(r.x, r.y, r.width // 2, r.height // 2)
    _union_jack(s, uj)
    # Commonwealth star (bottom-left, white dot)
    pygame.draw.circle(s, _WHITE, (r.x + r.width // 4, r.y + r.height * 3 // 4), 2)
    # Southern Cross (4 small stars, right side)
    for sx, sy in [(r.x + r.width * 3 // 4, r.y + r.height // 4),
                   (r.x + r.width * 7 // 8, r.y + r.height // 2),
                   (r.x + r.width * 3 // 4, r.y + r.height * 3 // 4),
                   (r.x + r.width * 5 // 8, r.y + r.height // 2)]:
        pygame.draw.circle(s, _WHITE, (sx, sy), 1)


def _south_african(s, r):
    # Green horizontal stripe through middle, flanked by yellow+black edges
    _hstripes(s, r, [_RED, _WHITE, _ZA_BLUE])
    # Green chevron / horizontal band through center
    cy = r.centery
    bh = max(2, r.height // 5)
    pygame.draw.rect(s, _ZA_GREEN, (r.x, cy - bh, r.width, bh * 2))
    # Black left triangle suggestion
    pts = [(r.x, r.y), (r.x, r.bottom), (r.x + r.width // 4, cy)]
    pygame.draw.polygon(s, _BLACK, pts)
    # Yellow border on triangle
    pygame.draw.line(s, _ZA_GOLD, (r.x, r.y), (r.x + r.width // 4, cy), 1)
    pygame.draw.line(s, _ZA_GOLD, (r.x, r.bottom - 1), (r.x + r.width // 4, cy), 1)


def _spanish(s, r):
    _hstripes(s, r, [_SP_RED, _SP_GOLD, _SP_GOLD, _SP_RED])


def _german(s, r):
    _hstripes(s, r, [_BLACK, _DE_RED, _DE_GOLD])


def _swedish(s, r):
    _nordic(s, r, _SE_BLUE, _SE_GOLD)


def _canadian(s, r):
    _vstripes(s, r, [_RED, _WHITE, _RED])
    # Maple leaf — simplified red cross in white section
    cx, cy = r.centerx, r.centery
    pygame.draw.rect(s, _RED, (cx - 1, cy - r.height // 3, 2, r.height * 2 // 3))
    pygame.draw.rect(s, _RED, (cx - r.width // 8, cy - r.height // 6,
                                r.width // 4, r.height // 6))


def _japanese(s, r):
    pygame.draw.rect(s, _WHITE, r)
    rx = max(3, min(r.width, r.height) * 3 // 8)
    pygame.draw.circle(s, (188, 0, 45), r.center, rx)


def _south_korean(s, r):
    pygame.draw.rect(s, _WHITE, r)
    cx, cy = r.centerx, r.centery
    radius = max(3, min(r.width, r.height) // 4)
    # Taeguk (simplified: red arc top, blue arc bottom)
    pygame.draw.circle(s, _KO_RED,  (cx, cy), radius)
    pygame.draw.circle(s, _KO_BLUE, (cx, cy + radius // 2), radius // 2)
    pygame.draw.circle(s, _KO_RED,  (cx, cy - radius // 2), radius // 2)
    # Simplified trigrams (black lines left and right)
    bx1, bx2 = r.x + 2, r.right - 4
    for dy in (-r.height // 4, 0, r.height // 4):
        pygame.draw.line(s, _BLACK, (bx1, cy + dy), (bx1 + 3, cy + dy), 1)
        pygame.draw.line(s, _BLACK, (bx2, cy + dy), (bx2 + 3, cy + dy), 1)


def _argentine(s, r):
    _hstripes(s, r, [_AR_LBLUE, _WHITE, _AR_LBLUE])
    # Sun — yellow circle in centre
    pygame.draw.circle(s, _SP_GOLD, r.center, max(2, r.height // 6))


def _french(s, r):
    _vstripes(s, r, [_FR_BLUE, _WHITE, _FR_RED])


def _italian(s, r):
    _vstripes(s, r, [_IT_GREEN, _WHITE, _IT_RED])


def _danish(s, r):
    _nordic(s, r, _DK_RED, _WHITE)


def _norwegian(s, r):
    _nordic(s, r, _NO_RED, _WHITE, inner=_NO_BLUE)


def _new_zealander(s, r):
    pygame.draw.rect(s, _BLUE, r)
    uj = pygame.Rect(r.x, r.y, r.width // 2, r.height // 2)
    _union_jack(s, uj)
    # 4 red stars (Southern Cross)
    for sx, sy in [(r.x + r.width * 3 // 4, r.y + r.height // 4),
                   (r.x + r.width * 7 // 8, r.y + r.height // 2),
                   (r.x + r.width * 3 // 4, r.y + r.height * 3 // 4),
                   (r.x + r.width * 5 // 8, r.y + r.height // 2)]:
        pygame.draw.circle(s, _RED, (sx, sy), 2)
        pygame.draw.circle(s, _WHITE, (sx, sy), 1)


def _zimbabwean(s, r):
    # 7 stripes: green/yellow/red/black/red/yellow/green
    _hstripes(s, r, [_ZA_GREEN, _ZA_GOLD, _ZA_RED, _BLACK,
                     _ZA_RED, _ZA_GOLD, _ZA_GREEN])
    # White triangle on left
    pts = [(r.x, r.y), (r.x, r.bottom), (r.x + r.width // 3, r.centery)]
    pygame.draw.polygon(s, _WHITE, pts)
    # Yellow star (dot)
    pygame.draw.circle(s, _ZA_GOLD, (r.x + r.width // 6, r.centery), 2)


def _unknown(s, r):
    pygame.draw.rect(s, (60, 60, 60), r)
    pygame.draw.line(s, (120, 120, 120), r.topleft, r.bottomright, 1)
    pygame.draw.line(s, (120, 120, 120), r.topright, r.bottomleft, 1)


# ── Dispatch table ────────────────────────────────────────────────────────────

_FLAG_FUNCS = {
    "American":      _american,
    "English":       _english,
    "Scottish":      _scottish,
    "Irish":         _irish,
    "Welsh":         _welsh,
    "Australian":    _australian,
    "South African": _south_african,
    "Spanish":       _spanish,
    "German":        _german,
    "Swedish":       _swedish,
    "Canadian":      _canadian,
    "Japanese":      _japanese,
    "South Korean":  _south_korean,
    "Argentine":     _argentine,
    "French":        _french,
    "Italian":       _italian,
    "Danish":        _danish,
    "Norwegian":     _norwegian,
    "New Zealander": _new_zealander,
    "Zimbabwean":    _zimbabwean,
}


# ── Public API ────────────────────────────────────────────────────────────────

def draw_flag(surface: pygame.Surface, nationality: str,
              x: int, y: int, w: int = FLAG_W, h: int = FLAG_H):
    """Draw a simplified flag for *nationality* at (x, y) with size (w, h)."""
    r = pygame.Rect(x, y, w, h)
    fn = _FLAG_FUNCS.get(nationality, _unknown)
    fn(surface, r)
    pygame.draw.rect(surface, (10, 10, 10), r, 1)
