"""
TourStandingsState — season-long standings screen.

Shows the full points table for the current tour season, highlights the
player's position, and provides the "Play Next Event" / "Start New Season"
flow.  Promotion (or relegation) is evaluated at season end.
"""

import pygame

from src.career.tournament import TOUR_DISPLAY_NAMES, EVENTS_PER_SEASON, PROMOTION_THRESHOLD
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
C_PROMO     = ( 40, 120,  40)   # promotion zone row tint
C_PLAYER_BG = ( 20,  55,  20)
C_PLAYER_BD = ( 60, 160,  60)
C_BTN       = ( 28,  78,  28)
C_BTN_HOV   = ( 48, 120,  48)
C_BTN_RED   = ( 78,  28,  28)
C_BTN_RED_H = (120,  48,  48)

from src.constants import SCREEN_W, SCREEN_H

ROW_H     = 22
MAX_ROWS  = 22


class TourStandingsState:
    """Season standings screen."""

    def __init__(self, game):
        self.game   = game
        self.player = game.player

        self.font_title  = fonts.heading(34)
        self.font_hdr    = fonts.heading(15)
        self.font_medium = fonts.body(16)
        self.font_small  = fonts.body(14)
        self.font_large  = fonts.heading(22)

        self._scroll    = 0
        self._btn_hov   = None
        self._standings = self._build_standings()

        # Q-school event just finished if the current tournament is flagged
        t = game.current_tournament
        self._is_qschool = t is not None and getattr(t, "is_qschool", False)

        self._season_over = self._is_qschool or (
            self.player.events_this_season
            >= EVENTS_PER_SEASON.get(self.player.tour_level, 8)
        )
        self._promotion_info = self._check_promotion() if self._season_over else None

        # Table geometry
        self._tx = 50
        self._ty = 155
        self._tw = SCREEN_W - 100
        col_widths = [45, 220, 130, 100, 100]
        self._col_x = []
        cx = self._tx
        for w in col_widths:
            self._col_x.append(cx)
            cx += w

        # Buttons
        btn_w, btn_h = 280, 50
        if self._season_over:
            self._btn_next = pygame.Rect(
                SCREEN_W // 2 - btn_w // 2, SCREEN_H - 68, btn_w, btn_h)
        else:
            self._btn_next = pygame.Rect(
                SCREEN_W // 2 - btn_w // 2, SCREEN_H - 68, btn_w, btn_h)

        self._btn_menu = pygame.Rect(
            self._btn_next.right + 16, SCREEN_H - 68, 160, btn_h)

    # ── Standings builder ─────────────────────────────────────────────────────

    def _build_standings(self) -> list[dict]:
        from src.data.opponents_data import get_opponent_pool
        p    = self.player
        pool = get_opponent_pool(p.tour_level)

        entries = [{
            "name":        p.name,
            "is_player":   True,
            "nationality": p.nationality,
            "points":      p.season_points,
            "events":      p.events_this_season,
        }]
        for opp in pool:
            pts    = p.opp_season_points.get(opp.name, 0)
            played = min(p.events_this_season,
                         EVENTS_PER_SEASON.get(p.tour_level, 8))
            entries.append({
                "name":        opp.name,
                "is_player":   False,
                "nationality": opp.nationality,
                "points":      pts,
                "events":      played,
            })

        return sorted(entries, key=lambda e: (-e["points"], e["name"]))

    def _check_promotion(self) -> dict:
        """Determine promotion/Q-school result at season end."""
        p = self.player

        # ── Q-school result ───────────────────────────────────────────────────
        if self._is_qschool:
            t   = self.game.current_tournament
            pos = t.get_player_position() if t else 999
            if pos <= 15:
                return {
                    "promoted":  True,
                    "new_level": 5,
                    "message":   f"Q-School Passed ({self._ordinal(pos)})! "
                                 f"Promoted to the World Tour!",
                }
            field = len(t.opponents) + 1 if t else 31
            remaining = max(0, self.player.qschool_attempts_remaining)
            if remaining > 0:
                tail = (f" {remaining} attempt{'s' if remaining != 1 else ''} "
                        f"remaining this season.")
            else:
                tail = " No attempts remaining — play another Tour 4 season to re-qualify."
            return {
                "promoted": False,
                "message":  f"Q-School missed — finished {self._ordinal(pos)} "
                            f"of {field}. Top 15 needed.{tail}",
            }

        # ── Normal season end ─────────────────────────────────────────────────
        threshold = PROMOTION_THRESHOLD.get(p.tour_level)
        if threshold is None:
            return {"promoted": False, "message": "You are on the Grand Tour!"}

        player_pos = next(
            (i + 1 for i, e in enumerate(self._standings) if e["is_player"]), 999)

        if player_pos > threshold:
            return {
                "promoted": False,
                "message":  f"Finished {self._ordinal(player_pos)} — "
                            f"top {threshold} needed for promotion.",
            }

        # Player is inside the promotion threshold
        next_lvl  = p.tour_level + 1
        next_name = TOUR_DISPLAY_NAMES.get(next_lvl, "Next Tour")

        # Tour 4 → 5: must pass Q-school
        if p.tour_level == 4:
            return {
                "qschool_qualified": True,
                "message": f"Top {threshold} finish! You've earned a place in "
                           f"the Q-School Qualifier.",
            }

        # Tour 5 → 6: also need world ranking ≤ 50
        if p.tour_level == 5 and p.world_rank > 50:
            return {
                "promoted": False,
                "message":  f"Top {threshold} achieved but World Ranking "
                            f"#{p.world_rank} too low — need top 50.",
            }

        return {
            "promoted":  True,
            "new_level": next_lvl,
            "message":   f"Promoted to the {next_name}!",
        }

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            p = event.pos
            self._btn_hov = (
                "next" if self._btn_next.collidepoint(p) else
                "menu" if self._btn_menu.collidepoint(p) else None
            )

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self._btn_next.collidepoint(event.pos):
                    self._on_next()
                elif self._btn_menu.collidepoint(event.pos):
                    self._go_menu()
            elif event.button == 4:
                self._scroll = max(0, self._scroll - 3)
            elif event.button == 5:
                mx = max(0, len(self._standings) - MAX_ROWS)
                self._scroll = min(mx, self._scroll + 3)

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._on_next()
            elif event.key == pygame.K_ESCAPE:
                self._go_menu()
            elif event.key == pygame.K_UP:
                self._scroll = max(0, self._scroll - 1)
            elif event.key == pygame.K_DOWN:
                mx = max(0, len(self._standings) - MAX_ROWS)
                self._scroll = min(mx, self._scroll + 1)

    def _on_next(self):
        # Check win condition before proceeding
        if self.player.has_won_game():
            from src.states.hall_of_fame import HallOfFameState
            self.game.change_state(HallOfFameState(self.game))
            return
        if self._season_over:
            self._handle_season_end()
        else:
            self._play_next_event()

    def _handle_season_end(self):
        p    = self.player
        info = self._promotion_info or {}

        if info.get("promoted"):
            p.tour_level                   = info["new_level"]
            p.qschool_pending              = False
            p.qschool_attempts_remaining   = 0
        elif info.get("qschool_qualified"):
            # First-time qualification from a Tour 4 season finish.
            p.qschool_pending              = True
            p.qschool_attempts_remaining   = 2
        elif self._is_qschool and not info.get("promoted"):
            # Failed Q-School. If an attempt remains, let the player try again
            # without replaying the whole season; otherwise they must re-earn
            # qualification via another top-5 Tour 4 season.
            if p.qschool_attempts_remaining > 0:
                p.qschool_pending = True

        p.reset_season()
        self.game.current_tournament = None
        self._play_next_event()

    def _play_next_event(self):
        from src.states.career_hub import CareerHubState
        self.game.change_state(CareerHubState(self.game))

    def _go_menu(self):
        from src.states.main_menu import MainMenuState
        self.game.change_state(MainMenuState(self.game))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        pass

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)
        cx = SCREEN_W // 2
        p  = self.player

        tour_name  = TOUR_DISPLAY_NAMES.get(p.tour_level, "Tour")
        total_evts = EVENTS_PER_SEASON.get(p.tour_level, 8)
        threshold  = PROMOTION_THRESHOLD.get(p.tour_level)

        # ── Title ─────────────────────────────────────────────────────────────
        title = self.font_title.render("Season Standings", True, C_WHITE)
        surface.blit(title, (cx - title.get_width() // 2, 14))

        sub = self.font_medium.render(
            f"{tour_name}  •  Season {p.season}  •  "
            f"{p.events_this_season} of {total_evts} events played",
            True, (100, 160, 80))
        surface.blit(sub, (cx - sub.get_width() // 2, 56))

        # World ranking + majors display
        if p.world_ranking_points > 0:
            from src.career.rankings import rank_label
            from src.career.majors import MAJOR_ORDER
            rank_str = rank_label(p.world_rank)
            maj_str  = f"  •  Majors: {len(p.majors_won)}/4" if p.tour_level == 6 else ""
            rs = self.font_small.render(rank_str + maj_str, True,
                                        C_GOLD if p.world_rank <= 10 else C_GRAY)
            surface.blit(rs, (cx - rs.get_width() // 2, 76))

        # Promotion threshold hint
        if threshold and not self._is_qschool:
            if not self._season_over:
                if p.tour_level == 4:
                    th_txt = f"Top {threshold} qualify for Q-School at season end"
                elif p.tour_level == 5:
                    rank_ok = p.world_rank <= 50
                    th_txt  = (f"Top {threshold} + World Ranking ≤ 50 earn promotion"
                               + (f"  (you: #{p.world_rank})" if p.world_ranking_points > 0 else ""))
                else:
                    th_txt = f"Top {threshold} earn promotion at season end"
            else:
                th_txt = (self._promotion_info or {}).get("message", "")
            th_col = C_GOLD if self._season_over else (100, 150, 80)
            th_s   = self.font_medium.render(th_txt, True, th_col)
            surface.blit(th_s, (cx - th_s.get_width() // 2, 84))

        # Season-over banner
        if self._season_over and self._promotion_info:
            info    = self._promotion_info
            good    = info.get("promoted") or info.get("qschool_qualified")
            ban_col = C_GREEN if good else C_RED
            ban_s   = self.font_large.render(info["message"], True, ban_col)
            surface.blit(ban_s, (cx - ban_s.get_width() // 2, 110))

        # ── Table ─────────────────────────────────────────────────────────────
        self._draw_table(surface, threshold)

        # ── Buttons ───────────────────────────────────────────────────────────
        if self._season_over:
            info = self._promotion_info or {}
            if self._is_qschool:
                next_lbl = ("To World Tour  >" if info.get("promoted")
                            else "Back to Continental Tour  >")
            elif info.get("qschool_qualified"):
                next_lbl = "To Q-School Qualifier  >"
            elif info.get("promoted"):
                next_lbl = "Start Next Tour  >"
            else:
                next_lbl = "Start New Season  >"
        else:
            event_n = p.events_this_season + 1
            next_lbl = f"Play Event {event_n}  >"

        next_bg = C_BTN_HOV if self._btn_hov == "next" else C_BTN
        pygame.draw.rect(surface, next_bg, self._btn_next, border_radius=8)
        pygame.draw.rect(surface, C_GREEN,  self._btn_next, 2, border_radius=8)
        nl = self.font_medium.render(next_lbl, True, C_WHITE)
        surface.blit(nl, nl.get_rect(center=self._btn_next.center))

        menu_bg = C_BTN_RED_H if self._btn_hov == "menu" else C_BTN_RED
        pygame.draw.rect(surface, menu_bg, self._btn_menu, border_radius=8)
        pygame.draw.rect(surface, C_RED,   self._btn_menu, 2, border_radius=8)
        ml = self.font_small.render("Main Menu", True, C_WHITE)
        surface.blit(ml, ml.get_rect(center=self._btn_menu.center))

        if len(self._standings) > MAX_ROWS:
            hint = self.font_small.render("↑↓ / Scroll to see more", True, C_GRAY)
            surface.blit(hint, (cx - hint.get_width() // 2,
                                self._btn_next.top - 20))

    def _draw_table(self, surface, threshold):
        tx = self._tx
        ty = self._ty if not self._season_over else self._ty + 28
        tw = self._tw
        col = self._col_x

        # Header
        pygame.draw.rect(surface, C_HDR,
                         pygame.Rect(tx, ty, tw, 24), border_radius=4)
        for i, h in enumerate(["Pos", "Name", "Nationality",
                                "Events", "Points"]):
            s = self.font_hdr.render(h, True, (150, 200, 120))
            surface.blit(s, (col[i] + 4, ty + 4))

        total_in_table = len(self._standings)
        visible = self._standings[self._scroll: self._scroll + MAX_ROWS]
        for row_i, entry in enumerate(visible):
            real_pos = self._scroll + row_i + 1
            ry       = ty + 24 + row_i * ROW_H
            is_pl    = entry["is_player"]
            in_promo = threshold and real_pos <= threshold
            is_last  = is_pl and real_pos == total_in_table

            # Row background
            if is_pl:
                pygame.draw.rect(surface, C_PLAYER_BG,
                                 pygame.Rect(tx, ry, tw, ROW_H - 1),
                                 border_radius=2)
                pygame.draw.rect(surface, C_PLAYER_BD,
                                 pygame.Rect(tx, ry, tw, ROW_H - 1), 1,
                                 border_radius=2)
            elif in_promo:
                pygame.draw.rect(surface, C_PROMO,
                                 pygame.Rect(tx, ry, tw, ROW_H - 1))
            elif row_i % 2 == 0:
                pygame.draw.rect(surface, (16, 24, 16),
                                 pygame.Rect(tx, ry, tw, ROW_H - 1))

            tc = C_WHITE if is_pl else (200, 210, 200)

            surface.blit(self.font_small.render(str(real_pos), True, tc),
                         (col[0] + 4, ry + 3))

            name_str = ("★ " + entry["name"]) if is_pl else entry["name"]
            if is_last:
                name_str += "   — last place"
            name_col = (210, 120, 120) if is_last else tc
            surface.blit(self.font_small.render(name_str, True, name_col),
                         (col[1] + 4, ry + 3))

            surface.blit(self.font_small.render(entry["nationality"], True, C_GRAY),
                         (col[2] + 4, ry + 3))

            surface.blit(self.font_small.render(str(entry["events"]), True, tc),
                         (col[3] + 4, ry + 3))

            pts_col = C_GOLD if is_pl else (180, 180, 180)
            surface.blit(self.font_small.render(str(entry["points"]), True, pts_col),
                         (col[4] + 4, ry + 3))

        # Promotion cut line
        if threshold and self._scroll <= threshold <= self._scroll + MAX_ROWS:
            cut_y = ty + 24 + (threshold - self._scroll) * ROW_H
            pygame.draw.line(surface, C_GOLD,
                             (tx, cut_y), (tx + tw, cut_y), 2)
            lbl = self.font_small.render("── promotion line ──", True, C_GOLD)
            surface.blit(lbl, (tx + tw // 2 - lbl.get_width() // 2, cut_y + 1))

    @staticmethod
    def _ordinal(n: int) -> str:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(
            n % 10 if n % 100 not in (11, 12, 13) else 0, "th")
        return f"{n}{suffix}"
