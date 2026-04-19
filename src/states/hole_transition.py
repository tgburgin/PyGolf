"""
HoleTransitionState — shown between holes.

Tournament mode : always shows the live running leaderboard — everyone's
                  score through the same number of holes as the player.
Free-play mode  : shows the running 18-hole scorecard.
"""

import pygame

from src.ui.scorecard import Scorecard
from src.ui           import fonts

C_BG        = ( 12,  20,  12)
C_HDR       = ( 28,  42,  28)
C_ROW_ALT   = ( 14,  22,  14)
C_BORDER    = ( 65,  95,  65)
C_WHITE     = (255, 255, 255)
C_GRAY      = (165, 168, 160)
C_GREEN     = ( 55, 185,  55)
C_RED       = (215,  50,  50)
C_YELLOW    = (215, 175,  50)
C_BTN       = ( 40, 120,  40)
C_BTN_HOV   = ( 60, 160,  60)
C_PLAYER_BG = ( 20,  55,  20)
C_PLAYER_BD = ( 60, 160,  60)

from src.constants import SCREEN_W, SCREEN_H

ROW_H    = 26


def _vp(diff):
    return "E" if diff == 0 else (f"+{diff}" if diff > 0 else str(diff))


def _vp_color(diff):
    return C_GREEN if diff < 0 else (C_RED if diff > 0 else C_WHITE)


class HoleTransitionState:

    def __init__(self, game, course, completed_hole_index, scores):
        self.game                 = game
        self.course               = course
        self.completed_hole_index = completed_hole_index
        self.scores               = scores   # hole scores this round so far

        self.scorecard = Scorecard(course)

        self.font_title  = fonts.heading(34)
        self.font_large  = fonts.heading(26)
        self.font_medium = fonts.body(19)
        self.font_small  = fonts.body(15)
        self.font_lb     = fonts.body(15)
        self.font_lb_hdr = fonts.heading(13)

        btn_w, btn_h = 260, 48
        self.btn_next = pygame.Rect(
            SCREEN_W // 2 - btn_w // 2, SCREEN_H - 68, btn_w, btn_h)
        self._btn_hover = False

        sc_w = min(1100, SCREEN_W - 60)
        self.sc_rect = pygame.Rect((SCREEN_W - sc_w) // 2, 220, sc_w, 200)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _score_label(self, strokes, par):
        if strokes == 1:
            return "Hole in One!", C_YELLOW
        labels = {
            -3: ("Albatross!", C_YELLOW),
            -2: ("Eagle!",     C_GREEN),
            -1: ("Birdie!",    C_GREEN),
             0: ("Par",        C_WHITE),
             1: ("Bogey",      C_RED),
             2: ("Double Bogey", C_RED),
        }
        return labels.get(strokes - par,
                          (f"+{strokes-par}" if strokes-par > 0
                           else str(strokes-par), C_RED))

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_next.collidepoint(event.pos):
                self._go_next()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_n):
                self._go_next()
        elif event.type == pygame.MOUSEMOTION:
            self._btn_hover = self.btn_next.collidepoint(event.pos)

    def _go_next(self):
        from src.states.golf_round import GolfRoundState
        self.game.change_state(
            GolfRoundState(self.game, self.course,
                           self.completed_hole_index + 1, self.scores))

    def update(self, dt):
        pass

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)
        cx = SCREEN_W // 2

        hole_num = self.completed_hole_index + 1

        # ── Title ─────────────────────────────────────────────────────────────
        title = self.font_title.render(f"Hole {hole_num} Complete", True, C_WHITE)
        surface.blit(title, (cx - title.get_width() // 2, 18))

        # ── Score badge ───────────────────────────────────────────────────────
        strokes = self.scores[-1]
        par     = self.course.get_hole(self.completed_hole_index).par
        label, lcolor = self._score_label(strokes, par)
        badge = self.font_large.render(label, True, lcolor)
        surface.blit(badge, (cx - badge.get_width() // 2, 62))

        detail = self.font_medium.render(
            f"{strokes} strokes  •  Par {par}", True, C_GRAY)
        surface.blit(detail, (cx - detail.get_width() // 2, 96))

        # ── Running round total ───────────────────────────────────────────────
        total_strokes = sum(self.scores)
        total_par     = self.course.total_par_through(len(self.scores))
        diff          = total_strokes - total_par
        running = self.font_medium.render(
            f"Round total after {len(self.scores)} holes:  "
            f"{total_strokes}  ({_vp(diff)})",
            True, _vp_color(diff))
        surface.blit(running, (cx - running.get_width() // 2, 128))

        # ── Main content ──────────────────────────────────────────────────────
        t = self.game.current_tournament
        content_y = 172

        if t is not None:
            lb = t.get_live_leaderboard(len(self.scores), self.scores)
            self._draw_leaderboard(surface, lb, len(self.scores), t, content_y)
        else:
            self._draw_scorecard(surface, content_y)

        # ── Next Hole button ──────────────────────────────────────────────────
        next_num  = self.completed_hole_index + 2
        btn_color = C_BTN_HOV if self._btn_hover else C_BTN
        pygame.draw.rect(surface, btn_color, self.btn_next, border_radius=8)
        pygame.draw.rect(surface, C_GREEN,   self.btn_next, 2, border_radius=8)
        btn_lbl = self.font_medium.render(
            f"Next: Hole {next_num}  (Enter)", True, C_WHITE)
        surface.blit(btn_lbl, btn_lbl.get_rect(center=self.btn_next.center))

        remaining = 18 - len(self.scores)
        hint = self.font_small.render(
            f"{remaining} hole{'s' if remaining != 1 else ''} remaining",
            True, C_GRAY)
        surface.blit(hint, (cx - hint.get_width() // 2,
                            self.btn_next.bottom + 5))

    # ── Live leaderboard ──────────────────────────────────────────────────────

    def _draw_leaderboard(self, surface, lb, holes_done, tournament, top_y):
        top10        = lb[:10]
        player_pos   = next((i + 1 for i, e in enumerate(lb) if e["is_player"]), None)
        player_entry = next((e for e in lb if e["is_player"]), None)
        in_top10     = player_pos is not None and player_pos <= 10

        cx = SCREEN_W // 2
        tw = 700
        tx = cx - tw // 2

        col_pos  = tx
        col_name = tx + 44
        col_vp   = tx + 310
        col_thru = tx + 400

        # Section header
        rnd_num = tournament.current_round_number
        rnd_lbl = (f"Event leaderboard — Round {rnd_num}  •  After hole {holes_done}"
                   if tournament.total_rounds > 1
                   else f"Event leaderboard  •  After hole {holes_done}")
        pygame.draw.rect(surface, C_HDR,
                         pygame.Rect(tx, top_y, tw, 22), border_radius=4)
        surface.blit(self.font_lb_hdr.render(rnd_lbl, True, (150, 200, 120)),
                     (tx + 6, top_y + 4))

        # Column headers
        hdr_y = top_y + 24
        pygame.draw.rect(surface, (20, 32, 20), pygame.Rect(tx, hdr_y, tw, 18))
        for txt, cx_pos in [("Pos", col_pos), ("Player", col_name),
                             ("Score", col_vp), ("Thru", col_thru)]:
            surface.blit(self.font_lb_hdr.render(txt, True, (130, 170, 110)),
                         (cx_pos + 4, hdr_y + 2))

        def draw_row(ry, pos, entry, is_player):
            if is_player:
                pygame.draw.rect(surface, C_PLAYER_BG,
                                 pygame.Rect(tx, ry, tw, ROW_H - 2), border_radius=2)
                pygame.draw.rect(surface, C_PLAYER_BD,
                                 pygame.Rect(tx, ry, tw, ROW_H - 2), 1, border_radius=2)
            elif pos % 2 == 0:
                pygame.draw.rect(surface, C_ROW_ALT,
                                 pygame.Rect(tx, ry, tw, ROW_H - 2))

            tc = C_WHITE if is_player else (195, 205, 195)
            vp = entry["vs_par"]

            surface.blit(self.font_lb.render(str(pos), True, tc), (col_pos + 4, ry + 5))
            name_str = ("★ " + entry["name"]) if is_player else entry["name"]
            surface.blit(self.font_lb.render(name_str, True, tc), (col_name + 4, ry + 5))

            vp_col = _vp_color(vp) if is_player else (
                (150, 195, 150) if vp < 0 else (195, 150, 150) if vp > 0 else (175, 175, 175))
            surface.blit(self.font_lb.render(_vp(vp), True, vp_col), (col_vp + 4, ry + 5))
            surface.blit(self.font_lb.render(str(holes_done), True, C_GRAY),
                         (col_thru + 4, ry + 5))

        row_start = hdr_y + 20
        for i, entry in enumerate(top10):
            draw_row(row_start + i * ROW_H, i + 1, entry, entry["is_player"])

        if not in_top10 and player_entry is not None:
            sep_y = row_start + 10 * ROW_H + 2
            for x in range(tx, tx + tw, 8):
                pygame.draw.line(surface, (55, 75, 55), (x, sep_y), (x + 4, sep_y))
            dots = self.font_lb_hdr.render("· · ·", True, C_GRAY)
            surface.blit(dots, (cx - dots.get_width() // 2, sep_y - 1))
            draw_row(sep_y + 12, player_pos, player_entry, True)

    # ── Scorecard fallback ────────────────────────────────────────────────────

    def _draw_scorecard(self, surface, top_y):
        cx = SCREEN_W // 2
        lbl = self.font_small.render("SCORECARD", True, C_GRAY)
        surface.blit(lbl, (self.sc_rect.x, top_y - lbl.get_height() - 2))
        sc = pygame.Rect(self.sc_rect.x, top_y, self.sc_rect.width, self.sc_rect.height)
        self.scorecard.draw(surface, sc, self.scores)
        pygame.draw.line(surface, C_BORDER,
                         (60, sc.bottom + 12), (SCREEN_W - 60, sc.bottom + 12))
