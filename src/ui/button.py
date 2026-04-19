"""
Shared button helper with idle / hover / pressed / disabled states.

States call `draw_button(...)` with a rect, label, and a set of flags;
press feedback is a one-frame-scale dip + darker fill while the mouse
button is held. States that want this behaviour track which button
is "pressed" via `pressed_key == key` and clear it on mouseup.

Kept deliberately small — no layout math, no click dispatch, no callbacks.
Those live at the call site.
"""

from __future__ import annotations

import pygame


def draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    bg,
    bg_hover,
    bg_disabled,
    border,
    border_disabled=None,
    text_color=(255, 255, 255),
    text_disabled=(130, 130, 130),
    hovered: bool = False,
    pressed: bool = False,
    disabled: bool = False,
    radius: int = 8,
):
    """Draw a single button. Returns the rect actually used (possibly shrunk
    by 1 px when pressed, so the caller can blit a glyph at the same visual
    centre if needed)."""

    if disabled:
        fill = bg_disabled
        border_col = border_disabled or border
        tc = text_disabled
    elif pressed:
        fill = _darken(bg_hover if hovered else bg, 0.78)
        border_col = border
        tc = text_color
    elif hovered:
        fill = bg_hover
        border_col = border
        tc = text_color
    else:
        fill = bg
        border_col = border
        tc = text_color

    draw_rect = rect.inflate(-2, -2) if pressed else rect
    pygame.draw.rect(surface, fill,       draw_rect, border_radius=radius)
    pygame.draw.rect(surface, border_col, draw_rect, 2, border_radius=radius)

    lbl = font.render(label, True, tc)
    surface.blit(lbl, lbl.get_rect(center=draw_rect.center))
    return draw_rect


def _darken(rgb, f: float):
    return (int(rgb[0] * f), int(rgb[1] * f), int(rgb[2] * f))
