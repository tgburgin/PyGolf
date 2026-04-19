"""
Scorecard — draws an 18-hole golf scorecard table.

The card is split into front nine (holes 1-9) and back nine (holes 10-18),
each with a subtotal column.  Score cells are colour-coded:

  Hole-in-one / Albatross  → gold background
  Eagle (-2 or better)     → dark green background
  Birdie (-1)              → green background
  Par                      → plain white text
  Bogey (+1)               → light red background
  Double bogey (+2)        → red background
  Worse                    → dark red background

Holes not yet played show a dash.
"""

import pygame

from src.ui import fonts

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG        = ( 18,  24,  18)
C_HEADER    = ( 35,  50,  35)
C_ROW_DARK  = ( 28,  36,  28)
C_ROW_LIGHT = ( 38,  48,  38)
C_BORDER    = ( 65,  90,  65)
C_WHITE     = (255, 255, 255)
C_GRAY      = (160, 165, 155)
C_GOLD      = (210, 175,  40)   # eagle / ace
C_D_GREEN   = ( 20, 140,  20)   # eagle background
C_GREEN     = ( 45, 175,  45)   # birdie background
C_L_RED     = (200,  80,  80)   # bogey background
C_RED       = (180,  40,  40)   # double-bogey background
C_D_RED     = (120,  20,  20)   # worse background
C_PAR_TEXT  = (230, 235, 225)   # par — white-ish text, no fill


def _score_style(strokes, par):
    """Return (bg_color_or_None, text_color) for a score cell."""
    diff = strokes - par
    if diff <= -3:
        return C_GOLD,    (0, 0, 0)
    elif diff == -2:
        return C_D_GREEN, C_WHITE
    elif diff == -1:
        return C_GREEN,   C_WHITE
    elif diff == 0:
        return None,      C_PAR_TEXT
    elif diff == 1:
        return C_L_RED,   C_WHITE
    elif diff == 2:
        return C_RED,     C_WHITE
    else:
        return C_D_RED,   C_WHITE


class Scorecard:
    """
    Renders an 18-hole scorecard onto a pygame Surface.

    Usage
    ─────
        sc = Scorecard(course)
        sc.draw(surface, pygame.Rect(x, y, width, height), scores)

    Parameters
    ──────────
    course  : Course object
    surface : target pygame.Surface
    rect    : pygame.Rect — area to fill
    scores  : list[int] — stroke counts for completed holes (len 0..18)
              holes beyond len(scores) show as unplayed
    """

    _ROW_LABELS = ("HOLE", "PAR", "YOU")

    def __init__(self, course):
        self.course    = course
        self.font_hdr  = fonts.heading(15)
        self.font_cell = fonts.heading(14)
        self.font_lbl  = fonts.body(12)

    def draw(self, surface, rect, scores):
        """Draw the scorecard into rect."""
        pygame.draw.rect(surface, C_BG, rect)
        pygame.draw.rect(surface, C_BORDER, rect, 1)

        w, h = rect.width, rect.height
        x0, y0 = rect.x, rect.y

        # Layout: 2 rows of 9 holes  (front / back)
        # Each row has: label col + 9 hole cols + total col  = 11 cols
        label_w  = 36
        total_w  = 34
        hole_w   = (w - label_w - total_w) // 9
        row_h    = h // 6   # 3 data rows × 2 nines

        for nine in range(2):          # 0 = front, 1 = back
            start_hole = nine * 9      # 0-based index into course.holes
            ry = y0 + nine * (row_h * 3)

            # ── Section header ────────────────────────────────────────────────
            hdr_rect = pygame.Rect(x0, ry, w, row_h)
            pygame.draw.rect(surface, C_HEADER, hdr_rect)
            hdr_text = "FRONT NINE" if nine == 0 else "BACK NINE"
            lbl = self.font_hdr.render(hdr_text, True, C_GRAY)
            surface.blit(lbl, (x0 + 4, ry + (row_h - lbl.get_height()) // 2))

            # OUT / IN total par for this nine
            nine_par    = sum(self.course.holes[start_hole + i].par for i in range(9))
            nine_scores = scores[start_hole:start_hole + 9]
            nine_total  = sum(nine_scores) if len(nine_scores) == 9 else None

            ry += row_h   # move down past header

            # ── Three data rows: HOLE, PAR, YOU ───────────────────────────────
            for row_idx, label in enumerate(self._ROW_LABELS):
                row_rect = pygame.Rect(x0, ry, w, row_h)
                bg = C_ROW_DARK if row_idx % 2 == 0 else C_ROW_LIGHT
                pygame.draw.rect(surface, bg, row_rect)

                # Label cell
                lbl_surf = self.font_lbl.render(label, True, C_GRAY)
                surface.blit(lbl_surf,
                             (x0 + 2, ry + (row_h - lbl_surf.get_height()) // 2))

                # 9 hole cells
                for i in range(9):
                    hi   = start_hole + i
                    hole = self.course.holes[hi]
                    cx   = x0 + label_w + i * hole_w
                    cell = pygame.Rect(cx, ry, hole_w, row_h)

                    # Grid line
                    pygame.draw.line(surface, C_BORDER,
                                     (cx, ry), (cx, ry + row_h))

                    if row_idx == 0:           # HOLE row
                        txt = str(hole.number)
                        color = C_GRAY
                        self._draw_cell(surface, cell, txt, self.font_cell, None, color)

                    elif row_idx == 1:         # PAR row
                        self._draw_cell(surface, cell, str(hole.par),
                                        self.font_cell, None, C_GRAY)

                    else:                       # YOU row
                        if hi < len(scores):
                            s      = scores[hi]
                            bg_c, tc = _score_style(s, hole.par)
                            self._draw_cell(surface, cell, str(s),
                                            self.font_cell, bg_c, tc)
                        else:
                            self._draw_cell(surface, cell, "–",
                                            self.font_cell, None, (80, 85, 78))

                # Total / OUT / IN cell
                tx   = x0 + label_w + 9 * hole_w
                tcell = pygame.Rect(tx, ry, total_w, row_h)
                pygame.draw.line(surface, C_BORDER, (tx, ry), (tx, ry + row_h))

                if row_idx == 0:
                    txt, color = ("OUT" if nine == 0 else "IN"), C_GRAY
                elif row_idx == 1:
                    txt, color = str(nine_par), C_GRAY
                else:
                    if nine_total is not None:
                        diff = nine_total - nine_par
                        ds   = ("E" if diff == 0
                                else f"+{diff}" if diff > 0
                                else str(diff))
                        txt  = f"{nine_total} ({ds})"
                        color = C_GREEN if diff < 0 else (C_L_RED if diff > 0 else C_WHITE)
                    else:
                        played = len(nine_scores)
                        txt    = f"–/{nine_par}" if played == 0 else f"{sum(nine_scores)}…"
                        color  = C_GRAY
                self._draw_cell(surface, tcell, txt, self.font_lbl, None, color)

                ry += row_h

        # ── Grand total row ───────────────────────────────────────────────────
        if len(scores) == 18:
            total_strokes = sum(scores)
            diff          = total_strokes - self.course.par
            ds            = ("E" if diff == 0 else f"+{diff}" if diff > 0 else str(diff))
            total_txt     = f"TOTAL  {total_strokes}  ({ds})"
            tc            = (C_GREEN if diff < 0
                             else C_L_RED if diff > 0
                             else C_WHITE)
            total_row = pygame.Rect(x0, y0 + h - row_h, w, row_h)
            pygame.draw.rect(surface, C_HEADER, total_row)
            s = self.font_hdr.render(total_txt, True, tc)
            surface.blit(s, (x0 + w // 2 - s.get_width() // 2,
                             total_row.y + (row_h - s.get_height()) // 2))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _draw_cell(self, surface, rect, text, font, bg_color, text_color):
        if bg_color:
            pygame.draw.rect(surface, bg_color, rect)
        surf = font.render(text, True, text_color)
        surface.blit(surf, surf.get_rect(center=rect.center))
