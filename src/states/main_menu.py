"""
MainMenuState — the title / start screen.

Buttons
-------
  New Game  → CharacterCreationState
  Load Game → shows save slots (or grayed out if no saves exist)
  Quit

Save panel
----------
  Each slot has a Load area (click the row) and a ✕ Delete button.
  Clicking Delete shows a confirmation overlay before the file is removed.
"""

import os
import sys

import pygame

from src.utils.save_system import (
    list_saves, get_save_preview, load_game,
    SaveVersionError, SaveCorruptError,
)

C_BG         = (  6,  12,   6)
C_PANEL      = ( 14,  22,  14)
C_TITLE      = (168, 224,  88)
C_SUB        = (100, 148,  60)
C_BTN        = ( 28,  78,  28)
C_BTN_HOV    = ( 48, 120,  48)
C_BTN_DIS    = ( 60,  52,  42)   # warm desaturated — distinct from the active green
C_BORDER     = ( 58,  98,  58)
C_BORDER_DIS = ( 48,  60,  48)
C_WHITE      = (255, 255, 255)
C_GRAY       = (130, 130, 130)
C_GOLD       = (210, 170,  30)
C_RED        = (200,  55,  55)
C_RED_HOV    = (230,  80,  80)
C_RED_DIM    = ( 80,  24,  24)

from src.constants import SCREEN_W, SCREEN_H

TOUR_NAMES = {
    1: "Amateur Circuit",
    2: "Challenger Tour",
    3: "Development Tour",
    4: "Continental Tour",
    5: "World Tour",
    6: "The Grand Tour",
}


class MainMenuState:
    """Title screen — new game, load game, quit."""

    def __init__(self, game):
        self.game = game

        self.font_title  = pygame.font.SysFont("arial", 72, bold=True)
        self.font_sub    = pygame.font.SysFont("arial", 22)
        self.font_btn    = pygame.font.SysFont("arial", 24, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 18)
        self.font_small  = pygame.font.SysFont("arial", 14)

        self._saves    = list_saves()
        self._previews = [get_save_preview(p) for p in self._saves[:5]]

        self._hovered_btn  = None
        self._hovered_save = None   # index of hovered load-row
        self._hovered_del  = None   # index of hovered delete button
        self._show_saves   = False
        self._confirm_idx  = None   # index awaiting delete confirmation
        self._confirm_yes_hov = False
        self._confirm_no_hov  = False

        # Transient error banner shown over the save panel after a bad load.
        self._load_error: str | None = None
        self._load_error_timer: float = 0.0

        cx = SCREEN_W // 2
        bw, bh = 300, 56
        self._btn_new  = pygame.Rect(cx - bw // 2, 340, bw, bh)
        self._btn_load = pygame.Rect(cx - bw // 2, 414, bw, bh)
        self._btn_quit = pygame.Rect(cx - bw // 2, 488, bw, bh)

        # Save panel
        sp_w, sp_h = 580, 400
        self._save_panel = pygame.Rect(
            cx - sp_w // 2, (SCREEN_H - sp_h) // 2, sp_w, sp_h)
        self._save_rects: list[pygame.Rect] = []   # load-click area per slot
        self._del_rects:  list[pygame.Rect] = []   # delete button per slot
        self._btn_cancel = pygame.Rect(
            self._save_panel.centerx - 100,
            self._save_panel.bottom - 52,
            200, 38)

        # Confirmation dialog (recomputed when needed)
        self._confirm_panel = pygame.Rect(cx - 210, SCREEN_H // 2 - 80, 420, 160)
        cpy = self._confirm_panel
        self._confirm_yes = pygame.Rect(cpy.x + 20,         cpy.bottom - 56, 180, 40)
        self._confirm_no  = pygame.Rect(cpy.right - 200,    cpy.bottom - 56, 180, 40)

        # Settings button (bottom-right)
        self._btn_settings = pygame.Rect(SCREEN_W - 140, SCREEN_H - 50, 125, 34)
        self._hovered_settings = False

        # Shared audio-settings overlay.
        from src.ui.audio_settings import AudioSettingsPanel
        self._audio_panel = AudioSettingsPanel(SCREEN_W, SCREEN_H)

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        if self._confirm_idx is not None:
            self._handle_confirm_event(event)
            return
        if self._audio_panel.handle_event(event):
            return
        if self._show_saves:
            self._handle_save_panel_event(event)
            return

        if event.type == pygame.MOUSEMOTION:
            p = event.pos
            self._hovered_btn = None
            self._hovered_settings = self._btn_settings.collidepoint(p)
            for name, rect in [("new", self._btn_new),
                                ("load", self._btn_load),
                                ("quit", self._btn_quit)]:
                if rect.collidepoint(p):
                    self._hovered_btn = name

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            p = event.pos
            if self._btn_settings.collidepoint(p):
                self._audio_panel.open()
                return
            if self._btn_new.collidepoint(p):
                self._go_new_game()
            elif self._btn_load.collidepoint(p) and self._saves:
                self._show_saves = True
            elif self._btn_quit.collidepoint(p):
                pygame.quit()
                sys.exit()

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_n:
                self._go_new_game()
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

    def _handle_save_panel_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            p = event.pos
            self._hovered_save = None
            self._hovered_del  = None
            for i, r in enumerate(self._save_rects):
                if r.collidepoint(p):
                    self._hovered_save = i
            for i, r in enumerate(self._del_rects):
                if r.collidepoint(p):
                    self._hovered_del = i

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            p = event.pos
            # Delete buttons take priority
            for i, r in enumerate(self._del_rects):
                if r.collidepoint(p):
                    self._confirm_idx = i
                    return
            if self._btn_cancel.collidepoint(p):
                self._show_saves = False
                return
            for i, r in enumerate(self._save_rects):
                if r.collidepoint(p):
                    if self._previews[i].get("corrupt"):
                        self._load_error = self._previews[i].get(
                            "error", "This save cannot be loaded.")
                        self._load_error_timer = 4.0
                        return
                    self._load_save(self._previews[i])
                    return
            # Click outside = cancel
            if not self._save_panel.collidepoint(p):
                self._show_saves = False

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._show_saves = False

    def _handle_confirm_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            p = event.pos
            self._confirm_yes_hov = self._confirm_yes.collidepoint(p)
            self._confirm_no_hov  = self._confirm_no.collidepoint(p)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            p = event.pos
            if self._confirm_yes.collidepoint(p):
                self._delete_save(self._confirm_idx)
            elif self._confirm_no.collidepoint(p):
                self._confirm_idx = None
            # Click outside confirmation = cancel
            elif not self._confirm_panel.collidepoint(p):
                self._confirm_idx = None

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._confirm_idx = None
            elif event.key == pygame.K_RETURN:
                self._delete_save(self._confirm_idx)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _go_new_game(self):
        from src.states.character_creation import CharacterCreationState
        self.game.change_state(CharacterCreationState(self.game))

    def _load_save(self, preview: dict):
        try:
            player, tourn_data, round_state = load_game(preview["path"])
        except (SaveVersionError, SaveCorruptError) as e:
            self._load_error       = str(e)
            self._load_error_timer = 4.0
            return
        except Exception as e:
            self._load_error       = f"Unexpected error loading save: {e}"
            self._load_error_timer = 4.0
            return
        self.game.player = player

        if tourn_data is not None:
            try:
                from src.career.tournament import Tournament
                self.game.current_tournament = Tournament.from_dict(tourn_data)
            except Exception as e:
                print(f"Failed to restore tournament: {e}")
                self.game.current_tournament = None
        else:
            self.game.current_tournament = None

        # Mid-round resume path: if the save captured an in-progress hole,
        # rebuild the course by name and drop straight back into the round.
        if round_state and self.game.current_tournament is not None:
            if self._resume_round(round_state):
                return
            # Resume failed — fall through to the hub so the career isn't lost.
            self._load_error       = "Could not resume the in-progress round; the course was not found. Your career is intact."
            self._load_error_timer = 5.0

        self._launch_game()

    def _resume_round(self, round_state: dict) -> bool:
        """Rebuild the course the player was on and re-enter GolfRoundState.

        Returns True on success, False if the course can't be found.
        """
        t = self.game.current_tournament
        if t is None or not t.course_name:
            return False
        try:
            from src.data.tours_data import get_courses_for_tour
            from src.career.tour import get_tour_id
            tour_id = get_tour_id(t.tour_level)
            courses = get_courses_for_tour(tour_id) or []
            course  = next((c for c in courses if c.name == t.course_name), None)
            if course is None:
                return False
            from src.states.golf_round import GolfRoundState
            self.game.change_state(
                GolfRoundState(self.game, course,
                               int(round_state.get("hole_index", 0)),
                               list(round_state.get("scores", [])),
                               resume_state=round_state))
            return True
        except Exception as e:
            print(f"Resume failed: {e}")
            return False

    def _delete_save(self, idx: int):
        """Delete the save file at index idx, then refresh the list."""
        try:
            path = self._saves[idx]
            os.remove(path)
        except Exception as e:
            print(f"Failed to delete save: {e}")
        finally:
            self._confirm_idx = None
            # Refresh save list
            self._saves    = list_saves()
            self._previews = [get_save_preview(p) for p in self._saves[:5]]
            self._save_rects = []
            self._del_rects  = []
            if not self._saves:
                self._show_saves = False

    def _launch_game(self):
        from src.states.career_hub import CareerHubState
        self.game.change_state(CareerHubState(self.game))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self._load_error_timer > 0:
            self._load_error_timer = max(0.0, self._load_error_timer - dt)
            if self._load_error_timer == 0.0:
                self._load_error = None

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        surface.fill(C_BG)
        cx = SCREEN_W // 2

        title = self.font_title.render("Let's Golf!", True, C_TITLE)
        surface.blit(title, (cx - title.get_width() // 2, 150))

        sub = self.font_sub.render("A Career Golf Adventure", True, C_SUB)
        surface.blit(sub, (cx - sub.get_width() // 2, 248))

        load_disabled = not self._saves
        for name, rect, label in [
            ("new",  self._btn_new,  "New Game"),
            ("load", self._btn_load, "Load Game"),
            ("quit", self._btn_quit, "Quit"),
        ]:
            disabled = (name == "load" and load_disabled)
            hovered  = self._hovered_btn == name and not disabled
            bg   = C_BTN_DIS if disabled else (C_BTN_HOV if hovered else C_BTN)
            bord = C_BORDER_DIS if disabled else C_BORDER
            pygame.draw.rect(surface, bg,   rect, border_radius=8)
            pygame.draw.rect(surface, bord, rect, 2, border_radius=8)
            tc = C_GRAY if disabled else C_WHITE
            lbl = self.font_btn.render(label, True, tc)
            surface.blit(lbl, lbl.get_rect(center=rect.center))

        if load_disabled:
            hint = self.font_small.render("No save files found", True, (70, 85, 70))
        else:
            info = self._previews[0]
            tour = TOUR_NAMES.get(info.get("tour_level", 1), "Amateur Circuit")
            hint = self.font_small.render(
                f"Last: {info['name']}  •  {tour}  •  "
                f"{info.get('events_played', 0)} events played",
                True, (90, 140, 70))
        surface.blit(hint, (cx - hint.get_width() // 2, self._btn_load.bottom + 6))

        ctrl = self.font_small.render(
            "N = New Game   •   Esc = Quit", True, (55, 75, 55))
        surface.blit(ctrl, (cx - ctrl.get_width() // 2, SCREEN_H - 30))

        # Settings button
        sg_bg = C_BTN_HOV if self._hovered_settings else C_BTN
        pygame.draw.rect(surface, sg_bg,   self._btn_settings, border_radius=6)
        pygame.draw.rect(surface, C_BORDER, self._btn_settings, 1, border_radius=6)
        sg_lbl = self.font_small.render("⚙ Settings", True, C_WHITE)
        surface.blit(sg_lbl, sg_lbl.get_rect(center=self._btn_settings.center))

        if self._show_saves:
            self._draw_save_panel(surface)
            if self._confirm_idx is not None:
                self._draw_confirm_overlay(surface)

        self._audio_panel.draw(surface)

    # ── Save panel ────────────────────────────────────────────────────────────

    def _draw_save_panel(self, surface):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surface.blit(dim, (0, 0))

        r = self._save_panel
        pygame.draw.rect(surface, C_PANEL,  r, border_radius=10)
        pygame.draw.rect(surface, C_BORDER, r, 2, border_radius=10)

        title = self.font_btn.render("Select Save File", True, C_WHITE)
        surface.blit(title, (r.centerx - title.get_width() // 2, r.y + 14))

        hint = self.font_small.render(
            "Click a row to load  •  ✕ to delete", True, C_GRAY)
        surface.blit(hint, (r.centerx - hint.get_width() // 2, r.y + 44))

        pygame.draw.line(surface, C_BORDER,
                         (r.x + 16, r.y + 62), (r.right - 16, r.y + 62))

        self._save_rects = []
        self._del_rects  = []
        row_h    = 62
        del_w    = 36
        del_pad  = 8

        for i, preview in enumerate(self._previews):
            row_y = r.y + 70 + i * (row_h + 4)
            full  = pygame.Rect(r.x + 14, row_y, r.width - 28, row_h)
            # Load area excludes the delete button on the right
            load  = pygame.Rect(full.x, full.y,
                                full.width - del_w - del_pad * 2, full.height)
            delbtn = pygame.Rect(full.right - del_w - del_pad,
                                 full.y + (full.height - del_w) // 2,
                                 del_w, del_w)

            self._save_rects.append(load)
            self._del_rects.append(delbtn)

            # Row background
            load_hov = self._hovered_save == i
            del_hov  = self._hovered_del  == i
            row_bg = (38, 68, 38) if load_hov else (24, 38, 24)
            pygame.draw.rect(surface, row_bg, full, border_radius=6)
            pygame.draw.rect(surface, C_BORDER, full, 1, border_radius=6)

            # Save info
            is_corrupt = bool(preview.get("corrupt"))
            name_col   = (200, 130, 130) if is_corrupt else C_WHITE
            name_text  = preview.get("name", "?")
            if is_corrupt:
                name_text = f"{name_text}  (corrupt)"
            name_s = self.font_medium.render(name_text, True, name_col)
            surface.blit(name_s, (full.x + 12, full.y + 8))

            if is_corrupt:
                info_str = preview.get("error", "Cannot be loaded")
                info_s = self.font_small.render(info_str, True, (180, 120, 120))
            else:
                tour     = TOUR_NAMES.get(preview.get("tour_level", 1), "Amateur")
                info_str = (f"{preview.get('nationality', '')}   "
                            f"{tour}   "
                            f"{preview.get('events_played', 0)} events   "
                            f"${preview.get('money', 0):,}")
                info_s = self.font_small.render(info_str, True, C_GRAY)
            surface.blit(info_s, (full.x + 12, full.y + 36))

            # Delete button
            del_bg   = C_RED_HOV if del_hov else C_RED_DIM
            del_bord = C_RED_HOV if del_hov else C_RED
            pygame.draw.rect(surface, del_bg,   delbtn, border_radius=5)
            pygame.draw.rect(surface, del_bord, delbtn, 1, border_radius=5)
            x_lbl = self.font_medium.render("✕", True,
                                            C_WHITE if del_hov else (180, 100, 100))
            surface.blit(x_lbl, x_lbl.get_rect(center=delbtn.center))

        # Cancel button
        pygame.draw.rect(surface, (55, 30, 30), self._btn_cancel, border_radius=6)
        pygame.draw.rect(surface, C_RED,        self._btn_cancel, 1, border_radius=6)
        cl = self.font_medium.render("Cancel", True, C_WHITE)
        surface.blit(cl, cl.get_rect(center=self._btn_cancel.center))

        # Transient error banner (shown after a failed load)
        if self._load_error:
            banner_h = 34
            banner = pygame.Rect(r.x + 14, self._btn_cancel.y - banner_h - 10,
                                 r.width - 28, banner_h)
            pygame.draw.rect(surface, (55, 20, 20), banner, border_radius=5)
            pygame.draw.rect(surface, C_RED,        banner, 1, border_radius=5)
            msg = self._load_error
            if len(msg) > 80:
                msg = msg[:77] + "…"
            es = self.font_small.render(msg, True, (240, 200, 200))
            surface.blit(es, es.get_rect(center=banner.center))

    # ── Confirmation overlay ──────────────────────────────────────────────────

    def _draw_confirm_overlay(self, surface):
        idx = self._confirm_idx
        if idx is None or idx >= len(self._previews):
            return

        # Additional dim over the save panel
        dim2 = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim2.fill((0, 0, 0, 120))
        surface.blit(dim2, (0, 0))

        cp = self._confirm_panel
        pygame.draw.rect(surface, (20, 12, 12), cp, border_radius=10)
        pygame.draw.rect(surface, C_RED,        cp, 2,  border_radius=10)

        name = self._previews[idx].get("name", "this save")
        q1 = self.font_btn.render("Delete save file?", True, C_WHITE)
        q2 = self.font_medium.render(
            f'"{name}" will be permanently deleted.', True, (210, 170, 170))
        q3 = self.font_small.render(
            "This cannot be undone.", True, (160, 100, 100))

        surface.blit(q1, q1.get_rect(centerx=cp.centerx, top=cp.y + 16))
        surface.blit(q2, q2.get_rect(centerx=cp.centerx, top=cp.y + 52))
        surface.blit(q3, q3.get_rect(centerx=cp.centerx, top=cp.y + 76))

        # Yes button
        yes_bg = C_RED_HOV if self._confirm_yes_hov else C_RED_DIM
        pygame.draw.rect(surface, yes_bg,  self._confirm_yes, border_radius=7)
        pygame.draw.rect(surface, C_RED,   self._confirm_yes, 2, border_radius=7)
        yl = self.font_medium.render("Yes, Delete", True, C_WHITE)
        surface.blit(yl, yl.get_rect(center=self._confirm_yes.center))

        # No button
        no_bg = C_BTN_HOV if self._confirm_no_hov else C_BTN
        pygame.draw.rect(surface, no_bg,    self._confirm_no, border_radius=7)
        pygame.draw.rect(surface, C_BORDER, self._confirm_no, 2, border_radius=7)
        nl = self.font_medium.render("Cancel  (Esc)", True, C_WHITE)
        surface.blit(nl, nl.get_rect(center=self._confirm_no.center))
