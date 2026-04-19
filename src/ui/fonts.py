"""
Fonts — cached loader for the project's body/heading typefaces.

Design intent
-------------
Default to the bundled pixel font (PixelOperator) when the TTFs are present
in assets/fonts/; gracefully fall back to SysFont("arial") when they aren't.
This lets the repo ship without a font binary (the maintainer drops a trusted
copy in assets/fonts/ themselves) while the code path that calls `body(16)`
or `heading(28)` doesn't have to care.

Usage
-----
    from src.ui import fonts

    label = fonts.body(14).render("Power", True, WHITE)
    title = fonts.heading(72).render("Let's Golf!", True, GREEN)

The cache is keyed by (family, size, bold) so repeated calls during a draw
don't re-open the TTF.

Installing the pixel font
-------------------------
Download PixelOperator (CC0, by Jayvee Enaguas) from a trusted source and
place:

    assets/fonts/PixelOperator.ttf       (regular body)
    assets/fonts/PixelOperator-Bold.ttf  (bold, used for headings)

Suggested mirrors: the author's page at http://www.pixeloperator.com/, the
Arch Linux package `ttf-pixel-operator`, or the archived version on Internet
Archive. The file hashes should be verified before committing.
"""

from __future__ import annotations

import os
import pygame

_FONT_DIR = os.path.join("assets", "fonts")

# Physical files we look for. Missing → we fall back to SysFont.
_BODY_TTF    = "PixelOperator.ttf"
_BODY_BOLD   = "PixelOperator-Bold.ttf"

# Per-session cache. Cleared on pygame.quit() naturally since Font objects
# become invalid then; callers should not hold references across states.
_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}

# Pixel fonts render crisp at integer pixel sizes only. When a caller asks
# for a "pt" size that would otherwise be antialiased, we round down to the
# nearest multiple of a base unit so letters stay on a clean grid. Empirical
# good units for PixelOperator: 8, 12, 16, 20, 24, 32, 48, 64.
_PIXEL_SNAP = (8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 72)


def _snap(size: int) -> int:
    """Round size down to the nearest pixel-friendly tick."""
    best = _PIXEL_SNAP[0]
    for tick in _PIXEL_SNAP:
        if tick <= size:
            best = tick
        else:
            break
    return best


def _load(family: str, size: int, bold: bool) -> pygame.font.Font:
    key = (family, size, bold)
    if key in _cache:
        return _cache[key]

    ttf = _BODY_BOLD if bold else _BODY_TTF
    path = os.path.join(_FONT_DIR, ttf)
    font: pygame.font.Font
    if os.path.isfile(path):
        try:
            font = pygame.font.Font(path, _snap(size))
        except Exception:
            font = pygame.font.SysFont("arial", size, bold=bold)
    else:
        # No TTF shipped — use the system font so development/testing still
        # works even without the binary asset.
        font = pygame.font.SysFont("arial", size, bold=bold)

    _cache[key] = font
    return font


def body(size: int, *, bold: bool = False) -> pygame.font.Font:
    """Regular body font — labels, hints, HUD values."""
    return _load("body", size, bold)


def heading(size: int) -> pygame.font.Font:
    """Bold heading font — titles, section headers, large numbers."""
    return _load("heading", size, bold=True)


def clear_cache() -> None:
    """Drop cached Font objects. Call on display reinit if ever needed."""
    _cache.clear()


def render_shadowed(font: pygame.font.Font, text: str, fg,
                    shadow=(0, 0, 0), offset: tuple[int, int] = (1, 1)
                    ) -> pygame.Surface:
    """Render text with a hard 1 px drop shadow on a transparent surface.

    Pixel fonts at small sizes lose legibility on colourful backgrounds; a
    dark shadow gives every glyph a crisp edge. The returned surface is
    slightly larger than the text to hold the offset.
    """
    fg_surf  = font.render(text, False, fg)
    sh_surf  = font.render(text, False, shadow)
    w = fg_surf.get_width() + abs(offset[0])
    h = fg_surf.get_height() + abs(offset[1])
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(sh_surf, (max(0, offset[0]), max(0, offset[1])))
    out.blit(fg_surf, (max(0, -offset[0]), max(0, -offset[1])))
    return out
