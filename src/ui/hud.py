"""
HUD — the right-hand info panel drawn during a golf round.

Displays:
  • Hole number, par, and yardage
  • Stroke count and score vs par
  • Current terrain (lie)
  • Active club with prev/next cycle buttons
  • Power bar (fills while player drags)
  • Shot shape selector (Draw / Straight / Fade)
  • Mini-map of the hole with ball and pin markers
"""

import math

import pygame

from src.golf.shot import ShotState, ShotShape, MAX_DRAG_PIXELS
from src.utils.math_utils import clamp

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG         = ( 22,  28,  22)
C_PANEL_TOP  = ( 32,  40,  32)
C_BORDER     = ( 75, 105,  75)
C_DIVIDER    = ( 50,  70,  50)
C_WHITE      = (255, 255, 255)
C_OFF_WHITE  = (220, 225, 215)
C_LIGHT_GRAY = (165, 168, 160)
C_DARK_GRAY  = ( 48,  52,  48)
C_GREEN      = ( 55, 185,  55)
C_RED        = (215,  50,  50)
C_GOLD       = (215, 175,  50)
C_BLUE       = ( 60, 120, 215)

PANEL_WIDTH  = 320


class HUD:
    """Right-side information and control panel."""

    def __init__(self, screen_width, screen_height):
        self.screen_width  = screen_width
        self.screen_height = screen_height
        self.panel_x       = screen_width - PANEL_WIDTH
        self.panel_rect    = pygame.Rect(self.panel_x, 0, PANEL_WIDTH, screen_height)

        self.font_large  = pygame.font.SysFont("arial", 28, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 19)
        self.font_small  = pygame.font.SysFont("arial", 15)

        self._build_buttons()

    def _build_buttons(self):
        px = self.panel_x

        # Club navigation arrows
        self.btn_prev_club = pygame.Rect(px + 10,  260, 34, 28)
        self.btn_next_club = pygame.Rect(px + 276, 260, 34, 28)

        # Shot shape buttons
        btn_y = 390
        btn_w = 84
        btn_h = 34
        gap   = 5
        self.shape_buttons = {
            ShotShape.DRAW:     pygame.Rect(px + 10,                  btn_y, btn_w, btn_h),
            ShotShape.STRAIGHT: pygame.Rect(px + 10 +  btn_w + gap,   btn_y, btn_w, btn_h),
            ShotShape.FADE:     pygame.Rect(px + 10 + (btn_w + gap)*2, btn_y, btn_w, btn_h),
        }

        # Mini-map area (shifted down to make room for wind section)
        self.minimap_rect = pygame.Rect(px + 10, 508, PANEL_WIDTH - 20, 160)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface, hole, strokes, club, shot_ctrl, terrain_name,
             renderer=None, ball_world_pos=None, wind_angle=0.0, wind_strength=0,
             ball_id=None):
        """
        Draw the complete HUD panel.

        renderer        : CourseRenderer — used to draw the mini-map (optional)
        ball_world_pos  : (x, y) in world pixels — ball position for mini-map
        """
        # ── Background ────────────────────────────────────────────────────────
        pygame.draw.rect(surface, C_BG, self.panel_rect)

        # Gradient header stripe
        header = pygame.Rect(self.panel_x, 0, PANEL_WIDTH, 72)
        pygame.draw.rect(surface, C_PANEL_TOP, header)
        pygame.draw.line(surface, C_BORDER,
                         (self.panel_x, 0), (self.panel_x, self.screen_height), 2)

        x  = self.panel_x + 14   # left content margin
        rw = PANEL_WIDTH - 28    # usable row width

        # ── Hole header ───────────────────────────────────────────────────────
        self._text(surface, f"Hole {hole.number}", self.font_large, C_WHITE, x, 14)
        par_txt = f"Par {hole.par}   •   {hole.yardage} yds"
        self._text(surface, par_txt, self.font_small, C_LIGHT_GRAY, x, 48)

        self._divider(surface, 72)

        # ── Strokes ───────────────────────────────────────────────────────────
        y = 82
        self._text(surface, "Strokes", self.font_small, C_LIGHT_GRAY, x, y)

        num_surf = self.font_large.render(str(strokes), True, C_WHITE)
        surface.blit(num_surf, (x, y + 18))

        if strokes > 0:
            diff = strokes - hole.par
            diff_str   = (str(diff) if diff < 0
                          else "E" if diff == 0
                          else f"+{diff}")
            diff_color = C_GREEN if diff < 0 else C_WHITE if diff == 0 else C_RED
            self._text(surface, diff_str, self.font_medium, diff_color,
                       x + num_surf.get_width() + 10, y + 22)

        self._divider(surface, 140)

        # ── Lie ───────────────────────────────────────────────────────────────
        y = 150
        self._text(surface, "Lie",         self.font_small,  C_LIGHT_GRAY, x,      y)
        self._text(surface, terrain_name,  self.font_medium, C_OFF_WHITE,  x + 32, y - 1)

        self._divider(surface, 178)

        # ── Club ──────────────────────────────────────────────────────────────
        y = 188
        self._text(surface, "Club", self.font_small, C_LIGHT_GRAY, x, y)

        # Active ball pill (right-aligned, same row as the "Club" label)
        if ball_id is not None:
            self._draw_ball_pill(surface, ball_id,
                                 self.panel_x + PANEL_WIDTH - 14, y - 2)

        # Prev / Next arrows
        self._draw_button(surface, self.btn_prev_club, "<", C_DARK_GRAY, C_OFF_WHITE)
        self._draw_button(surface, self.btn_next_club, ">", C_DARK_GRAY, C_OFF_WHITE)

        # Club name centred between arrows
        club_cx = (self.btn_prev_club.right + self.btn_next_club.left) // 2
        club_s  = self.font_medium.render(club.name, True, C_GOLD)
        surface.blit(club_s, (club_cx - club_s.get_width() // 2,
                               self.btn_prev_club.y + 5))

        # Max distance below
        dist_s = self.font_small.render(f"Max {club.max_distance_yards} yds",
                                         True, C_LIGHT_GRAY)
        surface.blit(dist_s, (club_cx - dist_s.get_width() // 2, 295))

        self._divider(surface, 318)

        # ── Power bar ─────────────────────────────────────────────────────────
        y = 326
        self._text(surface, "Power", self.font_small, C_LIGHT_GRAY, x, y)

        power    = shot_ctrl.get_power()
        bar_rect = pygame.Rect(x, y + 18, rw, 20)

        pygame.draw.rect(surface, C_DARK_GRAY, bar_rect, border_radius=4)
        if power > 0:
            fc = (C_GREEN if power < 0.65 else C_GOLD if power < 0.88 else C_RED)
            pygame.draw.rect(surface, fc,
                             pygame.Rect(x, y + 18, int(rw * power), 20),
                             border_radius=4)
        pygame.draw.rect(surface, C_DIVIDER, bar_rect, 1, border_radius=4)

        pct = self.font_small.render(f"{int(power * 100)}%", True, C_WHITE)
        surface.blit(pct, (x + rw // 2 - pct.get_width() // 2, y + 20))

        self._divider(surface, 368)

        # ── Shot shape ────────────────────────────────────────────────────────
        y = 376
        self._text(surface, "Shot Shape", self.font_small, C_LIGHT_GRAY, x, y)

        accents = {ShotShape.DRAW: C_BLUE, ShotShape.STRAIGHT: C_GREEN, ShotShape.FADE: C_RED}
        for shape, rect in self.shape_buttons.items():
            accent   = accents[shape]
            active   = shot_ctrl.shot_shape == shape
            bg       = accent if active else C_DARK_GRAY
            pygame.draw.rect(surface, bg,     rect, border_radius=5)
            pygame.draw.rect(surface, accent, rect, 2, border_radius=5)
            lbl = self.font_small.render(shape.value, True, C_WHITE)
            # Draw a small shape glyph above the label so the buttons are
            # distinguishable without relying on colour alone.
            self._draw_shape_glyph(surface, rect, shape, C_WHITE)
            surface.blit(lbl, lbl.get_rect(
                centerx=rect.centerx, bottom=rect.bottom - 4))

        self._divider(surface, 434)

        # ── Wind ──────────────────────────────────────────────────────────────
        y = 440
        self._text(surface, "Wind", self.font_small, C_LIGHT_GRAY, x, y)
        self._draw_wind(surface, x, y + 16, wind_angle, wind_strength)

        self._divider(surface, 488)

        # ── Mini-map ──────────────────────────────────────────────────────────
        y = 494
        self._text(surface, "Course Map", self.font_small, C_LIGHT_GRAY, x, y)

        if renderer is not None and ball_world_pos is not None:
            renderer.draw_minimap(surface, self.minimap_rect, ball_world_pos)
        else:
            # Placeholder if renderer not provided
            pygame.draw.rect(surface, C_DARK_GRAY, self.minimap_rect, border_radius=3)
            pygame.draw.rect(surface, C_DIVIDER,   self.minimap_rect, 1, border_radius=3)

        self._divider(surface, self.minimap_rect.bottom + 8)

        # ── Controls (compact) ────────────────────────────────────────────────
        y = self.minimap_rect.bottom + 16
        for line in ("Click near ball  •  Drag to aim",
                     "Release to shoot  •  Scroll = club"):
            self._text(surface, line, self.font_small, (110, 115, 108), x, y)
            y += 20

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_click(self, pos, shot_ctrl, clubs, current_index):
        for shape, rect in self.shape_buttons.items():
            if rect.collidepoint(pos):
                shot_ctrl.shot_shape = shape
                return current_index
        if self.btn_prev_club.collidepoint(pos):
            return (current_index - 1) % len(clubs)
        if self.btn_next_club.collidepoint(pos):
            return (current_index + 1) % len(clubs)
        return current_index

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _text(self, surface, text, font, color, x, y):
        surface.blit(font.render(text, True, color), (x, y))

    def _divider(self, surface, y):
        pygame.draw.line(surface, C_DIVIDER,
                         (self.panel_x + 10, y),
                         (self.panel_x + PANEL_WIDTH - 10, y))

    _BALL_COLOURS = {
        "range":    (200, 200, 200),
        "tour":     (240, 240, 240),
        "distance": (250, 220, 120),
        "spin":     (200, 120, 220),
        "soft":     (180, 225, 240),
        "pro_tour": (255, 255, 255),
    }

    def _draw_ball_pill(self, surface, ball_id, right_x, y):
        """Compact active-ball badge: coloured dot + short label, right-aligned."""
        from src.golf.ball_types import get_ball
        info  = get_ball(ball_id)
        label = info["label"]
        lbl   = self.font_small.render(label, True, C_OFF_WHITE)
        pad   = 6
        w     = 14 + lbl.get_width() + pad * 2
        h     = lbl.get_height() + 4
        rect  = pygame.Rect(right_x - w, y, w, h)
        pygame.draw.rect(surface, C_DARK_GRAY, rect, border_radius=h // 2)
        pygame.draw.rect(surface, C_DIVIDER,   rect, 1, border_radius=h // 2)
        dot_col = self._BALL_COLOURS.get(ball_id, (220, 220, 220))
        pygame.draw.circle(surface, dot_col,
                           (rect.x + pad + 4, rect.centery), 4)
        pygame.draw.circle(surface, C_DARK_GRAY,
                           (rect.x + pad + 4, rect.centery), 4, 1)
        surface.blit(lbl, (rect.x + pad + 12, rect.y + 2))

    def _draw_shape_glyph(self, surface, rect, shape, color):
        """Tiny curve-arrow glyph centred near the top of a shape button.

        Draw = curves left, Straight = arrow straight up, Fade = curves right.
        Gives shape buttons a non-colour cue for colour-blind players.
        """
        from src.golf.shot import ShotShape
        cx = rect.centerx
        top = rect.y + 5
        if shape == ShotShape.STRAIGHT:
            pygame.draw.line(surface, color, (cx, top + 11), (cx, top), 2)
            pygame.draw.polygon(surface, color,
                                [(cx, top - 1), (cx - 3, top + 4), (cx + 3, top + 4)])
            return
        # DRAW curves left (points end up-left), FADE curves right.
        sign = -1 if shape == ShotShape.DRAW else 1
        pts = [(cx - sign * 6, top + 11),
               (cx,            top + 7),
               (cx + sign * 2, top + 1)]
        pygame.draw.lines(surface, color, False, pts, 2)
        tip = pts[-1]
        pygame.draw.polygon(surface, color, [
            tip,
            (tip[0] - sign * 4, tip[1] + 3),
            (tip[0] + sign * 1, tip[1] + 4),
        ])

    def _draw_wind(self, surface, x, y, angle, strength):
        """Draw a compact wind indicator: compass arrow + cardinal + strength dots."""
        if strength == 0:
            s = self.font_medium.render("Calm", True, C_LIGHT_GRAY)
            surface.blit(s, (x, y))
            return

        # Compass circle + arrow
        cx, cy = x + 14, y + 12
        pygame.draw.circle(surface, C_DARK_GRAY, (cx, cy), 12)
        pygame.draw.circle(surface, C_DIVIDER,   (cx, cy), 12, 1)
        ndx, ndy = math.cos(angle), math.sin(angle)
        ex, ey = int(cx + ndx * 9), int(cy + ndy * 9)
        pygame.draw.line(surface, C_OFF_WHITE, (cx, cy), (ex, ey), 2)
        # Arrowhead
        lx = int(ex - ndx * 5 + ndy * 3)
        ly = int(ey - ndy * 5 - ndx * 3)
        rx = int(ex - ndx * 5 - ndy * 3)
        ry = int(ey - ndy * 5 + ndx * 3)
        pygame.draw.polygon(surface, C_OFF_WHITE, [(ex, ey), (lx, ly), (rx, ry)])

        # Cardinal direction — arrow and label both show drift direction.
        # pygame: angle=0→East, angle=π/2→South (y-down), so compass = 90+degrees(angle)
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        bearing = (90 + math.degrees(angle)) % 360
        cardinal = dirs[int((bearing + 22.5) / 45) % 8]
        self._text(surface, cardinal, self.font_medium, C_OFF_WHITE, x + 34, y + 4)

        # Strength dots (5 max)
        dot_color = C_GREEN if strength <= 2 else C_GOLD if strength <= 3 else C_RED
        dot_x0, dot_y = x + 76, y + 12
        for i in range(5):
            c = dot_color if i < strength else C_DARK_GRAY
            pygame.draw.circle(surface, c,        (dot_x0 + i * 11, dot_y), 4)
            pygame.draw.circle(surface, C_DIVIDER, (dot_x0 + i * 11, dot_y), 4, 1)

    def _draw_button(self, surface, rect, label, bg, text_color):
        pygame.draw.rect(surface, bg,        rect, border_radius=4)
        pygame.draw.rect(surface, C_BORDER,  rect, 1, border_radius=4)
        lbl = self.font_medium.render(label, True, text_color)
        surface.blit(lbl, lbl.get_rect(center=rect.center))
