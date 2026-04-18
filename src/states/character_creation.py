"""
CharacterCreationState — name your golfer, choose nationality, distribute stat points.

Layout
------
  Left  : Name text input  •  Nationality selector
  Right : 6-stat attribute panel with 30 bonus points to spend
  Bottom: Start Career button
"""

import pygame

from src.career.player import NATIONALITIES, STAT_KEYS, BASE_STAT, MAX_STAT

# ── Colours ───────────────────────────────────────────────────────────────────
C_BG        = (  6,  12,   6)
C_PANEL     = ( 18,  26,  18)
C_PANEL_HDR = ( 28,  42,  28)
C_BORDER    = ( 58,  98,  58)
C_DIVIDER   = ( 38,  60,  38)
C_WHITE     = (255, 255, 255)
C_GRAY      = (130, 130, 130)
C_GOLD      = (210, 170,  30)
C_GREEN     = ( 55, 185,  55)
C_RED       = (200,  55,  55)
C_BLUE      = ( 60, 130, 220)
C_INPUT_BG  = ( 22,  36,  22)
C_INPUT_ACT = ( 18,  50,  18)
C_BTN       = ( 28,  78,  28)
C_BTN_HOV   = ( 48, 120,  48)
C_BTN_DIS   = ( 60,  52,  42)   # warm desaturated — distinct from active greens
C_BTN_SML   = ( 38,  55,  38)
C_BTN_SML_H = ( 60,  90,  60)

from src.constants import SCREEN_W, SCREEN_H

BONUS_TOTAL = 30

# (stat_key, display_name, short_description)
STAT_INFO = [
    ("power",      "Power",      "Drive distance"),
    ("accuracy",   "Accuracy",   "Shot precision"),
    ("short_game", "Short Game", "Chipping & pitching"),
    ("putting",    "Putting",    "Green reading"),
    ("mental",     "Mental",     "Pressure handling"),
    ("fitness",    "Fitness",    "Season endurance"),
]


class CharacterCreationState:
    """Character creation screen."""

    def __init__(self, game):
        self.game = game

        self.font_title  = pygame.font.SysFont("arial", 38, bold=True)
        self.font_hdr    = pygame.font.SysFont("arial", 16, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 18)
        self.font_small  = pygame.font.SysFont("arial", 14)
        self.font_input  = pygame.font.SysFont("arial", 22)
        self.font_large  = pygame.font.SysFont("arial", 26, bold=True)

        # ── State ─────────────────────────────────────────────────────────────
        self._name        = ""
        self._name_active = True
        self._cursor_on   = True
        self._cursor_t    = 0.0

        self._nat_idx = 0
        self._bonuses = {k: 0 for k in STAT_KEYS}

        # ── Layout ────────────────────────────────────────────────────────────
        # Two panels side by side with a gap
        pw = 560                           # panel width
        ph = 510                           # panel height
        gap = 20
        total_w = pw * 2 + gap
        px0 = (SCREEN_W - total_w) // 2   # left panel x
        px1 = px0 + pw + gap              # right panel x
        py  = 100                          # panel y

        self._left_panel  = pygame.Rect(px0, py, pw, ph)
        self._right_panel = pygame.Rect(px1, py, pw, ph)

        # Name input box
        self._name_box = pygame.Rect(px0 + 16, py + 72, pw - 32, 42)

        # Nationality arrows + display
        ny = py + 170
        self._nat_box   = pygame.Rect(px0 + 16, ny, pw - 32, 42)
        self._nat_prev  = pygame.Rect(px0 + 16, ny, 42, 42)
        self._nat_next  = pygame.Rect(px0 + pw - 58, ny, 42, 42)

        # Stat rows (right panel)
        row_y0 = py + 90
        row_h  = 64
        self._stat_rects: list[dict] = []
        for i, (key, name, desc) in enumerate(STAT_INFO):
            ry = row_y0 + i * row_h
            minus_btn = pygame.Rect(px1 + pw - 90, ry + 14, 32, 32)
            plus_btn  = pygame.Rect(px1 + pw - 48, ry + 14, 32, 32)
            self._stat_rects.append({
                "key": key, "name": name, "desc": desc,
                "row_y": ry,
                "minus": minus_btn, "plus": plus_btn,
            })

        # Start Career button
        bw, bh = 300, 54
        self._btn_start = pygame.Rect(
            SCREEN_W // 2 - bw // 2, py + ph + 24, bw, bh)
        self._btn_start_hov = False

        # Back button
        self._btn_back = pygame.Rect(px0, py + ph + 24, 120, 36)
        self._btn_back_hov = False

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def _points_remaining(self):
        return BONUS_TOTAL - sum(self._bonuses.values())

    def _can_start(self):
        return self._name.strip() != ""

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self._on_move(event.pos)
        elif event.type == pygame.KEYDOWN:
            if self._name_active:
                self._handle_name_key(event)
            if event.key == pygame.K_ESCAPE:
                self._go_back()

    def _on_move(self, pos):
        self._btn_start_hov = self._btn_start.collidepoint(pos) and self._can_start()
        self._btn_back_hov  = self._btn_back.collidepoint(pos)

    def _on_click(self, pos):
        # Name box focus
        self._name_active = self._name_box.collidepoint(pos)

        # Nationality navigation
        if self._nat_prev.collidepoint(pos):
            self._nat_idx = (self._nat_idx - 1) % len(NATIONALITIES)
        elif self._nat_next.collidepoint(pos):
            self._nat_idx = (self._nat_idx + 1) % len(NATIONALITIES)

        # Stat buttons
        for row in self._stat_rects:
            if row["minus"].collidepoint(pos):
                if self._bonuses[row["key"]] > 0:
                    self._bonuses[row["key"]] -= 1
            elif row["plus"].collidepoint(pos):
                if (self._points_remaining > 0 and
                        self._bonuses[row["key"]] < (MAX_STAT - BASE_STAT)):
                    self._bonuses[row["key"]] += 1

        # Start
        if self._btn_start.collidepoint(pos) and self._can_start():
            self._start_career()

        # Back
        if self._btn_back.collidepoint(pos):
            self._go_back()

    def _handle_name_key(self, event):
        if event.key == pygame.K_BACKSPACE:
            self._name = self._name[:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_TAB):
            self._name_active = False
        elif len(self._name) < 20:
            if event.unicode and event.unicode.isprintable():
                self._name += event.unicode

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start_career(self):
        from src.career.player import Player
        from src.states.career_hub import CareerHubState

        name        = self._name.strip()
        nationality = NATIONALITIES[self._nat_idx]

        player = Player(name, nationality)
        player.set_bonus_stats(self._bonuses)
        self.game.player = player

        self.game.change_state(CareerHubState(self.game))

    def _go_back(self):
        from src.states.main_menu import MainMenuState
        self.game.change_state(MainMenuState(self.game))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self._cursor_t += dt
        if self._cursor_t >= 0.5:
            self._cursor_t = 0.0
            self._cursor_on = not self._cursor_on

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)

        cx = SCREEN_W // 2
        title = self.font_title.render("Create Your Golfer", True, (168, 224, 88))
        surface.blit(title, (cx - title.get_width() // 2, 50))

        self._draw_left_panel(surface)
        self._draw_right_panel(surface)
        self._draw_bottom_buttons(surface)

    def _draw_left_panel(self, surface):
        r = self._left_panel
        pygame.draw.rect(surface, C_PANEL,  r, border_radius=8)
        pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=8)

        # Panel header
        pygame.draw.rect(surface, C_PANEL_HDR,
                         pygame.Rect(r.x, r.y, r.width, 46), border_radius=8)
        lbl = self.font_hdr.render("GOLFER PROFILE", True, (160, 200, 120))
        surface.blit(lbl, (r.x + 16, r.y + 14))

        # ── Name ──────────────────────────────────────────────────────────────
        nl = self.font_small.render("NAME", True, C_GRAY)
        surface.blit(nl, (r.x + 16, r.y + 56))

        nb = self._name_box
        bg = C_INPUT_ACT if self._name_active else C_INPUT_BG
        pygame.draw.rect(surface, bg, nb, border_radius=5)
        bord_c = C_GREEN if self._name_active else C_BORDER
        pygame.draw.rect(surface, bord_c, nb, 2, border_radius=5)

        display = self._name
        if self._name_active and self._cursor_on:
            display += "|"
        elif self._name_active:
            display += " "

        if not display.strip():
            ph = self.font_input.render("Enter your name…", True, (60, 80, 60))
            surface.blit(ph, (nb.x + 10, nb.y + (nb.height - ph.get_height()) // 2))
        else:
            ns = self.font_input.render(display, True, C_WHITE)
            surface.blit(ns, (nb.x + 10, nb.y + (nb.height - ns.get_height()) // 2))

        # ── Nationality ───────────────────────────────────────────────────────
        nl2 = self.font_small.render("NATIONALITY", True, C_GRAY)
        surface.blit(nl2, (r.x + 16, r.y + 154))

        nat_box = self._nat_box
        pygame.draw.rect(surface, C_INPUT_BG, nat_box, border_radius=5)
        pygame.draw.rect(surface, C_BORDER,   nat_box, 1, border_radius=5)

        # Prev / Next arrows
        for btn, txt in [(self._nat_prev, "◀"), (self._nat_next, "▶")]:
            pygame.draw.rect(surface, C_BTN_SML, btn, border_radius=4)
            pygame.draw.rect(surface, C_BORDER,  btn, 1, border_radius=4)
            ts = self.font_medium.render(txt, True, C_WHITE)
            surface.blit(ts, ts.get_rect(center=btn.center))

        nat_name = NATIONALITIES[self._nat_idx]
        ns2 = self.font_medium.render(nat_name, True, C_WHITE)
        surface.blit(ns2, ns2.get_rect(center=nat_box.center))

        # ── Tip ───────────────────────────────────────────────────────────────
        tip = self.font_small.render("Click name box, then type your name",
                                     True, (70, 100, 60))
        surface.blit(tip, (r.x + 16, r.y + 240))

    def _draw_right_panel(self, surface):
        r = self._right_panel
        pygame.draw.rect(surface, C_PANEL,  r, border_radius=8)
        pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=8)

        # Panel header
        pygame.draw.rect(surface, C_PANEL_HDR,
                         pygame.Rect(r.x, r.y, r.width, 46), border_radius=8)
        lbl = self.font_hdr.render("ATTRIBUTES", True, (160, 200, 120))
        surface.blit(lbl, (r.x + 16, r.y + 14))

        pts = self._points_remaining
        pts_color = C_GOLD if pts > 0 else C_GREEN
        pts_s = self.font_hdr.render(f"Points remaining: {pts}", True, pts_color)
        surface.blit(pts_s, (r.right - pts_s.get_width() - 16, r.y + 14))

        # ── Stat rows ─────────────────────────────────────────────────────────
        for row in self._stat_rects:
            key    = row["key"]
            bonus  = self._bonuses[key]
            total  = BASE_STAT + bonus
            ry     = row["row_y"]

            # Row background (subtle)
            row_rect = pygame.Rect(r.x + 8, ry + 6, r.width - 16, 52)
            pygame.draw.rect(surface, (22, 34, 22), row_rect, border_radius=5)

            # Stat name + description
            name_s = self.font_medium.render(row["name"], True, C_WHITE)
            desc_s = self.font_small.render(row["desc"], True, C_GRAY)
            surface.blit(name_s, (r.x + 18, ry + 10))
            surface.blit(desc_s, (r.x + 18, ry + 32))

            # Total value
            val_s = self.font_large.render(str(total), True, C_GOLD)
            surface.blit(val_s, (r.x + 190, ry + 16))

            # Progress bar (total out of MAX_STAT)
            bar_rect = pygame.Rect(r.x + 240, ry + 24, 200, 10)
            pygame.draw.rect(surface, (38, 55, 38), bar_rect, border_radius=3)
            fill_w = int(200 * total / MAX_STAT)
            if fill_w > 0:
                bar_color = (C_GREEN if bonus == 0
                             else C_GOLD if bonus < 15
                             else C_RED)
                pygame.draw.rect(surface, bar_color,
                                 pygame.Rect(bar_rect.x, bar_rect.y,
                                             fill_w, 10), border_radius=3)
            pygame.draw.rect(surface, C_DIVIDER, bar_rect, 1, border_radius=3)

            # -/+ buttons
            for btn, active in [(row["minus"], bonus > 0),
                                 (row["plus"],  self._points_remaining > 0
                                               and bonus < MAX_STAT - BASE_STAT)]:
                bg = C_BTN_SML if active else (30, 38, 30)
                tc = C_WHITE   if active else (60, 70, 60)
                pygame.draw.rect(surface, bg,        btn, border_radius=4)
                pygame.draw.rect(surface, C_DIVIDER, btn, 1, border_radius=4)
                sym = self.font_medium.render(
                    "−" if btn == row["minus"] else "+", True, tc)
                surface.blit(sym, sym.get_rect(center=btn.center))

    def _draw_bottom_buttons(self, surface):
        # Start button
        can = self._can_start()
        bg   = C_BTN_HOV if (self._btn_start_hov and can) else (C_BTN if can else C_BTN_DIS)
        bord = C_GREEN if can else C_DIVIDER
        pygame.draw.rect(surface, bg,   self._btn_start, border_radius=8)
        pygame.draw.rect(surface, bord, self._btn_start, 2, border_radius=8)
        lbl_txt  = "Start Career" if can else "Enter a name first"
        lbl_col  = C_WHITE if can else C_GRAY
        lbl = self.font_large.render(lbl_txt, True, lbl_col)
        surface.blit(lbl, lbl.get_rect(center=self._btn_start.center))

        # Back button
        bg2 = (50, 30, 30) if self._btn_back_hov else (35, 22, 22)
        pygame.draw.rect(surface, bg2,    self._btn_back, border_radius=6)
        pygame.draw.rect(surface, C_RED,  self._btn_back, 1, border_radius=6)
        bl = self.font_small.render("◀ Back", True, (200, 150, 150))
        surface.blit(bl, bl.get_rect(center=self._btn_back.center))
