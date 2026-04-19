"""
ui_skin.py — Centralised UI drawing helpers.

Drop a sprite sheet at assets/ui/ui_sheet.png to enable custom graphics.
If the sheet is absent every function falls back to pygame.draw primitives
so the game always renders without any assets.

Sprite sheet layout (SLICE = 6 px corners, so each 9-slice block is 18×18 px):
  Row 0  — panel
  Row 1  — button (normal)
  Row 2  — button (hover)
  Row 3  — button (disabled)
  Row 4  — button (active / selected tab)
  Row 5  — button (play / confirm — green accent)

Each row is one 9-slice block: 3×SLICE wide, 3×SLICE tall.
Total sheet minimum size: 18 × 108 px.  Add more rows as needed.
"""

import os
import pygame

# ── Sheet config ──────────────────────────────────────────────────────────────

_SHEET_PATH = os.path.join("assets", "ui", "ui_sheet.png")
SLICE = 6          # corner/edge size in pixels on the source sheet
_BLOCK = SLICE * 3  # one 9-slice block height = 18 px

# Row indices on the sheet
_ROW_PANEL    = 0
_ROW_BTN      = 1
_ROW_BTN_HOV  = 2
_ROW_BTN_DIS  = 3
_ROW_BTN_ACT  = 4
_ROW_BTN_PLAY = 5

# ── Fallback colours (match career_hub defaults) ──────────────────────────────

_C_PANEL    = ( 18,  28,  18)
_C_BORDER   = ( 55,  90,  55)
_C_BTN      = ( 28,  75,  28)
_C_BTN_HOV  = ( 50, 120,  50)
_C_BTN_DIS  = ( 60,  52,  42)
_C_BTN_ACT  = ( 20,  55,  20)
_C_BTN_PLAY = ( 20,  88,  20)
_C_BTN_PLAY_H = ( 40, 140,  40)
_C_GREEN    = ( 55,  90,  55)
_C_RADIUS   = 6

# ── Internal state ────────────────────────────────────────────────────────────

_sheet: pygame.Surface | None = None
_loaded = False   # True once we have tried to load (even if it failed)


def _get_sheet() -> pygame.Surface | None:
    global _sheet, _loaded
    if _loaded:
        return _sheet
    _loaded = True
    if os.path.exists(_SHEET_PATH):
        try:
            _sheet = pygame.image.load(_SHEET_PATH).convert_alpha()
        except Exception as e:
            print(f"[ui_skin] Could not load {_SHEET_PATH}: {e}")
    return _sheet


def reload():
    """Force a reload of the sprite sheet (call after changing the PNG)."""
    global _sheet, _loaded
    _sheet  = None
    _loaded = False


# ── 9-slice renderer ──────────────────────────────────────────────────────────

def _nine_slice(surface: pygame.Surface, sheet: pygame.Surface,
                row: int, dest: pygame.Rect):
    """Blit a 9-slice block from *sheet* row *row* onto *surface* at *dest*."""
    s = SLICE
    sy = row * _BLOCK
    sw = sheet.get_width()

    # Source rects (col × row on sheet)
    def src(cx, cy, cw, ch):
        return pygame.Rect(cx, sy + cy, cw, ch)

    # Destination geometry
    dx, dy, dw, dh = dest.x, dest.y, dest.width, dest.height
    mid_w = max(0, dw - s * 2)
    mid_h = max(0, dh - s * 2)

    # Corners
    surface.blit(sheet, (dx,           dy          ), src(0,     0, s, s))
    surface.blit(sheet, (dx + dw - s,  dy          ), src(s*2,   0, s, s))
    surface.blit(sheet, (dx,           dy + dh - s ), src(0,   s*2, s, s))
    surface.blit(sheet, (dx + dw - s,  dy + dh - s ), src(s*2, s*2, s, s))

    # Edges (scaled)
    if mid_w > 0:
        top    = pygame.transform.scale(sheet.subsurface(src(s, 0,   s, s)), (mid_w, s))
        bot    = pygame.transform.scale(sheet.subsurface(src(s, s*2, s, s)), (mid_w, s))
        surface.blit(top, (dx + s, dy          ))
        surface.blit(bot, (dx + s, dy + dh - s ))
    if mid_h > 0:
        left   = pygame.transform.scale(sheet.subsurface(src(0,   s, s, s)), (s, mid_h))
        right  = pygame.transform.scale(sheet.subsurface(src(s*2, s, s, s)), (s, mid_h))
        surface.blit(left,  (dx,           dy + s))
        surface.blit(right, (dx + dw - s,  dy + s))

    # Centre fill
    if mid_w > 0 and mid_h > 0:
        centre = pygame.transform.scale(
            sheet.subsurface(src(s, s, s, s)), (mid_w, mid_h))
        surface.blit(centre, (dx + s, dy + s))


# ── Public API ────────────────────────────────────────────────────────────────

def draw_panel(surface: pygame.Surface, rect: pygame.Rect):
    """Draw a background panel."""
    sheet = _get_sheet()
    if sheet:
        _nine_slice(surface, sheet, _ROW_PANEL, rect)
    else:
        pygame.draw.rect(surface, _C_PANEL,  rect, border_radius=_C_RADIUS)
        pygame.draw.rect(surface, _C_BORDER, rect, 1, border_radius=_C_RADIUS)


def draw_button(surface: pygame.Surface, rect: pygame.Rect,
                hovered: bool = False, disabled: bool = False,
                active: bool = False, play: bool = False):
    """
    Draw a button.

    hovered  — mouse is over it
    disabled — greyed out, not clickable
    active   — currently selected (e.g. active tab)
    play     — green 'play event' accent style
    """
    sheet = _get_sheet()
    if sheet:
        if disabled:
            row = _ROW_BTN_DIS
        elif active:
            row = _ROW_BTN_ACT
        elif play:
            row = _ROW_BTN_PLAY
        elif hovered:
            row = _ROW_BTN_HOV
        else:
            row = _ROW_BTN
        _nine_slice(surface, sheet, row, rect)
    else:
        if disabled:
            bg, border = _C_BTN_DIS, _C_BORDER
        elif active:
            bg, border = _C_BTN_ACT, _C_BORDER
        elif play:
            bg, border = (_C_BTN_PLAY_H if hovered else _C_BTN_PLAY), _C_GREEN
        elif hovered:
            bg, border = _C_BTN_HOV, _C_BORDER
        else:
            bg, border = _C_BTN, _C_BORDER
        pygame.draw.rect(surface, bg,     rect, border_radius=4)
        pygame.draw.rect(surface, border, rect, 1, border_radius=4)
