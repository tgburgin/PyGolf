"""
AudioSettingsPanel — a modal overlay for Master / SFX / Ambient volume.

Originally lived inline in MainMenuState. Extracted so the pause overlay
in GolfRoundState can reuse it without duplicating the layout.

Usage:
    panel = AudioSettingsPanel(screen_w, screen_h)

    # Inside your state's event loop:
    if panel.handle_event(event):
        pass   # event was consumed

    # Inside draw():
    if panel.visible:
        panel.draw(surface)

Call `panel.open()` to show it and `panel.close()` to hide it. A click
on the close button, outside the panel, or an Esc press will also close
it automatically via handle_event.
"""

import pygame


_C_PANEL   = ( 14,  22,  14)
_C_BORDER  = ( 58,  98,  58)
_C_BTN     = ( 28,  78,  28)
_C_BTN_HOV = ( 48, 120,  48)
_C_WHITE   = (255, 255, 255)
_C_GOLD    = (210, 170,  30)


class AudioSettingsPanel:
    """Stateful audio-settings overlay. One per owning state."""

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.visible  = False

        pw, ph = 440, 280
        self._panel = pygame.Rect(
            (screen_w - pw) // 2, (screen_h - ph) // 2, pw, ph)
        self._close = pygame.Rect(
            self._panel.centerx - 80, self._panel.bottom - 50, 160, 34)

        self._vol_btns: list[tuple[str, pygame.Rect, pygame.Rect]] = []
        self._font_btn    = pygame.font.SysFont("arial", 24, bold=True)
        self._font_medium = pygame.font.SysFont("arial", 18)
        self._font_small  = pygame.font.SysFont("arial", 14)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed by the panel."""
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self._close.collidepoint(pos):
                self.close()
                return True
            from src.utils.sound_manager import SoundManager
            snd = SoundManager.instance()
            for key, minus_r, plus_r in self._vol_btns:
                if minus_r.collidepoint(pos):
                    cur = getattr(snd, f"{key}_vol")
                    getattr(snd, f"set_{key}")(max(0.0, round(cur - 0.1, 1)))
                    return True
                if plus_r.collidepoint(pos):
                    cur = getattr(snd, f"{key}_vol")
                    getattr(snd, f"set_{key}")(min(1.0, round(cur + 0.1, 1)))
                    return True
            # Click outside the panel closes it.
            if not self._panel.collidepoint(pos):
                self.close()
                return True
            # Inside-panel clicks are still consumed so they don't fall through.
            return True

        # Eat every other event while visible to keep the panel modal.
        return True

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        from src.utils.sound_manager import SoundManager
        snd = SoundManager.instance()

        dim = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surface.blit(dim, (0, 0))

        r = self._panel
        pygame.draw.rect(surface, _C_PANEL,  r, border_radius=10)
        pygame.draw.rect(surface, _C_BORDER, r, 2, border_radius=10)

        title = self._font_btn.render("Audio Settings", True, _C_WHITE)
        surface.blit(title, (r.centerx - title.get_width() // 2, r.y + 14))
        pygame.draw.line(surface, _C_BORDER,
                         (r.x + 16, r.y + 48), (r.right - 16, r.y + 48))

        rows = [("master", "Master Volume"),
                ("sfx",    "Sound Effects"),
                ("ambient","Ambient")]
        self._vol_btns = []
        row_y = r.y + 62
        btn_w, btn_h = 34, 28

        for key, label in rows:
            val = getattr(snd, f"{key}_vol")
            ls  = self._font_medium.render(label + ":", True, _C_WHITE)
            surface.blit(ls, (r.x + 20, row_y + 4))

            bar_x, bar_y, bar_w, bar_h = r.x + 170, row_y + 8, 160, 14
            pygame.draw.rect(surface, (30, 45, 30),
                             pygame.Rect(bar_x, bar_y, bar_w, bar_h),
                             border_radius=4)
            fill = int(bar_w * val)
            if fill > 0:
                pygame.draw.rect(surface, _C_BTN_HOV,
                                 pygame.Rect(bar_x, bar_y, fill, bar_h),
                                 border_radius=4)

            pct = self._font_small.render(f"{int(val * 100)}%", True, _C_GOLD)
            surface.blit(pct, (bar_x + bar_w + 8, row_y + 4))

            minus_r = pygame.Rect(r.x + 340, row_y, btn_w, btn_h)
            plus_r  = pygame.Rect(r.x + 382, row_y, btn_w, btn_h)
            for btn_r, lbl in [(minus_r, "−"), (plus_r, "+")]:
                pygame.draw.rect(surface, _C_BTN,    btn_r, border_radius=4)
                pygame.draw.rect(surface, _C_BORDER, btn_r, 1, border_radius=4)
                bl = self._font_medium.render(lbl, True, _C_WHITE)
                surface.blit(bl, bl.get_rect(center=btn_r.center))
            self._vol_btns.append((key, minus_r, plus_r))

            row_y += 52

        pygame.draw.rect(surface, _C_BTN,    self._close, border_radius=6)
        pygame.draw.rect(surface, _C_BORDER, self._close, 1, border_radius=6)
        cl = self._font_medium.render("Close  (Esc)", True, _C_WHITE)
        surface.blit(cl, cl.get_rect(center=self._close.center))
