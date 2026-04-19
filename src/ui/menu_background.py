"""
MenuBackground — procedural pixel-art golf vista for the title screen.

Renders at a low internal resolution (320x180) then nearest-neighbour
upscales to the screen, which gives an honest chunky-pixel look without
shipping any image assets. The static scene is cached on construction;
per-frame work is limited to a handful of animated sprites (flag ripple,
birds, water shimmer) drawn over the cached base, plus a subtle vertical
dim band behind the button column so text contrast survives any palette.

Composition keeps focal points (sun, flag, water) well off the centre
vertical strip occupied by the menu buttons.
"""

from __future__ import annotations

import math
import random

import pygame


# Internal render resolution. The whole scene is composed at this size,
# then scaled by ratio to fill the screen (no interpolation).
_IW, _IH = 320, 180


# ── Palette ───────────────────────────────────────────────────────────────────
SKY_TOP      = ( 36,  28,  76)
SKY_UPPER    = ( 92,  52, 104)
SKY_MID      = (168,  88,  96)
SKY_LOW      = (232, 168, 104)
SKY_HORIZON  = (248, 212, 152)

SUN          = (255, 228, 136)
SUN_HALO_1   = (255, 200, 120)
SUN_HALO_2   = (240, 160, 100)

HILL_FAR     = ( 74,  72, 104)
HILL_MID     = ( 58,  92,  84)
HILL_NEAR    = ( 72, 124,  76)
TREELINE     = ( 34,  64,  44)

FAIRWAY      = (110, 176,  88)
FAIRWAY_SH   = ( 80, 144,  72)
ROUGH        = ( 60, 112,  60)
ROUGH_DARK   = ( 44,  84,  52)

SAND         = (220, 196, 148)
SAND_SH      = (188, 160, 116)

WATER        = ( 72, 132, 180)
WATER_HI     = (156, 204, 232)

GREEN_PUTT   = (148, 204, 112)
GREEN_EDGE   = (100, 168,  88)

PIN          = ( 40,  40,  48)
FLAG         = (208,  60,  60)
FLAG_SH      = (152,  36,  36)

GRASS_TUFT   = ( 56, 108,  56)
GRASS_TUFT_H = (108, 176,  96)

BIRD         = ( 24,  24,  32)


class MenuBackground:
    """Cached static vista + a handful of animated overlay elements."""

    def __init__(self, screen_w: int, screen_h: int):
        self.sw = screen_w
        self.sh = screen_h

        self._base = pygame.Surface((_IW, _IH))
        self._render_base(self._base)

        # Animation state
        self._t = 0.0
        self._birds = [
            {"x":  40.0, "y": 28.0, "vx": 10.5, "phase": 0.0},
            {"x": 140.0, "y": 44.0, "vx":  8.0, "phase": 1.2},
        ]
        self._shimmer_timer = 0.0
        self._shimmer_pos: tuple[int, int] | None = None

        # Dim-band surface — baked once at screen res with per-pixel alpha.
        self._dim = self._build_dim_band(screen_w, screen_h)

    # ── Static scene ─────────────────────────────────────────────────────────

    def _render_base(self, surf: pygame.Surface) -> None:
        rng = random.Random(0xC0FFEE)

        self._draw_sky(surf)
        self._draw_sun(surf)
        self._draw_hills(surf, rng)
        self._draw_treeline(surf, rng)
        self._draw_fairway(surf, rng)
        self._draw_bunker(surf)
        self._draw_water(surf)
        self._draw_green(surf)
        self._draw_pin(surf)        # static pole; flag overlay animates
        self._draw_foreground(surf, rng)

    def _draw_sky(self, surf: pygame.Surface) -> None:
        # Hard colour bands give a deliberate pixel-art look rather than a
        # smooth gradient. Bands shrink toward the horizon.
        bands = [
            (SKY_TOP,     0,  40),
            (SKY_UPPER,  40,  68),
            (SKY_MID,    68,  90),
            (SKY_LOW,    90, 108),
            (SKY_HORIZON,108, 118),
        ]
        for col, y0, y1 in bands:
            pygame.draw.rect(surf, col, (0, y0, _IW, y1 - y0))

        # Simple ordered dither at each band boundary for a softer edge.
        for col, y0, y1 in bands:
            if y1 >= _IH:
                break
            below_col = next((c for c, a, _ in bands if a == y1), None)
            if below_col is None:
                continue
            for x in range(0, _IW, 2):
                surf.set_at((x + (y1 & 1), y1), col)
                surf.set_at((x + 1 - (y1 & 1), y1 + 1), below_col)

    def _draw_sun(self, surf: pygame.Surface) -> None:
        cx, cy = 258, 40
        pygame.draw.circle(surf, SUN_HALO_2, (cx, cy), 16)
        pygame.draw.circle(surf, SUN_HALO_1, (cx, cy), 12)
        pygame.draw.circle(surf, SUN,        (cx, cy),  8)
        # horizontal light ribbons
        for dy, w in [(-2, 28), (0, 34), (2, 24)]:
            pygame.draw.line(surf, SUN_HALO_1,
                             (cx - w, cy + dy), (cx + w, cy + dy))

    def _draw_hills(self, surf: pygame.Surface, rng: random.Random) -> None:
        # Three silhouette layers: farther = bluer/flatter, closer = greener/taller.
        def fill_ridge(col, base_y, amp, period, phase):
            pts = [(0, _IH)]
            for x in range(0, _IW + 2, 2):
                y = base_y + int(amp * math.sin(x / period + phase))
                pts.append((x, y))
            pts.append((_IW, _IH))
            pygame.draw.polygon(surf, col, pts)

        fill_ridge(HILL_FAR,  110, 6,  48, 0.3)
        fill_ridge(HILL_MID,  118, 8,  36, 1.4)
        fill_ridge(HILL_NEAR, 128, 10, 30, 2.6)

    def _draw_treeline(self, surf: pygame.Surface, rng: random.Random) -> None:
        # Cluster of tiny rounded trees along the HILL_NEAR ridge (y ≈ 120–130),
        # skipped in a small gap where the fairway meets the horizon.
        gap_x0, gap_x1 = 132, 176
        for x in range(6, _IW - 6, 4):
            if gap_x0 <= x <= gap_x1:
                continue
            y = 124 + int(2 * math.sin(x / 14.0)) + rng.choice([-1, 0, 0, 1])
            r = rng.choice([2, 2, 3])
            pygame.draw.circle(surf, TREELINE, (x, y), r)

    def _draw_fairway(self, surf: pygame.Surface, rng: random.Random) -> None:
        # S-curve sweeping from bottom-right up into the hill gap.
        # Polygon built as left edge + right edge, then a single fill.
        def centre_x(y):
            # y ∈ [128, 180]. At y=128 (horizon gap) centre is x≈155; at
            # y=180 (bottom edge) centre is x≈240. One gentle inflection.
            t = (y - 128) / 52.0
            bend = 12.0 * math.sin(t * math.pi)
            return 155 + (240 - 155) * t + bend

        def width(y):
            t = (y - 128) / 52.0
            return int(4 + 48 * t)   # 4 px at horizon, 52 px at foreground

        left_pts, right_pts = [], []
        for y in range(128, 181):
            cx = centre_x(y)
            w  = width(y)
            left_pts.append((int(cx - w), y))
            right_pts.append((int(cx + w), y))

        rough_pts  = [(lp[0] - 4, lp[1]) for lp in left_pts] + \
                     [(rp[0] + 4, rp[1]) for rp in reversed(right_pts)]
        pygame.draw.polygon(surf, ROUGH, rough_pts)

        fair_pts = left_pts + list(reversed(right_pts))
        pygame.draw.polygon(surf, FAIRWAY, fair_pts)

        # Fairway shade — thin darker band along the left edge for depth.
        shade_pts = left_pts + [(lp[0] + 3, lp[1]) for lp in reversed(left_pts)]
        pygame.draw.polygon(surf, FAIRWAY_SH, shade_pts)

        # Dithered rough → fairway edge
        for (lx, ly) in left_pts:
            if ly % 2 == 0:
                surf.set_at((lx - 1, ly), ROUGH_DARK)
        for (rx, ry) in right_pts:
            if ry % 2 == 0:
                surf.set_at((rx + 1, ry), ROUGH_DARK)

    def _draw_bunker(self, surf: pygame.Surface) -> None:
        # Small fairway bunker right of the fairway centre, mid-distance.
        pygame.draw.ellipse(surf, SAND_SH, (210, 150, 24, 10))
        pygame.draw.ellipse(surf, SAND,    (212, 151, 20,  7))

    def _draw_water(self, surf: pygame.Surface) -> None:
        # Small pond in the bottom-right, outside the button column.
        pygame.draw.ellipse(surf, WATER,    (262, 158, 52, 18))
        pygame.draw.ellipse(surf, WATER_HI, (268, 160,  8,  2))
        pygame.draw.ellipse(surf, WATER_HI, (294, 167,  6,  2))

    def _draw_green(self, surf: pygame.Surface) -> None:
        # Signature green lower-left — kidney-shaped via two overlapping ovals.
        pygame.draw.ellipse(surf, GREEN_EDGE, (12, 140, 68, 28))
        pygame.draw.ellipse(surf, GREEN_PUTT, (16, 142, 60, 22))
        # cup
        surf.set_at((46, 150), PIN)
        surf.set_at((47, 150), PIN)

    def _draw_pin(self, surf: pygame.Surface) -> None:
        # Pole only; flag is drawn each frame in _draw_animated for the ripple.
        for y in range(136, 151):
            surf.set_at((48, y), PIN)

    def _draw_foreground(self, surf: pygame.Surface, rng: random.Random) -> None:
        # Grass tufts along the very bottom to anchor the foreground.
        for x in range(0, _IW, 3):
            h = rng.choice([1, 1, 2, 2, 3])
            col = GRASS_TUFT_H if rng.random() < 0.35 else GRASS_TUFT
            for dy in range(h):
                surf.set_at((x + rng.choice([-1, 0, 0, 1]), _IH - 1 - dy), col)

    # ── Dim band ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_dim_band(sw: int, sh: int) -> pygame.Surface:
        """Vertical soft dim behind the button column — ~38% alpha centre,
        fading to 0 at ±220 px from centre. Protects text contrast without
        hiding the scene."""
        surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        cx = sw // 2
        half = 220
        max_a = 96
        for x in range(cx - half, cx + half + 1):
            t = 1.0 - abs(x - cx) / half
            a = int(max_a * (t ** 1.3))
            if a <= 0:
                continue
            pygame.draw.line(surf, (0, 0, 0, a), (x, 0), (x, sh))
        return surf

    # ── Update / draw ────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        self._t += dt

        for b in self._birds:
            b["x"] += b["vx"] * dt
            if b["x"] > _IW + 8:
                b["x"] = -8
                b["y"] = 20 + (hash(str(self._t)) % 32)

        self._shimmer_timer -= dt
        if self._shimmer_timer <= 0:
            self._shimmer_timer = random.uniform(0.4, 1.1)
            # Random bright pixel somewhere on the water ellipse.
            self._shimmer_pos = (
                random.randint(268, 308),
                random.randint(161, 173),
            )

    def draw(self, surface: pygame.Surface) -> None:
        # Build a per-frame composite at internal res, then upscale once.
        frame = self._base.copy()
        self._draw_animated(frame)
        scaled = pygame.transform.scale(frame, (self.sw, self.sh))
        surface.blit(scaled, (0, 0))
        surface.blit(self._dim, (0, 0))

    def _draw_animated(self, surf: pygame.Surface) -> None:
        # Flag ripple — two frames alternating at ~5 Hz. Rooted at pole top.
        phase = int(self._t * 5) & 1
        fx0, fy0 = 49, 136   # just right of the pole top
        if phase == 0:
            flag = [(fx0, fy0), (fx0+5, fy0), (fx0+6, fy0+1),
                    (fx0+5, fy0+2), (fx0+1, fy0+2), (fx0, fy0+2)]
        else:
            flag = [(fx0, fy0), (fx0+4, fy0+1), (fx0+6, fy0),
                    (fx0+5, fy0+2), (fx0+2, fy0+3), (fx0, fy0+2)]
        pygame.draw.polygon(surf, FLAG, flag)
        # shade underside
        surf.set_at((fx0 + 2, fy0 + 2), FLAG_SH)
        surf.set_at((fx0 + 3, fy0 + 2), FLAG_SH)

        # Birds — little V of three pixels each, wings beating with phase.
        for b in self._birds:
            bx, by = int(b["x"]), int(b["y"])
            wing_up = int((self._t * 6 + b["phase"])) & 1
            if wing_up:
                pts = [(bx - 2, by), (bx - 1, by - 1), (bx, by),
                       (bx + 1, by - 1), (bx + 2, by)]
            else:
                pts = [(bx - 2, by + 1), (bx - 1, by), (bx, by + 1),
                       (bx + 1, by), (bx + 2, by + 1)]
            for p in pts:
                if 0 <= p[0] < _IW and 0 <= p[1] < _IH:
                    surf.set_at(p, BIRD)

        # Water shimmer
        if self._shimmer_pos is not None and int(self._t * 4) & 1:
            surf.set_at(self._shimmer_pos, WATER_HI)
