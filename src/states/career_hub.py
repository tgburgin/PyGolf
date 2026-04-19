"""
CareerHubState — between-event career management screen.

Tabs
────
  0  Training & Equipment  — stat training + club upgrades
  1  Staff                 — hire/fire staff (unlocks Tour 4)
  2  Sponsors              — sponsor deals and active contract
  3  Career Stats          — stats table + achievements
"""

import pygame

from src.golf.club        import CLUB_SETS, CLUB_SET_ORDER
from src.golf.ball_types  import BALL_TYPES, BALL_ORDER, effect_summary as ball_effect_summary
from src.career.player    import STAT_KEYS, BASE_STAT, MAX_STAT, ACHIEVEMENTS
from src.career.tournament import TOUR_DISPLAY_NAMES, EVENTS_PER_SEASON
from src.career.staff      import STAFF_TYPES, STAFF_ORDER
from src.career.sponsorship import get_available_sponsors, is_target_met, progress_label
from src.constants          import SCREEN_W, SCREEN_H

CONTENT_X  = 15
CONTENT_Y  = 106   # below tab bar
CONTENT_W  = SCREEN_W - 30
CONTENT_H  = SCREEN_H - CONTENT_Y - 10

# ── Colours ───────────────────────────────────────────────────────────────────
C_BG         = ( 10,  16,  10)
C_PANEL      = ( 18,  28,  18)
C_BORDER     = ( 55,  90,  55)
C_HDR        = ( 28,  44,  28)
C_WHITE      = (255, 255, 255)
C_GRAY       = (130, 138, 120)
C_GREEN      = ( 55, 185,  55)
C_GOLD       = (210, 170,  30)
C_RED        = (200,  50,  50)
C_BTN        = ( 28,  75,  28)
C_BTN_HOV    = ( 50, 120,  50)
C_BTN_DIS    = ( 60,  52,  42)   # warm desaturated — distinct from active greens
C_BTN_PLAY   = ( 20,  88,  20)
C_BTN_PLAY_H = ( 40, 140,  40)
C_BTN_RED    = ( 78,  28,  28)
C_BTN_RED_H  = (120,  48,  48)
C_STAT_BAR   = ( 40, 120,  40)
C_STAT_STAFF = ( 40, 100, 170)   # staff bonus overlay
C_STAT_EMPTY = ( 38,  50,  38)
C_TAB        = ( 22,  38,  22)
C_TAB_ACT    = ( 38,  70,  38)
C_TAB_HOV    = ( 32,  56,  32)
C_ACH_DONE   = ( 30,  70,  30)
C_ACH_LOCK   = ( 30,  36,  30)
C_SPONSOR_ACT= ( 28,  50,  78)

STAT_LABELS = {
    "power":      "Power",
    "accuracy":   "Accuracy",
    "short_game": "Short Game",
    "putting":    "Putting",
    "mental":     "Mental",
    "fitness":    "Fitness",
}

TAB_LABELS = ["Training & Equipment", "Staff", "Sponsors", "Career Stats"]


class CareerHubState:
    """Career hub — tabbed screen accessed between every tour event."""

    def __init__(self, game):
        self.game   = game
        self.player = game.player

        self.font_title = pygame.font.SysFont("arial", 30, bold=True)
        self.font_hdr   = pygame.font.SysFont("arial", 15, bold=True)
        self.font_med   = pygame.font.SysFont("arial", 14)
        self.font_small = pygame.font.SysFont("arial", 12)

        self._tab  = 0
        self._hov  = None
        self._msg  = ""
        self._msg_timer = 0.0

        self._new_achievements: list[str] = []   # popped one by one in update

        self._build_tab_rects()
        self._build_tab0_rects()
        self._build_tab1_rects()
        self._build_tab2_rects()

        # Losing-streak nudge: if the last three rounds were all well over par,
        # point the player at their weakest stat. Shown once per hub entry.
        self._maybe_flash_losing_streak()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_tab_rects(self):
        """Tabs + persistent Play button in the tab bar."""
        tab_w  = 200
        tab_h  = 32
        tab_y  = 68
        self._tab_rects = []
        for i, _ in enumerate(TAB_LABELS):
            self._tab_rects.append(
                pygame.Rect(CONTENT_X + i * (tab_w + 4), tab_y, tab_w, tab_h))

        # Persistent Play Event button (right side of tab bar)
        self._btn_play = pygame.Rect(SCREEN_W - 220, tab_y, 205, tab_h)

    def _build_tab0_rects(self):
        """Training panel + Equipment panel + event summary."""
        ty = CONTENT_Y
        # Training panel (left)
        self._train_panel = pygame.Rect(CONTENT_X, ty, 390, CONTENT_H)
        self._train_btns: list[tuple[str, pygame.Rect]] = []
        btn_y = ty + 46
        for key in STAT_KEYS:
            r = pygame.Rect(CONTENT_X + 328, btn_y + 2, 52, 26)
            self._train_btns.append((key, r))
            btn_y += 76

        # Equipment panel (right): clubs (compact) + balls stacked below
        self._equip_panel = pygame.Rect(SCREEN_W - CONTENT_X - 390, ty, 390, CONTENT_H)
        self._equip_btns: list[tuple[str, pygame.Rect]] = []
        ey = ty + 40
        for set_name in CLUB_SET_ORDER[1:]:
            ex = self._equip_panel.x
            r  = pygame.Rect(ex + 295, ey + 4, 84, 24)
            self._equip_btns.append((set_name, r))
            ey += 48

        # Balls section starts after clubs + small header gap
        self._balls_section_y = ey + 24
        self._ball_btns: list[tuple[str, pygame.Rect]] = []
        by = self._balls_section_y + 22
        for ball_id in BALL_ORDER:
            ex = self._equip_panel.x
            r  = pygame.Rect(ex + 295, by + 4, 84, 24)
            self._ball_btns.append((ball_id, r))
            by += 34

        # Event info panel (centre)
        cx = CONTENT_X + 390 + 10
        cw = (SCREEN_W - CONTENT_X - 390 - 10) - (390 + 10)
        self._event_panel = pygame.Rect(cx, ty, cw, CONTENT_H)

    def _build_tab1_rects(self):
        """2×2 grid of staff hire cards."""
        card_w, card_h = 590, 145
        gx, gy = 20, 16
        x0 = CONTENT_X
        y0 = CONTENT_Y
        self._staff_cards: list[tuple[str, pygame.Rect]] = []
        self._staff_btn:   list[tuple[str, pygame.Rect]] = []
        for i, sid in enumerate(STAFF_ORDER):
            col = i % 2
            row = i // 2
            r = pygame.Rect(x0 + col * (card_w + gx),
                            y0 + row * (card_h + gy),
                            card_w, card_h)
            self._staff_cards.append((sid, r))
            btn_r = pygame.Rect(r.right - 110, r.bottom - 34, 100, 26)
            self._staff_btn.append((sid, btn_r))

    def _build_tab2_rects(self):
        """Sponsor list (left) + active contract (right)."""
        self._sponsor_list_panel = pygame.Rect(CONTENT_X, CONTENT_Y, 760, CONTENT_H)
        self._sponsor_active_panel = pygame.Rect(
            CONTENT_X + 780, CONTENT_Y, CONTENT_W - 780, CONTENT_H)
        # Accept buttons per sponsor — rebuilt in draw (dynamic list length)
        self._sponsor_btns: list[tuple[str, pygame.Rect]] = []

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._hov = self._hit_test(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._hit_test(event.pos)
            if hit is None:
                return
            if hit == "play":
                self._play_event()
            elif hit.startswith("tab:"):
                self._tab = int(hit[4:])
                self._build_tab2_rects()   # refresh sponsor button positions
            elif hit.startswith("train:"):
                self._do_train(hit[6:])
            elif hit.startswith("buy:"):
                self._do_buy(hit[4:])
            elif hit.startswith("ball_buy:"):
                self._do_ball_buy(hit[len("ball_buy:"):])
            elif hit.startswith("ball_select:"):
                self._do_ball_select(hit[len("ball_select:"):])
            elif hit.startswith("hire:"):
                self._do_hire(hit[5:])
            elif hit.startswith("fire:"):
                self._do_fire(hit[5:])
            elif hit.startswith("sponsor:"):
                self._do_accept_sponsor(hit[8:])
            elif hit == "drop_sponsor":
                self.player.drop_sponsor()
                self._flash("Sponsor contract dropped.")

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._play_event()
            elif event.key == pygame.K_TAB:
                self._tab = (self._tab + 1) % len(TAB_LABELS)

    def _hit_test(self, pos) -> str | None:
        if self._btn_play.collidepoint(pos):
            return "play"
        for i, r in enumerate(self._tab_rects):
            if r.collidepoint(pos):
                return f"tab:{i}"
        if self._tab == 0:
            for key, r in self._train_btns:
                if r.collidepoint(pos):
                    return f"train:{key}"
            for sn, r in self._equip_btns:
                if r.collidepoint(pos):
                    return f"buy:{sn}"
            for bid, r in self._ball_btns:
                if r.collidepoint(pos):
                    owned = bid in self.player.owned_balls
                    return f"ball_select:{bid}" if owned else f"ball_buy:{bid}"
        elif self._tab == 1:
            for sid, r in self._staff_btn:
                if r.collidepoint(pos):
                    hired = sid in self.player.hired_staff
                    return f"fire:{sid}" if hired else f"hire:{sid}"
        elif self._tab == 2:
            for sid, r in self._sponsor_btns:
                if r.collidepoint(pos):
                    return f"sponsor:{sid}"
            # Drop sponsor button
            ds = getattr(self, "_btn_drop_sponsor", None)
            if ds and ds.collidepoint(pos):
                return "drop_sponsor"
        return None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_train(self, key):
        p = self.player
        cost = p.training_cost(key)
        if cost is None:
            self._flash(f"{STAT_LABELS[key]} is already at maximum!")
            return
        if p.money < cost:
            self._flash(f"Need ${cost:,} to train {STAT_LABELS[key]}")
            return
        p.train_stat(key)
        self._flash(f"{STAT_LABELS[key]} improved to {p.stats[key]}! (${cost:,})")
        self._pop_new_achievements()

    def _do_buy(self, set_name):
        p    = self.player
        info = CLUB_SETS.get(set_name)
        if not info:
            return
        if info["min_tour"] > p.tour_level:
            self._flash(f"Requires Tour Level {info['min_tour']}")
            return
        cur = CLUB_SET_ORDER.index(p.club_set_name)
        tgt = CLUB_SET_ORDER.index(set_name)
        if tgt <= cur:
            self._flash("You already own equal or better clubs.")
            return
        if p.money < info["cost"]:
            self._flash(f"Need ${info['cost']:,} for {info['label']}")
            return
        p.upgrade_club_set(set_name)
        self._flash(f"Purchased {info['label']}!")
        self._pop_new_achievements()

    def _do_ball_buy(self, ball_id):
        p    = self.player
        info = BALL_TYPES.get(ball_id)
        if not info:
            return
        if info["min_tour"] > p.tour_level:
            self._flash(f"Requires Tour Level {info['min_tour']}")
            return
        if p.money < info["cost"]:
            self._flash(f"Need ${info['cost']:,} for {info['label']}")
            return
        if p.buy_ball(ball_id):
            self._flash(f"Bought {info['label']}! Now in play.")

    def _do_ball_select(self, ball_id):
        info = BALL_TYPES.get(ball_id, {})
        if self.player.select_ball(ball_id):
            self._flash(f"Switched to {info.get('label', ball_id)}.")

    def _do_hire(self, sid):
        p    = self.player
        info = STAFF_TYPES.get(sid)
        if not info:
            return
        if info["min_tour"] > p.tour_level:
            self._flash(f"Requires Tour Level {info['min_tour']} (Continental Tour)")
            return
        if p.money < info["hire_cost"]:
            self._flash(f"Need ${info['hire_cost']:,} to hire {info['label']}")
            return
        if p.hire_staff(sid):
            self._flash(f"Hired {info['label']}! (${info['hire_cost']:,})")
            self._pop_new_achievements()
        else:
            self._flash(f"Already hired {info['label']}")

    def _do_fire(self, sid):
        info = STAFF_TYPES.get(sid, {})
        self.player.fire_staff(sid)
        self._flash(f"Released {info.get('label', sid)}.")

    def _do_accept_sponsor(self, sponsor_id):
        p = self.player
        if p.active_sponsor is not None:
            self._flash("You already have an active sponsor. Drop it first.")
            return
        from src.career.sponsorship import SPONSORS
        deal = next((s for s in SPONSORS if s["id"] == sponsor_id), None)
        if deal is None:
            return
        if deal["min_tour"] > p.tour_level:
            self._flash(f"Requires Tour Level {deal['min_tour']}")
            return
        p.accept_sponsor(deal)
        self._flash(f"Signed with {deal['name']}! +${deal['signing_fee']:,} signing fee.")

    def _play_event(self):
        from src.data.tours_data import get_courses_for_tour
        from src.career.tour import get_tour_id
        from src.states.golf_round import GolfRoundState
        from src.career.tournament import Tournament, EVENTS_PER_SEASON
        from src.data.opponents_data import get_opponent_pool
        from src.career.majors import is_major_event, get_major_course, MAJORS
        import random

        p = self.player

        # ── Q-School Qualifier ────────────────────────────────────────────────
        if p.qschool_pending:
            courses = get_courses_for_tour(get_tour_id(5))   # World Tour courses
            if not courses:
                courses = get_courses_for_tour(get_tour_id(4))
            if not courses:
                self._flash("No course available for Q-School!")
                return
            course = random.choice(courses)
            opps   = get_opponent_pool(5)   # tougher World Tour field
            # Seed differs per attempt so the second Q-School isn't a replay
            # of the first — but still reproducible from the save file.
            attempt_idx = max(0, 2 - p.qschool_attempts_remaining)
            qs_seed = hash((p.name, p.season, "qschool", attempt_idx)) & 0xFFFFFFFF
            t = Tournament(
                "Q-School Qualifier", 4,
                [course.get_hole(i).par for i in range(course.total_holes)],
                opps, is_qschool=True,
                event_number=1, total_events=1,
                rng_seed=qs_seed,
                course_name=course.name)
            p.qschool_pending = False
            if p.qschool_attempts_remaining > 0:
                p.qschool_attempts_remaining -= 1
            self.game.current_tournament = t
            self.game.change_state(GolfRoundState(self.game, course, 0, []))
            return

        # ── Normal event ──────────────────────────────────────────────────────
        tour_id = get_tour_id(p.tour_level)
        total   = EVENTS_PER_SEASON.get(p.tour_level, 8)
        event_n = p.events_this_season + 1

        # Check if this event is a Major
        major_id = is_major_event(p.tour_level, event_n)

        if major_id:
            course = get_major_course(major_id)
            if course is None:
                self._flash("Major course not found — using random course.")
                major_id = None
        if not major_id or course is None:
            courses = get_courses_for_tour(tour_id)
            if not courses:
                self._flash("No courses found for this tour!")
                return
            course = random.choice(courses)

        opps = get_opponent_pool(p.tour_level)

        ev_seed = hash((p.name, p.season, p.tour_level,
                        event_n, major_id or "")) & 0xFFFFFFFF

        if major_id:
            name = MAJORS[major_id]["name"]
            prize_fund = MAJORS[major_id]["prize_fund"]
            t = Tournament(
                name, p.tour_level,
                [course.get_hole(i).par for i in range(course.total_holes)],
                opps, is_major=True, event_number=event_n, total_events=total,
                major_id=major_id, major_prize_fund=prize_fund,
                rng_seed=ev_seed, course_name=course.name)
        else:
            _NAMES = {1: "Amateur", 2: "Challenger", 3: "Development",
                      4: "Continental", 5: "World", 6: "Grand"}
            name = f"Event {event_n} — {_NAMES.get(p.tour_level, 'Tour')} Circuit"
            t = Tournament(
                name, p.tour_level,
                [course.get_hole(i).par for i in range(course.total_holes)],
                opps, is_major=False, event_number=event_n, total_events=total,
                rng_seed=ev_seed, course_name=course.name)

        self.game.current_tournament = t
        self.game.change_state(GolfRoundState(self.game, course, 0, []))

    def _flash(self, msg: str):
        self._msg       = msg
        self._msg_timer = 3.5

    def _maybe_flash_losing_streak(self) -> None:
        """Flash a helpful nudge if the player's last three rounds were all
        significantly over par. Picks out their weakest non-maxed stat."""
        p = self.player
        if p is None:
            return
        log = p.career_log or []
        if len(log) < 3:
            return
        recent = log[-3:]
        # "Struggling" = every recent round at least +3 over par.
        if not all(r.get("diff", 0) >= 3 for r in recent):
            return

        # Weakest non-maxed stat.
        pool = [(p.stats.get(k, 50), k) for k in STAT_KEYS
                if p.stats.get(k, 50) < MAX_STAT]
        if not pool:
            return
        pool.sort()
        _, weakest = pool[0]
        label = STAT_LABELS.get(weakest, weakest.title())
        self._flash(f"Struggling? Training {label} would help most right now.")

    def _pop_new_achievements(self):
        """Collect any newly-unlocked achievements for banner display."""
        p = self.player
        known = set(getattr(self, "_known_achievements", []))
        for ach in p.achievements:
            if ach not in known:
                self._new_achievements.append(ach)
        self._known_achievements = list(p.achievements)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self._msg_timer > 0:
            self._msg_timer -= dt
        if self._new_achievements and self._msg_timer <= 0:
            ach_id = self._new_achievements.pop(0)
            info   = ACHIEVEMENTS.get(ach_id, {})
            self._flash(f"Achievement unlocked: {info.get('label', ach_id)}!")

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)
        p  = self.player
        cx = SCREEN_W // 2

        # ── Title row ─────────────────────────────────────────────────────────
        title = self.font_title.render("Career Hub", True, C_WHITE)
        surface.blit(title, (cx - title.get_width() // 2, 10))

        tour_name = TOUR_DISPLAY_NAMES.get(p.tour_level, "Tour")
        event_n   = p.events_this_season + 1
        total_evts= EVENTS_PER_SEASON.get(p.tour_level, 8)
        sub = self.font_med.render(
            f"{tour_name}  •  Season {p.season}  •  "
            f"Event {event_n}/{total_evts}  •  ${p.money:,}",
            True, (90, 160, 80))
        surface.blit(sub, (cx - sub.get_width() // 2, 44))

        # ── Tab bar ───────────────────────────────────────────────────────────
        recommended_tab = self._recommended_tab()
        for i, label in enumerate(TAB_LABELS):
            r = self._tab_rects[i]
            active = (i == self._tab)
            hov    = (self._hov == f"tab:{i}")
            bg = C_TAB_ACT if active else (C_TAB_HOV if hov else C_TAB)
            pygame.draw.rect(surface, bg, r, border_radius=4)
            # Recommended (but not currently open) tab gets a gold accent
            # underline so the player's eye is drawn to what's worth doing.
            if recommended_tab == i and not active:
                accent = pygame.Rect(r.x + 4, r.bottom - 3, r.width - 8, 3)
                pygame.draw.rect(surface, C_GOLD, accent, border_radius=2)
            pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=4)
            icon_col = C_WHITE if active else C_GRAY
            ts = self.font_med.render(label, True, icon_col)
            # Icon + label, group-centered together
            icon_w, gap = 18, 6
            total_w = icon_w + gap + ts.get_width()
            group_x = r.centerx - total_w // 2
            self._draw_tab_icon(surface, i,
                                group_x, r.centery - 8, icon_col)
            surface.blit(ts, (group_x + icon_w + gap,
                              r.centery - ts.get_height() // 2))

        # Play Event button (persistent)
        bg = C_BTN_PLAY_H if self._hov == "play" else C_BTN_PLAY
        pygame.draw.rect(surface, bg, self._btn_play, border_radius=4)
        pygame.draw.rect(surface, C_GREEN, self._btn_play, 1, border_radius=4)
        if p.qschool_pending:
            play_label = "Play Q-School  →"
        else:
            play_label = f"Play Event {event_n}  →"
        pl = self.font_hdr.render(play_label, True, C_WHITE)
        surface.blit(pl, pl.get_rect(center=self._btn_play.center))

        # ── Tab content ───────────────────────────────────────────────────────
        if self._tab == 0:
            self._draw_tab0(surface)
        elif self._tab == 1:
            self._draw_tab1(surface)
        elif self._tab == 2:
            self._draw_tab2(surface)

        # Flash message. Drawn LAST as a rounded banner floating just inside
        # the top of the content area so it can't collide with the tab row
        # (an earlier 62 px y collided with the tabs starting at y=68).
        # Transient — only visible while _msg_timer > 0.
        if self._msg_timer > 0:
            ms = self.font_med.render(self._msg, True, C_GOLD)
            pad_x, pad_h = 18, 26
            banner = pygame.Rect(
                cx - ms.get_width() // 2 - pad_x,
                CONTENT_Y + 4,
                ms.get_width() + pad_x * 2,
                pad_h)
            pygame.draw.rect(surface, (20, 28, 18), banner, border_radius=6)
            pygame.draw.rect(surface, C_GOLD,       banner, 1, border_radius=6)
            surface.blit(ms, ms.get_rect(center=banner.center))
        elif self._tab == 3:
            self._draw_tab3(surface)

    # ── Tab 0 — Training & Equipment ──────────────────────────────────────────

    def _draw_tab0(self, surface):
        self._draw_training_panel(surface)
        self._draw_event_panel(surface)
        self._draw_equipment_panel(surface)

    def _draw_training_panel(self, surface):
        p = self.player
        r = self._train_panel
        pygame.draw.rect(surface, C_PANEL, r, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=6)
        self._section_hdr(surface, "TRAINING", r.x, r.y, r.width)

        ty = r.y + 46
        for (key, btn_r) in self._train_btns:
            val         = p.stats[key]
            staff_bonus = p.staff_stat_bonus(key)
            cost        = p.training_cost(key)
            maxed       = (cost is None)
            label       = STAT_LABELS[key]

            # Stat label + value
            val_str = f"{label}: {val}" + (f" (+{staff_bonus})" if staff_bonus else "")
            ls = self.font_med.render(val_str, True, C_WHITE)
            surface.blit(ls, (r.x + 10, ty))

            # Bar
            bar_x, bar_y, bar_w, bar_h = r.x + 10, ty + 20, 300, 10
            pygame.draw.rect(surface, C_STAT_EMPTY,
                             pygame.Rect(bar_x, bar_y, bar_w, bar_h))
            fill_w = int(bar_w * (val - BASE_STAT) / (MAX_STAT - BASE_STAT))
            if fill_w > 0:
                pygame.draw.rect(surface, C_STAT_BAR,
                                 pygame.Rect(bar_x, bar_y, fill_w, bar_h))
            # Staff bonus overlay
            if staff_bonus > 0:
                staff_fill = int(bar_w * staff_bonus / (MAX_STAT - BASE_STAT))
                pygame.draw.rect(surface, C_STAT_STAFF,
                                 pygame.Rect(bar_x + fill_w, bar_y,
                                             min(staff_fill, bar_w - fill_w), bar_h))

            cost_txt = "MAX" if maxed else f"${cost:,}"
            cs = self.font_small.render(cost_txt, True,
                                        C_GRAY if maxed else C_GOLD)
            surface.blit(cs, (r.x + 10, ty + 36))

            # +1 button
            can = (not maxed) and p.money >= (cost or 0)
            hk  = f"train:{key}"
            bg  = (C_BTN_DIS if (maxed or not can)
                   else C_BTN_HOV if self._hov == hk else C_BTN)
            pygame.draw.rect(surface, bg, btn_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, btn_r, 1, border_radius=4)
            bl = self.font_small.render("+1", True,
                                        C_GRAY if (maxed or not can) else C_WHITE)
            surface.blit(bl, bl.get_rect(center=btn_r.center))
            ty += 76

    def _draw_event_panel(self, surface):
        p = self.player
        r = self._event_panel
        pygame.draw.rect(surface, C_PANEL, r, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=6)
        self._section_hdr(surface, "NEXT EVENT", r.x, r.y, r.width)

        cx = r.x + r.width // 2
        ty = r.y + 52

        event_n    = p.events_this_season + 1
        total_evts = EVENTS_PER_SEASON.get(p.tour_level, 8)
        tour_name  = TOUR_DISPLAY_NAMES.get(p.tour_level, "Tour")

        from src.career.majors import is_major_event, MAJORS
        major_id = is_major_event(p.tour_level, event_n)

        if p.qschool_pending:
            qs = self.font_title.render("Q-School Qualifier", True, C_GOLD)
            surface.blit(qs, (cx - qs.get_width() // 2, ty)); ty += 44
            qs2 = self.font_hdr.render(
                "Finish top 15 to earn your World Tour card!", True, C_WHITE)
            surface.blit(qs2, (cx - qs2.get_width() // 2, ty)); ty += 30
        else:
            en = self.font_title.render(f"Event {event_n} of {total_evts}", True, C_WHITE)
            surface.blit(en, (cx - en.get_width() // 2, ty)); ty += 44

        if not p.qschool_pending and major_id:
            major_info = MAJORS[major_id]
            ms = self.font_hdr.render(
                f"★ MAJOR: {major_info['name']}", True, C_GOLD)
            surface.blit(ms, (cx - ms.get_width() // 2, ty)); ty += 24
            mc = self.font_small.render(
                f"Prize fund: ${major_info['prize_fund']:,}  •  2 rounds", True, C_GOLD)
            surface.blit(mc, (cx - mc.get_width() // 2, ty)); ty += 20

        tn = self.font_med.render(tour_name, True, (100, 175, 80))
        surface.blit(tn, (cx - tn.get_width() // 2, ty)); ty += 36

        # Majors won tracker (Grand Tour)
        if p.tour_level == 6:
            from src.career.majors import MAJOR_ORDER
            won_count = len(p.majors_won)
            mw = self.font_small.render(
                f"Majors: {won_count}/4 won", True,
                C_GREEN if won_count == 4 else C_GOLD)
            surface.blit(mw, (cx - mw.get_width() // 2, ty)); ty += 18

        # Stats summary (with staff bonuses)
        for key in STAT_KEYS:
            base   = p.stats[key]
            bonus  = p.staff_stat_bonus(key)
            lbl    = STAT_LABELS[key]
            val_s  = f"{base + bonus}" if bonus else f"{base}"
            col    = C_GOLD if bonus else C_GRAY
            row    = self.font_med.render(f"{lbl}: {val_s}", True, col)
            surface.blit(row, (r.x + 40, ty)); ty += 22

        ty += 10
        # Club info
        club_lbl = CLUB_SETS[p.club_set_name]["label"]
        ci = self.font_med.render(f"Clubs: {club_lbl}", True, C_GOLD)
        surface.blit(ci, (r.x + 40, ty)); ty += 24

        # World ranking
        if p.world_ranking_points > 0:
            from src.career.rankings import rank_label
            rl = self.font_small.render(rank_label(p.world_rank), True,
                                        C_GOLD if p.world_rank == 1 else C_GRAY)
            surface.blit(rl, (r.x + 40, ty)); ty += 22

        # Promotion requirements — surface the gate before the player hits it.
        promo_lines = self._promotion_requirement_lines(p)
        if promo_lines:
            hdr = self.font_small.render("Promotion:", True, (150, 180, 120))
            surface.blit(hdr, (r.x + 40, ty)); ty += 16
            for text, ok in promo_lines:
                col = C_GREEN if ok else C_GOLD
                s = self.font_small.render("  " + text, True, col)
                surface.blit(s, (r.x + 40, ty)); ty += 16

        # Active sponsor
        if p.active_sponsor:
            sp_name = p.active_sponsor["name"]
            sp_prog = progress_label(p.active_sponsor, p.sponsor_progress)
            si = self.font_small.render(f"Sponsor: {sp_name}", True, (120, 160, 220))
            surface.blit(si, (r.x + 40, ty)); ty += 18
            pi = self.font_small.render(sp_prog, True, C_GRAY)
            surface.blit(pi, (r.x + 40, ty))

    def _draw_equipment_panel(self, surface):
        p = self.player
        r = self._equip_panel
        pygame.draw.rect(surface, C_PANEL, r, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=6)
        self._section_hdr(surface, "EQUIPMENT", r.x, r.y, r.width)

        cur_idx = CLUB_SET_ORDER.index(p.club_set_name)
        ey = r.y + 40

        for (set_name, btn_r) in self._equip_btns:
            info    = CLUB_SETS[set_name]
            tgt_idx = CLUB_SET_ORDER.index(set_name)
            owned   = tgt_idx <= cur_idx
            locked  = info["min_tour"] > p.tour_level
            can_buy = (not owned) and (not locked) and p.money >= info["cost"]

            col      = C_GOLD if owned else (C_GRAY if locked else C_WHITE)
            name_str = info["label"] + ("  [current]" if tgt_idx == cur_idx else
                                        "  owned" if owned else "")
            ls = self.font_med.render(name_str, True, col)
            surface.blit(ls, (r.x + 10, ey))

            if owned:
                sub, sc = "Owned", C_GREEN
            elif locked:
                tour_name = TOUR_DISPLAY_NAMES.get(info['min_tour'], "next tour")
                sub, sc = f"Unlocks on {tour_name} (T{info['min_tour']})", C_RED
            else:
                sub, sc = f"${info['cost']:,}  ·  {self._driver_hint(set_name)}", (
                    C_GOLD if can_buy else C_GRAY)
            ss = self.font_small.render(sub, True, sc)
            surface.blit(ss, (r.x + 10, ey + 20))

            # Buy button
            hk = f"buy:{set_name}"
            bg = (C_BTN_DIS if (owned or locked)
                  else C_BTN_HOV if self._hov == hk
                  else (C_BTN if can_buy else C_BTN_DIS))
            pygame.draw.rect(surface, bg, btn_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, btn_r, 1, border_radius=4)
            bt = "Owned" if owned else ("Locked" if locked else "Buy")
            bl = self.font_small.render(bt, True,
                                        C_GREEN if owned else C_GRAY if locked else C_WHITE)
            surface.blit(bl, bl.get_rect(center=btn_r.center))
            ey += 48

        # ── Balls section ─────────────────────────────────────────────────────
        by = self._balls_section_y
        pygame.draw.line(surface, C_BORDER,
                         (r.x + 10, by - 6), (r.right - 10, by - 6), 1)
        hdr = self.font_hdr.render("BALLS", True, C_GOLD)
        surface.blit(hdr, (r.x + 12, by))
        by += 22

        # Current driver distance — the reference the preview is scaled from.
        from src.golf.club import get_club_bag
        cur_driver = next((c for c in get_club_bag(p.club_set_name)
                           if c.name == "Driver"), None)
        base_driver_yds = cur_driver.max_distance_yards if cur_driver else 250

        for (ball_id, btn_r) in self._ball_btns:
            info   = BALL_TYPES[ball_id]
            owned  = ball_id in p.owned_balls
            active = (p.ball_type == ball_id)
            locked = info["min_tour"] > p.tour_level and not owned
            can_buy = (not owned) and (not locked) and p.money >= info["cost"]

            col = C_GOLD if active else (C_GRAY if locked else C_WHITE)
            name_str = info["label"] + ("  [active]" if active else "")
            ls = self.font_med.render(name_str, True, col)
            surface.blit(ls, (r.x + 10, by))

            # Preview: effective driver distance with this ball, right-aligned
            # above the Buy/Select button. Lets the player see the concrete
            # payoff of the trade-offs printed below.
            preview_yds = int(round(base_driver_yds * info["dist_mult"]))
            pv = self.font_small.render(f"~{preview_yds}y", True, (130, 190, 130))
            surface.blit(pv, (btn_r.left - 8 - pv.get_width(), by + 2))

            if owned and not active:
                sub, sc = ball_effect_summary(ball_id), C_GRAY
            elif active:
                sub, sc = ball_effect_summary(ball_id), C_GREEN
            elif locked:
                sub, sc = f"Unlocks Tour {info['min_tour']}", C_RED
            else:
                sub, sc = f"${info['cost']:,}  ·  {ball_effect_summary(ball_id)}", (
                    C_GOLD if can_buy else C_GRAY)
            ss = self.font_small.render(sub, True, sc)
            surface.blit(ss, (r.x + 10, by + 18))

            # Buy / Select button
            if owned:
                hk = f"ball_select:{ball_id}"
                if active:
                    bg, bt, tc = C_BTN_DIS, "Active", C_GREEN
                else:
                    bg = C_BTN_HOV if self._hov == hk else C_BTN
                    bt, tc = "Select", C_WHITE
            elif locked:
                bg, bt, tc = C_BTN_DIS, "Locked", C_GRAY
            else:
                hk = f"ball_buy:{ball_id}"
                bg = (C_BTN_HOV if self._hov == hk
                      else (C_BTN if can_buy else C_BTN_DIS))
                bt, tc = "Buy", (C_WHITE if can_buy else C_GRAY)
            pygame.draw.rect(surface, bg, btn_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, btn_r, 1, border_radius=4)
            bl = self.font_small.render(bt, True, tc)
            surface.blit(bl, bl.get_rect(center=btn_r.center))
            by += 34

    # ── Tab 1 — Staff ─────────────────────────────────────────────────────────

    def _draw_tab1(self, surface):
        p = self.player
        locked_all = p.tour_level < 4

        if locked_all:
            msg = self.font_hdr.render(
                "Staff unlock on the Continental Tour (Level 4)", True, C_GRAY)
            surface.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, CONTENT_Y + 20))

        for (sid, r) in self._staff_cards:
            info   = STAFF_TYPES[sid]
            hired  = sid in p.hired_staff
            locked = info["min_tour"] > p.tour_level

            bg = C_PANEL
            if hired:
                bg = (30, 55, 30)
            elif locked:
                bg = (20, 24, 20)
            pygame.draw.rect(surface, bg, r, border_radius=6)
            bd_col = C_GREEN if hired else (C_BORDER if not locked else (45, 50, 45))
            pygame.draw.rect(surface, bd_col, r, 1, border_radius=6)

            ty = r.y + 12
            # Name
            ts = self.font_hdr.render(info["label"], True,
                                      C_WHITE if not locked else C_GRAY)
            surface.blit(ts, (r.x + 14, ty)); ty += 22

            # Description
            ds = self.font_small.render(info["description"], True, C_GRAY)
            surface.blit(ds, (r.x + 14, ty)); ty += 18

            # Bonuses
            bparts = [f"+{v} {STAT_LABELS[k]}" for k, v in info["bonuses"].items()]
            bs = self.font_small.render("Bonus: " + ", ".join(bparts), True,
                                        C_STAT_STAFF)
            surface.blit(bs, (r.x + 14, ty)); ty += 18

            # Hire cost + salary
            cs = self.font_small.render(
                f"Hire: ${info['hire_cost']:,}   Salary: ${info['salary']:,}/event",
                True, C_GOLD)
            surface.blit(cs, (r.x + 14, ty))

            # Hire/Fire button
            _, btn_r = self._staff_btn[STAFF_ORDER.index(sid)]
            hk = f"fire:{sid}" if hired else f"hire:{sid}"
            if locked:
                bg_b = C_BTN_DIS
            elif hired:
                bg_b = C_BTN_RED_H if self._hov == hk else C_BTN_RED
            else:
                bg_b = C_BTN_HOV if self._hov == hk else (C_BTN if p.money >= info["hire_cost"] else C_BTN_DIS)
            pygame.draw.rect(surface, bg_b, btn_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, btn_r, 1, border_radius=4)
            bt = "Fire" if hired else ("Locked" if locked else "Hire")
            bl = self.font_small.render(bt, True, C_WHITE)
            surface.blit(bl, bl.get_rect(center=btn_r.center))

    # ── Tab 2 — Sponsors ──────────────────────────────────────────────────────

    def _draw_tab2(self, surface):
        p        = self.player
        r_list   = self._sponsor_list_panel
        r_active = self._sponsor_active_panel

        # ── Available sponsors ────────────────────────────────────────────────
        pygame.draw.rect(surface, C_PANEL, r_list, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, r_list, 1, border_radius=6)
        self._section_hdr(surface, "AVAILABLE SPONSORS", r_list.x, r_list.y, r_list.width)

        available = get_available_sponsors(p.tour_level)
        self._sponsor_btns = []
        sy = r_list.y + 46
        row_h = 90

        for deal in available:
            locked  = deal["min_tour"] > p.tour_level
            active  = p.active_sponsor and p.active_sponsor["id"] == deal["id"]
            has_any = p.active_sponsor is not None

            row_r = pygame.Rect(r_list.x + 8, sy, r_list.width - 16, row_h - 6)
            bg    = (C_SPONSOR_ACT if active else
                     (20, 26, 20) if locked else C_PANEL)
            pygame.draw.rect(surface, bg, row_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, row_r, 1, border_radius=4)

            tx, ty_row = row_r.x + 10, row_r.y + 8
            ns = self.font_hdr.render(deal["name"], True,
                                      C_GOLD if active else
                                      C_GRAY if locked else C_WHITE)
            surface.blit(ns, (tx, ty_row))

            ds = self.font_small.render(deal["description"], True, C_GRAY)
            surface.blit(ds, (tx, ty_row + 20))

            fs = self.font_small.render(
                f"Sign fee: ${deal['signing_fee']:,}   "
                f"Season bonus: ${deal['season_bonus']:,}",
                True, C_GOLD)
            surface.blit(fs, (tx, ty_row + 38))

            # Accept button
            btn_r = pygame.Rect(row_r.right - 115, row_r.y + (row_h - 6 - 28) // 2,
                                 105, 28)
            self._sponsor_btns.append((deal["id"], btn_r))

            if active:
                btn_bg = C_BTN_DIS
                btn_txt = "Active"
            elif has_any:
                btn_bg = C_BTN_DIS
                btn_txt = "Drop first"
            elif locked:
                btn_bg = C_BTN_DIS
                btn_txt = "Locked"
            else:
                hk = f"sponsor:{deal['id']}"
                btn_bg = C_BTN_HOV if self._hov == hk else C_BTN
                btn_txt = "Accept"
            pygame.draw.rect(surface, btn_bg, btn_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, btn_r, 1, border_radius=4)
            bl = self.font_small.render(btn_txt, True, C_WHITE)
            surface.blit(bl, bl.get_rect(center=btn_r.center))

            sy += row_h

        # ── Active contract ───────────────────────────────────────────────────
        pygame.draw.rect(surface, C_PANEL, r_active, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, r_active, 1, border_radius=6)
        self._section_hdr(surface, "ACTIVE CONTRACT", r_active.x, r_active.y, r_active.width)

        if p.active_sponsor is None:
            ns = self.font_med.render("No active sponsor", True, C_GRAY)
            surface.blit(ns, (r_active.x + 12,
                               r_active.y + 50))
        else:
            sp   = p.active_sponsor
            prog = p.sponsor_progress
            ty2  = r_active.y + 46

            ns = self.font_hdr.render(sp["name"], True, C_WHITE)
            surface.blit(ns, (r_active.x + 12, ty2)); ty2 += 24

            ds = self.font_small.render(sp["description"], True, C_GRAY)
            surface.blit(ds, (r_active.x + 12, ty2)); ty2 += 20

            met = is_target_met(sp, prog)
            pl  = progress_label(sp, prog)
            pc  = self.font_med.render(pl, True, C_GREEN if met else C_GOLD)
            surface.blit(pc, (r_active.x + 12, ty2)); ty2 += 26

            bonus_s = self.font_med.render(
                f"Season bonus: ${sp['season_bonus']:,}", True, C_GOLD)
            surface.blit(bonus_s, (r_active.x + 12, ty2)); ty2 += 26

            if met:
                ms = self.font_hdr.render("TARGET MET!", True, C_GREEN)
                surface.blit(ms, (r_active.x + 12, ty2)); ty2 += 24

            # Drop button
            self._btn_drop_sponsor = pygame.Rect(
                r_active.x + 12, ty2 + 10, 140, 28)
            hk = "drop_sponsor"
            bg = C_BTN_RED_H if self._hov == hk else C_BTN_RED
            pygame.draw.rect(surface, bg, self._btn_drop_sponsor, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, self._btn_drop_sponsor, 1, border_radius=4)
            dl = self.font_small.render("Drop Contract", True, C_WHITE)
            surface.blit(dl, dl.get_rect(center=self._btn_drop_sponsor.center))

    # ── Tab 3 — Career Stats ──────────────────────────────────────────────────

    def _draw_tab3(self, surface):
        p  = self.player
        cy = CONTENT_Y

        # ── Stats column (left) ───────────────────────────────────────────────
        stats_r = pygame.Rect(CONTENT_X, cy, 500, CONTENT_H)
        pygame.draw.rect(surface, C_PANEL, stats_r, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, stats_r, 1, border_radius=6)
        self._section_hdr(surface, "CAREER STATISTICS", stats_r.x, stats_r.y, stats_r.width)

        tour_name  = TOUR_DISPLAY_NAMES.get(p.tour_level, "Tour")
        best_str   = ("—" if p.best_round is None else
                      f"{p.best_round:+d}" if p.best_round != 0 else "E")
        staff_s    = f"{len(p.hired_staff)} hired" if p.hired_staff else "None"
        sponsor_s  = (p.active_sponsor["name"]
                      if p.active_sponsor else "None")

        from src.career.rankings import rank_label
        from src.career.majors import MAJORS, MAJOR_ORDER
        majors_str = ", ".join(
            MAJORS[m]["short_name"] for m in MAJOR_ORDER if m in p.majors_won
        ) or "None"

        rows = [
            ("Name",           p.name),
            ("Nationality",    p.nationality),
            ("Tour",           tour_name),
            ("Season",         str(p.season)),
            ("World Ranking",  rank_label(p.world_rank)),
            ("Ranking Points", f"{p.world_ranking_points:.0f}"),
            ("Majors Won",     f"{len(p.majors_won)}/4"),
            ("",               majors_str[:30]),   # truncate long lists
            ("Events Played",  str(p.events_played)),
            ("Career Wins",    str(p.career_wins)),
            ("Top-5 Finishes", str(p.career_top5)),
            ("Top-10 Finishes",str(p.career_top10)),
            ("Best Round",     best_str),
            ("Career Earnings",f"${p.total_earnings:,}"),
            ("Current Money",  f"${p.money:,}"),
            ("Club Set",       CLUB_SETS[p.club_set_name]["label"]),
            ("Staff",          staff_s),
            ("Sponsor",        sponsor_s),
        ]
        ty = stats_r.y + 46
        for label, val in rows:
            ls = self.font_med.render(label + ":", True, C_GRAY)
            vs = self.font_med.render(val,         True, C_WHITE)
            surface.blit(ls, (stats_r.x + 12, ty))
            surface.blit(vs, (stats_r.x + 230, ty))
            ty += 24

        # ── Achievements column (right) ───────────────────────────────────────
        ach_x  = CONTENT_X + 520
        ach_w  = CONTENT_W - 520
        ach_r  = pygame.Rect(ach_x, cy, ach_w, CONTENT_H)
        pygame.draw.rect(surface, C_PANEL, ach_r, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, ach_r, 1, border_radius=6)
        self._section_hdr(surface, "ACHIEVEMENTS", ach_r.x, ach_r.y, ach_r.width)

        earned_ids = set(p.achievements)
        ty = ach_r.y + 46
        ach_row_h = 44
        for ach_id, info in ACHIEVEMENTS.items():
            done   = ach_id in earned_ids
            row_r  = pygame.Rect(ach_x + 8, ty, ach_w - 16, ach_row_h - 4)
            bg     = C_ACH_DONE if done else C_ACH_LOCK
            pygame.draw.rect(surface, bg, row_r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER if done else (45, 50, 45), row_r, 1, border_radius=4)

            icon = "★" if done else "○"
            ic   = self.font_hdr.render(icon, True, C_GOLD if done else C_GRAY)
            surface.blit(ic, (row_r.x + 8, row_r.y + 6))

            lc = C_WHITE if done else C_GRAY
            ls = self.font_med.render(info["label"], True, lc)
            surface.blit(ls, (row_r.x + 30, row_r.y + 4))
            ds = self.font_small.render(info["desc"], True,
                                        C_GRAY if done else (60, 65, 60))
            surface.blit(ds, (row_r.x + 30, row_r.y + 22))
            ty += ach_row_h

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_hdr(self, surface, label, x, y, w):
        pygame.draw.rect(surface, C_HDR,
                         pygame.Rect(x, y, w, 28), border_radius=6)
        ts = self.font_hdr.render(label, True, (150, 210, 120))
        surface.blit(ts, (x + 10, y + 6))

    def _recommended_tab(self) -> int | None:
        """Return the index of the tab the player would most benefit from
        visiting, or None if nothing stands out. Used to draw a subtle
        gold accent under the recommended tab.

        Priority:
          1. Equipment (tab 0) — an upgrade is unlocked at the current tour
             and affordable.
          2. Staff (tab 1) — staff available for the current tour but none hired.
          3. Sponsors (tab 2) — no active sponsor but signing deals are offered.
          4. None — the default next action is simply Play.
        """
        p = self.player
        if p is None:
            return None

        # 1. Equipment: is there a better affordable set at this tour level?
        cur_idx = CLUB_SET_ORDER.index(p.club_set_name)
        for s_idx, s_name in enumerate(CLUB_SET_ORDER):
            if s_idx <= cur_idx:
                continue
            info = CLUB_SETS[s_name]
            if info["min_tour"] <= p.tour_level and p.money >= info["cost"]:
                return 0

        # 2. Staff: tour 4+ unlocks staff. Nudge if nothing hired yet and they
        #    can afford the cheapest eligible hire.
        if p.tour_level >= 4 and not p.hired_staff:
            eligible = [(sid, info) for sid, info in STAFF_TYPES.items()
                        if info["min_tour"] <= p.tour_level]
            if eligible:
                min_cost = min(info["hire_cost"] for _, info in eligible)
                if p.money >= min_cost:
                    return 1

        # 3. Sponsors: tour 4+ with no active sponsor and at least one offer.
        if p.tour_level >= 4 and p.active_sponsor is None:
            if get_available_sponsors(p.tour_level):
                return 2

        return None

    @staticmethod
    def _promotion_requirement_lines(p) -> list[tuple[str, bool]]:
        """Human-readable list of requirements for promotion off the current tour.

        Each entry is (line, satisfied). Returns [] for tours with no gate
        beyond finishing the season (Tour 6, or when already qualified).
        """
        from src.career.tournament import PROMOTION_THRESHOLD
        lvl = p.tour_level
        threshold = PROMOTION_THRESHOLD.get(lvl)
        if threshold is None:
            return []

        if lvl == 4:
            if p.qschool_pending:
                attempts = max(1, p.qschool_attempts_remaining or 1)
                return [(f"Q-School qualified — "
                         f"{attempts} attempt{'s' if attempts != 1 else ''} ready", True)]
            return [(f"Finish top {threshold} to earn Q-School", False)]

        if lvl == 5:
            rank_ok = p.world_rank <= 50
            rank_line = (f"World Rank ≤ 50  (You: #{p.world_rank})"
                         if p.world_rank < 201
                         else "World Rank ≤ 50  (unranked)")
            return [
                (f"Finish top {threshold} in the season", False),
                (rank_line, rank_ok),
            ]

        return [(f"Finish top {threshold} in the season", False)]

    def _draw_tab_icon(self, surface, tab_idx: int, x: int, y: int, col):
        """Tiny pixel-art glyph per tab: equipment, staff, sponsor, stats."""
        if tab_idx == 0:
            # Club crossed with dumbbell — "training + equipment"
            pygame.draw.line(surface, col, (x + 2, y + 14), (x + 14, y + 2), 2)
            pygame.draw.circle(surface, col, (x + 14, y + 2),  2)
            pygame.draw.rect(surface, col, (x + 1, y + 12, 4, 4))
        elif tab_idx == 1:
            # Person icon — "staff"
            pygame.draw.circle(surface, col, (x + 8, y + 4), 3)
            pygame.draw.rect(surface, col, (x + 3, y + 9, 11, 6), border_radius=2)
        elif tab_idx == 2:
            # Dollar sign — "sponsors"
            pygame.draw.line(surface, col, (x + 8, y + 1), (x + 8, y + 15), 2)
            pygame.draw.arc(surface, col, (x + 2, y + 2, 12, 6), 0.4, 3.5, 2)
            pygame.draw.arc(surface, col, (x + 2, y + 8, 12, 6), -2.7, 0.7, 2)
        elif tab_idx == 3:
            # Trophy — "career stats"
            pygame.draw.rect(surface, col, (x + 4, y + 2, 8, 7))
            pygame.draw.line(surface, col, (x + 4, y + 5), (x + 1, y + 5), 2)
            pygame.draw.line(surface, col, (x + 12, y + 5), (x + 15, y + 5), 2)
            pygame.draw.rect(surface, col, (x + 6, y + 9, 4, 3))
            pygame.draw.rect(surface, col, (x + 3, y + 12, 10, 2))

    @staticmethod
    def _driver_hint(set_name: str) -> str:
        from src.golf.club import get_club_bag
        bag = get_club_bag(set_name)
        d   = next((c for c in bag if c.name == "Driver"), None)
        return f"Driver: {d.max_distance_yards}yds  acc:{d.accuracy:.2f}" if d else ""
