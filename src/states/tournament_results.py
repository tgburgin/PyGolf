"""
TournamentResultsState — full leaderboard after a 4-round tournament.

Shows:
  • Tournament name and prize fund
  • Full sorted leaderboard with per-round scores and total vs par
  • Player row highlighted in green
  • Prize money and season points earned
  • Button → Season Standings
"""

import pygame

from src.career.tournament import TOUR_DISPLAY_NAMES
from src.ui                import fonts

# ── Colours ───────────────────────────────────────────────────────────────────
C_BG        = ( 10,  16,  10)
C_PANEL     = ( 18,  26,  18)
C_BORDER    = ( 58,  98,  58)
C_HDR       = ( 28,  42,  28)
C_WHITE     = (255, 255, 255)
C_GRAY      = (155, 158, 150)
C_GREEN     = ( 55, 185,  55)
C_RED       = (215,  50,  50)
C_YELLOW    = (215, 175,  50)
C_GOLD      = (210, 170,  30)
C_PLAYER_BG = ( 20,  55,  20)
C_PLAYER_BD = ( 60, 160,  60)
C_BTN       = ( 28,  78,  28)
C_BTN_HOV   = ( 48, 120,  48)

from src.constants import SCREEN_W, SCREEN_H

ROW_H      = 22
MAX_ROWS   = 22   # rows visible without scrolling


def _vs_par_str(vp: int) -> str:
    if vp == 0:
        return "E"
    return f"+{vp}" if vp > 0 else str(vp)


def _vs_par_color(vp: int) -> tuple:
    if vp < 0:
        return C_GREEN
    if vp > 0:
        return C_RED
    return C_WHITE


class TournamentResultsState:
    """Full tournament leaderboard screen."""

    def __init__(self, game, tournament, result: dict):
        """
        Parameters
        ----------
        game       : Game
        tournament : Tournament  (already complete)
        result     : dict from player.apply_tournament_result()
                     keys: position, prize, points
        """
        self.game       = game
        self.tournament = tournament
        self.result     = result

        self.font_title  = fonts.heading(36)
        self.font_hdr    = fonts.heading(15)
        self.font_medium = fonts.body(16)
        self.font_small  = fonts.body(14)
        self.font_large  = fonts.heading(22)

        self._leaderboard = tournament.get_leaderboard()
        self._scroll      = 0
        self._btn_hov     = False

        # Table geometry
        self._table_x  = 50
        self._table_y  = 160
        self._table_w  = SCREEN_W - 100
        col_widths = [40, 200, 120, 65, 65, 65, 65, 75]
        self._col_x = []
        cx = self._table_x
        for w in col_widths:
            self._col_x.append(cx)
            cx += w

        self._table_h = MAX_ROWS * ROW_H + 24

        btn_w, btn_h = 280, 50
        self._btn = pygame.Rect(
            SCREEN_W // 2 - btn_w // 2, SCREEN_H - 68, btn_w, btn_h)

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._btn_hov = self._btn.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self._btn.collidepoint(event.pos):
                self._go_standings()
            elif event.button == 4:   # scroll up
                self._scroll = max(0, self._scroll - 3)
            elif event.button == 5:   # scroll down
                max_scroll = max(0, len(self._leaderboard) - MAX_ROWS)
                self._scroll = min(max_scroll, self._scroll + 3)

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._go_standings()
            elif event.key == pygame.K_UP:
                self._scroll = max(0, self._scroll - 1)
            elif event.key == pygame.K_DOWN:
                max_scroll = max(0, len(self._leaderboard) - MAX_ROWS)
                self._scroll = min(max_scroll, self._scroll + 1)

    def _go_standings(self):
        from src.states.tour_standings import TourStandingsState
        self.game.change_state(TourStandingsState(self.game))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        pass

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)
        cx = SCREEN_W // 2
        t  = self.tournament
        r  = self.result

        # ── Title ─────────────────────────────────────────────────────────────
        tour_name = TOUR_DISPLAY_NAMES.get(t.tour_level, "Tour")
        title = self.font_title.render(t.name, True, C_WHITE)
        surface.blit(title, (cx - title.get_width() // 2, 16))

        sub = self.font_medium.render(tour_name, True, (100, 160, 80))
        surface.blit(sub, (cx - sub.get_width() // 2, 60))

        # ── Player result banner ──────────────────────────────────────────────
        pos_str   = self._ordinal(r["position"])
        prize_str = (f"  •  Prize: ${r['prize']:,}" if r["prize"] > 0
                     else "  •  Amateur event – no prize money")
        pts_str   = f"  •  {r['points']} season points"

        banner_txt = f"You finished {pos_str}{prize_str}{pts_str}"
        banner = self.font_large.render(banner_txt, True, C_GOLD)
        surface.blit(banner, (cx - banner.get_width() // 2, 88))

        # ── Leaderboard table ─────────────────────────────────────────────────
        self._draw_table(surface)

        # ── Button ────────────────────────────────────────────────────────────
        bg = C_BTN_HOV if self._btn_hov else C_BTN
        pygame.draw.rect(surface, bg, self._btn, border_radius=8)
        pygame.draw.rect(surface, C_GREEN, self._btn, 2, border_radius=8)
        lbl = self.font_medium.render("Season Standings  >", True, C_WHITE)
        surface.blit(lbl, lbl.get_rect(center=self._btn.center))

        # Scroll hint
        if len(self._leaderboard) > MAX_ROWS:
            hint = self.font_small.render("↑↓ / Scroll to see more", True, C_GRAY)
            surface.blit(hint, (cx - hint.get_width() // 2,
                                self._btn.top - 20))

    def _draw_table(self, surface):
        tx = self._table_x
        ty = self._table_y
        tw = self._table_w
        col = self._col_x

        # Header background
        pygame.draw.rect(surface, C_HDR,
                         pygame.Rect(tx, ty, tw, 24), border_radius=4)

        headers = ["Pos", "Name", "Nationality",
                   "Rd 1", "Rd 2", "Rd 3", "Rd 4", "Total"]
        for i, h in enumerate(headers):
            s = self.font_hdr.render(h, True, (150, 200, 120))
            surface.blit(s, (col[i] + 4, ty + 4))

        visible = self._leaderboard[self._scroll: self._scroll + MAX_ROWS]
        for row_i, entry in enumerate(visible):
            real_pos = self._scroll + row_i + 1
            ry       = ty + 24 + row_i * ROW_H
            is_pl    = entry["is_player"]

            # Row background
            if is_pl:
                pygame.draw.rect(surface, C_PLAYER_BG,
                                 pygame.Rect(tx, ry, tw, ROW_H - 1),
                                 border_radius=2)
                pygame.draw.rect(surface, C_PLAYER_BD,
                                 pygame.Rect(tx, ry, tw, ROW_H - 1), 1,
                                 border_radius=2)
            elif row_i % 2 == 0:
                pygame.draw.rect(surface, (16, 24, 16),
                                 pygame.Rect(tx, ry, tw, ROW_H - 1))

            tc = C_WHITE if is_pl else (200, 210, 200)

            # Pos
            surface.blit(self.font_small.render(str(real_pos), True, tc),
                         (col[0] + 4, ry + 3))
            # Name
            name_str = ("★ " + entry["name"]) if is_pl else entry["name"]
            surface.blit(self.font_small.render(name_str, True, tc),
                         (col[1] + 4, ry + 3))
            # Nationality
            surface.blit(self.font_small.render(entry["nationality"], True, C_GRAY),
                         (col[2] + 4, ry + 3))

            par = self.tournament.course_par
            rounds = entry["rounds"]
            for ri, rx in enumerate([col[3], col[4], col[5], col[6]]):
                if ri < len(rounds):
                    vp  = rounds[ri] - par
                    txt = _vs_par_str(vp)
                    col_c = _vs_par_color(vp) if is_pl else (180, 180, 180)
                    surface.blit(self.font_small.render(txt, True, col_c),
                                 (rx + 4, ry + 3))

            # Total vs par
            vp  = entry["vs_par"]
            txt = _vs_par_str(vp)
            surface.blit(self.font_small.render(txt, True,
                         _vs_par_color(vp) if is_pl else (200, 200, 200)),
                         (col[7] + 4, ry + 3))

    @staticmethod
    def _ordinal(n: int) -> str:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10
                  if n % 100 not in (11, 12, 13) else 0, "th")
        return f"{n}{suffix}"
