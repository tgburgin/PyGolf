"""
GolfRoundState — plays one hole within an 18-hole round.

The state is constructed with a Course object and the current hole index (0-17).
When the hole is complete the state transitions to:
  - HoleTransitionState  (holes 1-17)
  - RoundSummaryState    (hole 18)

Layout
──────
  Left 960 px  : course viewport
  Right 320 px : HUD panel (src/ui/hud.py)
"""

import math
import random

import pygame

from src.golf.ball     import Ball, BallState
from src.golf.shot     import ShotController, ShotState, AIM_CLICK_RADIUS
from src.golf.terrain  import Terrain, TERRAIN_PROPS
from src.golf.club     import STARTER_BAG
from src.course.renderer import CourseRenderer
from src.ui.hud        import HUD
from src.utils.math_utils import clamp

# ── Layout constants ──────────────────────────────────────────────────────────
VIEWPORT_W = 960
VIEWPORT_H = 720

# Fraction of shot distance that the ball rolls after landing, by terrain.
# Putts never use this — they already ARE the roll.
_ROLL_FRAC = {
    Terrain.TEE:        0.18,
    Terrain.FAIRWAY:    0.18,
    Terrain.ROUGH:      0.04,
    Terrain.DEEP_ROUGH: 0.0,
    Terrain.BUNKER:     0.0,
    Terrain.TREES:      0.0,
    Terrain.GREEN:      0.08,
    Terrain.WATER:      0.0,
}
SCREEN_W   = 1280
SCREEN_H   = 720

# ── Colours ───────────────────────────────────────────────────────────────────
C_WHITE      = (255, 255, 255)
C_RED        = (220,  55,  55)
C_GREEN      = ( 60, 185,  60)
C_YELLOW     = (255, 220,   0)


class GolfRoundState:
    """Plays a single hole within a full round."""

    def __init__(self, game, course, hole_index, scores=None,
                 resume_state: dict | None = None):
        """
        Parameters
        ----------
        game         : Game — the main game object (used for state transitions)
        course       : Course — the 18-hole course being played
        hole_index   : int — 0-based index of the hole to play (0..17)
        scores       : list[int] — stroke totals already recorded
        resume_state : dict | None — mid-hole state to restore (ball pos,
                       strokes, wind). See `_collect_round_state()` for the
                       schema. When present, overrides the normal fresh-hole
                       initialisation after the hole is built.
        """
        self.game        = game
        self.course      = course
        self.hole_index  = hole_index
        self.scores      = list(scores) if scores else []

        # ── Build hole and renderer ───────────────────────────────────────────
        self.hole     = course.get_hole(hole_index)
        self.renderer = CourseRenderer(self.hole)
        self.tile_sz  = self.renderer.tile_size

        # ── Golf objects ──────────────────────────────────────────────────────
        tee_wx, tee_wy = self.renderer.get_tee_world_pos()
        self.ball     = Ball(tee_wx, tee_wy)

        # ── Camera — centred on the tee at startup ────────────────────────────
        self.cam_x = tee_wx - VIEWPORT_W / 2
        self.cam_y = tee_wy - VIEWPORT_H / 2
        self._clamp_camera()
        self.clubs    = list(game.player.clubs) if game.player else list(STARTER_BAG)
        self.club_idx = 0
        self.strokes  = 0

        self.shot_ctrl = ShotController()

        # ── UI ────────────────────────────────────────────────────────────────
        self.hud = HUD(SCREEN_W, SCREEN_H)

        self.font_big = pygame.font.SysFont("arial", 40, bold=True)
        self.font_med = pygame.font.SysFont("arial", 22)

        # ── Wind — randomised once per hole ──────────────────────────────────
        self.wind_angle    = random.uniform(0, 2 * math.pi)
        self.wind_strength = random.choices(
            [0, 1, 2, 3, 4, 5], weights=[10, 25, 30, 20, 10, 5])[0]

        # ── State flags ───────────────────────────────────────────────────────
        self.hole_complete  = False
        self.complete_timer = 0.0

        self.message       = ""
        self.message_timer = 0.0

        # ── Animation + audio ─────────────────────────────────────────────────
        self._flag_time       = 0.0
        self._score_snd_played = False

        # Start ambient sound (birds for lower tours, crowd for higher)
        from src.utils.sound_manager import SoundManager
        _snd = SoundManager.instance()
        if game.player and game.player.tour_level >= 4:
            _snd.play_ambient("ambient_crowd")
        else:
            _snd.play_ambient("ambient_birds")

        # Last safe ball position (for water drop / tree bounce)
        self._last_safe_x        = tee_wx
        self._last_safe_y        = tee_wy
        self._bounce_in_progress = False   # True while tree-bounce is animating

        self._auto_select_club()

        # Apply resume state if one was provided (from a mid-round save).
        # Applied after _auto_select_club so the club index we restore wins.
        if resume_state is not None:
            self._apply_resume_state(resume_state)

        # Pause overlay (ESC) state.
        self._paused = False
        self._pause_hover = None   # "resume" or "quit"

        # Show a one-time tutorial modal on the player's very first round.
        # Gated by Player.tutorial_seen so it only fires once per career.
        self._show_tutorial = (
            game.player is not None
            and not getattr(game.player, "tutorial_seen", False)
            and hole_index == 0
        )

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def current_club(self):
        return self.clubs[self.club_idx]

    def _ball_screen_pos(self):
        return (int(self.ball.x - self.cam_x),
                int(self.ball.y - self.cam_y))

    def _pin_world_pos(self):
        return self.renderer.get_pin_world_pos()

    def _pin_screen_pos(self):
        px, py = self._pin_world_pos()
        return (int(px - self.cam_x), int(py - self.cam_y))

    def _ball_terrain(self):
        return self.hole.get_terrain_at_pixel(self.ball.x, self.ball.y, self.tile_sz)

    def _effective_club(self):
        """Return a Club copy with stats scaled by player attributes + staff bonuses."""
        from src.golf.club import Club
        club   = self.current_club
        player = self.game.player
        if player is None:
            return club

        def eff(key):
            return player.stats.get(key, 50) + player.staff_stat_bonus(key)

        # Power scales distance: 50 = 1.0x, 80 = 1.15x
        power_mult = 1.0 + (eff("power") - 50) / 200.0

        if club.name == "Putter":
            acc_bonus = (eff("putting") - 50) / 500.0
        elif club.name in ("Pitching Wedge", "Sand Wedge"):
            acc_bonus = (eff("short_game") - 50) / 500.0
        else:
            acc_bonus = (eff("accuracy") - 50) / 500.0

        new_dist = club.max_distance_yards * power_mult
        new_acc  = club.accuracy + acc_bonus

        # B2-6: Fitness → late-round fatigue (kicks in after hole 12)
        if self.hole_index >= 12:
            fatigue = (self.hole_index - 11) * 0.01 * (1.0 - eff("fitness") / 100.0)
            new_acc *= (1.0 - fatigue)

        # B2-5: Mental → pressure penalty (tournament only, back 9, ≤3 strokes off lead)
        t = self.game.current_tournament
        if t is not None and self.hole_index >= 9:
            try:
                lb = t.get_live_leaderboard(len(self.scores), self.scores)
                leader_vp = lb[0]["vs_par"]
                player_vp = next(e["vs_par"] for e in lb if e["is_player"])
                strokes_back = max(0, player_vp - leader_vp)
                if strokes_back <= 3:
                    pressure = max(0.0, (3 - strokes_back) / 3.0) * (1.0 - eff("mental") / 100.0)
                    new_acc *= (1.0 - pressure * 0.25)
            except Exception:
                pass

        return Club(club.name, new_dist, min(0.99, new_acc), club.can_shape)

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event):
        # Tutorial modal eats the first input on a new career's first round.
        if self._show_tutorial:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self._dismiss_tutorial()
            return

        # Pause overlay — ESC toggles, clicks on its buttons act.
        if self._paused:
            self._handle_pause_event(event)
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Cancel any in-progress aim and open the pause menu.
            self.shot_ctrl.cancel()
            self._paused = True
            return

        if self.hole_complete:
            # After delay, any input moves to the next hole
            if (self.complete_timer > 1.2 and
                    event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN)):
                self._advance()
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._on_left_click(event.pos)
            elif event.button == 3:
                self.shot_ctrl.cancel()

        elif event.type == pygame.MOUSEMOTION:
            self.shot_ctrl.handle_mousemove(event.pos)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._on_left_release(event.pos)

        elif event.type == pygame.MOUSEWHEEL:
            direction = -1 if event.y > 0 else 1
            self._cycle_club(direction)

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_UP):
                self._cycle_club(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self._cycle_club(1)

    def _on_left_click(self, pos):
        if pos[0] >= VIEWPORT_W:
            self.club_idx = self.hud.handle_click(
                pos, self.shot_ctrl, self.clubs, self.club_idx)
            return

        if self.ball.state == BallState.AT_REST:
            self.shot_ctrl.handle_mousedown(pos, self._ball_screen_pos())

    def _on_left_release(self, pos):
        if pos[0] >= VIEWPORT_W:
            return
        if self.ball.state != BallState.AT_REST:
            return

        terrain = self._ball_terrain()
        result  = self.shot_ctrl.handle_mouseup(
            pos, self.ball.pos, self._effective_club(), terrain, self.tile_sz)

        if result is None:
            return

        from src.utils.sound_manager import SoundManager
        SoundManager.instance().play("swing")

        world_w, world_h = self.renderer.world_size()
        is_putt = (self.current_club.name == "Putter")

        # Wind drift — putts >15 yards get 20% of full drift; shorter putts unaffected
        if self.wind_strength == 0:
            wind_x = wind_y = 0.0
        elif is_putt:
            putt_yards = (math.sqrt((result.aim_x - self.ball.x) ** 2 +
                                    (result.aim_y - self.ball.y) ** 2)
                          / self.tile_sz * 10)
            if putt_yards > 15:
                wind_scale = self.tile_sz * 0.55 * 0.20
                wind_x = math.cos(self.wind_angle) * self.wind_strength * wind_scale
                wind_y = math.sin(self.wind_angle) * self.wind_strength * wind_scale
            else:
                wind_x = wind_y = 0.0
        else:
            wind_scale = self.tile_sz * 0.55
            wind_x = math.cos(self.wind_angle) * self.wind_strength * wind_scale
            wind_y = math.sin(self.wind_angle) * self.wind_strength * wind_scale

        aim_x = clamp(result.aim_x, 0, world_w - 1)
        aim_y = clamp(result.aim_y, 0, world_h - 1)
        target_x = clamp(aim_x + result.shape_x + wind_x, 0, world_w - 1)
        target_y = clamp(aim_y + result.shape_y + wind_y, 0, world_h - 1)

        # Roll distance — fraction of shot distance, scaled by landing terrain
        shot_dist_px = math.sqrt((aim_x - self.ball.x) ** 2 +
                                 (aim_y - self.ball.y) ** 2)
        roll_dist_px = shot_dist_px * _ROLL_FRAC.get(terrain, 0.0)

        self._last_safe_x = self.ball.x
        self._last_safe_y = self.ball.y

        self.strokes += 1
        self.ball.hit(target_x, target_y, is_putt=is_putt,
                      aim_x=aim_x, aim_y=aim_y,
                      shape_x=result.shape_x, shape_y=result.shape_y,
                      wind_x=wind_x, wind_y=wind_y,
                      roll_dist_px=roll_dist_px)

    def _cycle_club(self, direction):
        self.club_idx = (self.club_idx + direction) % len(self.clubs)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self._flag_time += dt

        from src.utils.sound_manager import SoundManager
        SoundManager.instance().update(dt)

        # Freeze simulation while paused — flag/ambient still tick, but the
        # ball, camera, and message timers stay still until the player resumes.
        if self._paused:
            return

        if self.hole_complete:
            self.complete_timer += dt
            return

        self.ball.update(dt, self._pin_world_pos())

        # ── Mid-flight tree collision ─────────────────────────────────────────
        # Check on every frame while airborne — trees block the ball immediately
        # rather than waiting for it to land on the other side.
        if self.ball.state == BallState.FLYING:
            if self._ball_terrain() == Terrain.TREES:
                self._handle_tree_collision()

        # ── Normal landing ────────────────────────────────────────────────────
        if (self.shot_ctrl.state == ShotState.EXECUTING
                and self.ball.state == BallState.AT_REST):
            self._on_ball_landed()

        # Tree-bounce completed — ball came to rest after bouncing out
        if self._bounce_in_progress and self.ball.state == BallState.AT_REST:
            self._bounce_in_progress = False
            self._auto_select_club()

        if self.ball.state == BallState.IN_HOLE:
            self.hole_complete  = True
            self.complete_timer = 0.0
            self._play_score_sound()

        # Stop the roll immediately if the ball enters heavy terrain
        if self.ball.state == BallState.ROLLING:
            roll_terrain = self._ball_terrain()
            if roll_terrain in (Terrain.BUNKER, Terrain.WATER,
                                Terrain.TREES, Terrain.DEEP_ROUGH):
                self.ball.stop_roll()

        if self.ball.state in (BallState.FLYING, BallState.ROLLING):
            self._follow_camera(dt)

        if self.message_timer > 0:
            self.message_timer -= dt

    def _handle_tree_collision(self):
        """
        Ball has entered tree terrain mid-flight.
        Walk backward along the trajectory until we find the tree boundary,
        place the ball there, then launch a bounce back toward open ground.
        """
        # Step back from current position toward the shot origin until
        # we land on non-tree terrain — that is the impact point.
        start_x = self.ball._start_x
        start_y = self.ball._start_y
        dx = start_x - self.ball.x
        dy = start_y - self.ball.y
        total = math.sqrt(dx * dx + dy * dy)

        impact_x, impact_y = self.ball.x, self.ball.y   # fallback

        if total > 0:
            ndx, ndy = dx / total, dy / total
            step = max(1.0, self.tile_sz * 0.5)
            steps = int(total / step) + 4
            for i in range(1, steps):
                tx = self.ball.x + ndx * step * i
                ty = self.ball.y + ndy * step * i
                if self.hole.get_terrain_at_pixel(tx, ty, self.tile_sz) != Terrain.TREES:
                    impact_x, impact_y = tx, ty
                    break

        # Plant the ball at the tree edge
        self.ball.place(impact_x, impact_y)

        if self._bounce_in_progress:
            # The bounce itself flew into trees — just stop here, no further bounce
            self._bounce_in_progress = False
            self._auto_select_club()
        else:
            # Initial shot — reset controller and send ball bouncing back
            self._show_message(self._trees_toast_text(), 2.4)
            self.shot_ctrl.on_ball_landed()
            self._do_tree_bounce()

    def _trees_toast_text(self) -> str:
        """Pick between 'Out of bounds' and 'In the trees' based on where the
        ball stopped relative to the hole grid. The edge rows/cols are treated
        as OOB — they are the tree wall that borders the course.
        """
        col = int(self.ball.x // self.tile_sz)
        row = int(self.ball.y // self.tile_sz)
        edge_margin = 2
        near_edge = (
            col < edge_margin or col >= self.hole.cols - edge_margin or
            row < edge_margin or row >= self.hole.rows - edge_margin)
        return "Out of bounds — dropped back" if near_edge else "In the trees — bounced out"

    def _do_tree_bounce(self):
        """Launch the ball back from the trees toward safe ground."""
        dx = self._last_safe_x - self.ball.x
        dy = self._last_safe_y - self.ball.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= 0:
            self._auto_select_club()
            return

        # The ball's speed at impact is proportional to how far it still had
        # to travel (remaining_dist), NOT how far it has already come (dist).
        # Using dist caused long shots that barely clipped a tree near their
        # target to rebound much faster than they were travelling at impact.
        rdx = self.ball._target_x - self.ball.x
        rdy = self.ball._target_y - self.ball.y
        remaining_dist = math.sqrt(rdx * rdx + rdy * rdy)

        # Bounce scales with remaining energy; minimum 10 px so it always moves
        bounce_px  = max(10.0, remaining_dist) * random.uniform(0.25, 0.45)
        angle      = math.atan2(dy, dx) + random.uniform(-0.4, 0.4)
        world_w, world_h = self.renderer.world_size()
        bx = clamp(self.ball.x + math.cos(angle) * bounce_px, 0, world_w - 1)
        by = clamp(self.ball.y + math.sin(angle) * bounce_px, 0, world_h - 1)
        self.ball.hit(bx, by, is_putt=False)
        self._bounce_in_progress = True

    def _water_drop_pos(self):
        """
        Walk from the ball's water position back toward the last safe position,
        one small step at a time, and return the first tile that isn't water.
        Guarantees the drop is never placed in the water.
        """
        bx, by = self.ball.x, self.ball.y
        dx = self._last_safe_x - bx
        dy = self._last_safe_y - by
        dist = math.sqrt(dx * dx + dy * dy)

        if dist == 0:
            return self._last_safe_x, self._last_safe_y

        ndx, ndy = dx / dist, dy / dist
        step = max(1.0, self.tile_sz * 0.25)

        pos_x, pos_y = bx, by
        travelled = 0.0
        while travelled < dist + step:
            travelled += step
            tx = bx + ndx * min(travelled, dist)
            ty = by + ndy * min(travelled, dist)
            if self.hole.get_terrain_at_pixel(tx, ty, self.tile_sz) != Terrain.WATER:
                return tx, ty

        return self._last_safe_x, self._last_safe_y

    def _on_ball_landed(self):
        self.shot_ctrl.on_ball_landed()
        terrain = self._ball_terrain()

        # Terrain landing sound
        from src.utils.sound_manager import SoundManager
        _snd = SoundManager.instance()
        _terrain_snd = {
            Terrain.WATER:      "hit_water",
            Terrain.BUNKER:     "hit_bunker",
            Terrain.TREES:      "hit_trees",
            Terrain.ROUGH:      "hit_rough",
            Terrain.DEEP_ROUGH: "hit_rough",
        }
        _snd.play(_terrain_snd.get(terrain, "hit"))

        # Trees: mid-flight check should catch this first, but handle as fallback
        if terrain == Terrain.TREES:
            self._show_message(self._trees_toast_text(), 2.4)
            self._do_tree_bounce()
            return

        # ── Water hazard ──────────────────────────────────────────────────────
        if terrain == Terrain.WATER:
            self.strokes += 1
            self._show_message("Water hazard! +1 penalty stroke", 2.8)
            drop_x, drop_y = self._water_drop_pos()
            self.ball.place(drop_x, drop_y)
        elif terrain == Terrain.DEEP_ROUGH:
            self._show_message("Deep rough — tough lie", 1.8)
        elif terrain == Terrain.BUNKER:
            self._show_message("In the bunker", 1.6)

        self._auto_select_club()

    def _play_score_sound(self):
        if self._score_snd_played:
            return
        self._score_snd_played = True
        from src.utils.sound_manager import SoundManager
        _snd = SoundManager.instance()
        diff = self.strokes - self.hole.par
        if self.strokes == 1:
            _snd.play("hole_in_one")
        elif diff <= -2:
            _snd.play("eagle")
        elif diff == -1:
            _snd.play("birdie")
        else:
            _snd.play("ball_in_hole")

    def _auto_select_club(self):
        terrain = self._ball_terrain()

        if terrain == Terrain.GREEN:
            for i, c in enumerate(self.clubs):
                if c.name == "Putter":
                    self.club_idx = i
                    return

        if terrain == Terrain.BUNKER:
            for i, c in enumerate(self.clubs):
                if c.name == "Sand Wedge":
                    self.club_idx = i
                    return

        pin_wx, pin_wy = self._pin_world_pos()
        dist_px = math.sqrt((self.ball.x - pin_wx) ** 2 +
                            (self.ball.y - pin_wy) ** 2)
        dist_yards = dist_px / self.tile_sz * 10
        dist_mod   = TERRAIN_PROPS[terrain]['dist_mod']

        best_idx  = 0
        best_diff = float('inf')

        for i, club in enumerate(self.clubs):
            if club.name == "Putter":
                continue
            effective_max = club.max_distance_yards * dist_mod
            diff = abs(effective_max - dist_yards)
            if diff < best_diff:
                best_diff = diff
                best_idx  = i

        self.club_idx = best_idx

    def _follow_camera(self, dt):
        target_cx = self.ball.x - VIEWPORT_W / 2
        target_cy = self.ball.y - VIEWPORT_H / 2
        speed = 4.0 * dt
        self.cam_x += (target_cx - self.cam_x) * speed
        self.cam_y += (target_cy - self.cam_y) * speed
        self._clamp_camera()

    def _clamp_camera(self):
        world_w, world_h = self.renderer.world_size()
        self.cam_x = clamp(self.cam_x, 0, max(0, world_w - VIEWPORT_W))
        self.cam_y = clamp(self.cam_y, 0, max(0, world_h - VIEWPORT_H))

    def _show_message(self, text, duration):
        self.message       = text
        self.message_timer = duration

    def _advance(self):
        """Move to the hole-transition screen (or round summary if last hole)."""
        from src.states.hole_transition import HoleTransitionState
        from src.states.round_summary   import RoundSummaryState
        from src.utils.sound_manager    import SoundManager
        SoundManager.instance().stop_ambient()

        updated_scores = self.scores + [self.strokes]

        if self.hole_index >= 17:
            # All 18 holes done — show final scorecard
            self.game.change_state(RoundSummaryState(self.game, self.course, updated_scores))
        else:
            # Show between-hole scorecard, then continue
            self.game.change_state(
                HoleTransitionState(self.game, self.course, self.hole_index, updated_scores))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface):
        viewport = pygame.Rect(0, 0, VIEWPORT_W, VIEWPORT_H)

        surface.fill((20, 80, 20))
        self.renderer.draw(surface, int(self.cam_x), int(self.cam_y), viewport)
        self.renderer.draw_animated_elements(
            surface, int(self.cam_x), int(self.cam_y), self._flag_time)

        # Faint click-zone ring around the ball while idle, to teach the click radius.
        if (self.shot_ctrl.state == ShotState.IDLE
                and self.ball.state == BallState.AT_REST
                and not self.hole_complete):
            bsx, bsy = self._ball_screen_pos()
            if 0 <= bsx <= VIEWPORT_W and 0 <= bsy <= VIEWPORT_H:
                ring = pygame.Surface((AIM_CLICK_RADIUS * 2 + 4,
                                       AIM_CLICK_RADIUS * 2 + 4),
                                      pygame.SRCALPHA)
                pygame.draw.circle(
                    ring, (255, 255, 255, 55),
                    (AIM_CLICK_RADIUS + 2, AIM_CLICK_RADIUS + 2),
                    AIM_CLICK_RADIUS, 1)
                surface.blit(ring, (bsx - AIM_CLICK_RADIUS - 2,
                                    bsy - AIM_CLICK_RADIUS - 2))

        aim = self.shot_ctrl.get_aim_line(self._ball_screen_pos())
        if aim:
            self._draw_aim_arrow(surface, *aim)

        self.ball.draw(surface, int(self.cam_x), int(self.cam_y))

        self._draw_pin_indicator(surface)

        if self.ball.state == BallState.AT_REST and not self.hole_complete:
            self._draw_distance_to_pin(surface)

        terrain_name = TERRAIN_PROPS[self._ball_terrain()]['name']
        self.hud.draw(surface, self.hole, self.strokes,
                      self.current_club, self.shot_ctrl, terrain_name,
                      renderer=self.renderer, ball_world_pos=self.ball.pos,
                      wind_angle=self.wind_angle, wind_strength=self.wind_strength)

        if self.message and self.message_timer > 0:
            self._draw_message(surface)

        if self.hole_complete:
            self._draw_complete_overlay(surface)

        if self._show_tutorial:
            self._draw_tutorial_overlay(surface)

        if self._paused:
            self._draw_pause_overlay(surface)

    def _dismiss_tutorial(self):
        self._show_tutorial = False
        if self.game.player is not None:
            self.game.player.tutorial_seen = True

    def _draw_tutorial_overlay(self, surface):
        # Dim the course; leave the HUD visible so players can see what the
        # text refers to.
        dim = pygame.Surface((VIEWPORT_W, VIEWPORT_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))

        pw, ph = 560, 340
        px = (VIEWPORT_W - pw) // 2
        py = (VIEWPORT_H - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surface, (14, 22, 14), panel, border_radius=12)
        pygame.draw.rect(surface, (58, 98, 58), panel, 2, border_radius=12)

        font_title = pygame.font.SysFont("arial", 30, bold=True)
        font_line  = pygame.font.SysFont("arial", 20)
        font_hint  = pygame.font.SysFont("arial", 16)

        title = font_title.render("How to play", True, (168, 224, 88))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 22))

        lines = [
            "1.  Left-click near the ball to start aiming.",
            "2.  Drag away from the ball — distance = power, direction = aim.",
            "3.  Release to take the shot.  Right-click cancels.",
            "",
            "Scroll wheel / arrow keys change clubs.",
            "The putter is auto-selected on the green.",
            "Wind, lie and club stats are shown in the HUD on the right.",
        ]
        ly = panel.y + 78
        for text in lines:
            if text:
                s = font_line.render(text, True, (230, 230, 230))
                surface.blit(s, (panel.x + 32, ly))
            ly += 30

        hint = font_hint.render("Click anywhere to continue.", True, (180, 200, 160))
        surface.blit(hint, (panel.centerx - hint.get_width() // 2,
                            panel.bottom - 34))

    # ── Pause / resume ────────────────────────────────────────────────────────

    def _pause_rects(self):
        pw, ph = 420, 230
        px = (VIEWPORT_W - pw) // 2
        py = (VIEWPORT_H - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        bw, bh = 260, 44
        resume = pygame.Rect(panel.centerx - bw // 2, panel.y + 90,  bw, bh)
        quit_  = pygame.Rect(panel.centerx - bw // 2, panel.y + 150, bw, bh)
        return panel, resume, quit_

    def _handle_pause_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._paused = False
            return
        _, resume, quit_ = self._pause_rects()
        if event.type == pygame.MOUSEMOTION:
            p = event.pos
            self._pause_hover = (
                "resume" if resume.collidepoint(p) else
                "quit"   if quit_.collidepoint(p)  else
                None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            p = event.pos
            if resume.collidepoint(p):
                self._paused = False
            elif quit_.collidepoint(p):
                self._save_and_quit_to_menu()

    def _save_and_quit_to_menu(self):
        """Persist the in-progress round and return to the main menu."""
        try:
            from src.utils.save_system import save_game
            save_game(self.game.player,
                      self.game.current_tournament,
                      round_state=self._collect_round_state())
        except Exception as e:
            print(f"Mid-round save failed: {e}")
        from src.states.main_menu import MainMenuState
        self.game.change_state(MainMenuState(self.game))

    def _collect_round_state(self) -> dict:
        """Snapshot everything needed to resume this hole mid-round."""
        return {
            "hole_index":    self.hole_index,
            "strokes":       self.strokes,
            "scores":        list(self.scores),
            "ball_x":        float(self.ball.x),
            "ball_y":        float(self.ball.y),
            "wind_angle":    float(self.wind_angle),
            "wind_strength": int(self.wind_strength),
            "last_safe_x":   float(self._last_safe_x),
            "last_safe_y":   float(self._last_safe_y),
            "club_idx":      int(self.club_idx),
        }

    def _apply_resume_state(self, s: dict) -> None:
        """Restore the mid-hole state captured by `_collect_round_state`."""
        self.strokes       = int(s.get("strokes", 0))
        self.scores        = list(s.get("scores", self.scores))
        bx = s.get("ball_x")
        by = s.get("ball_y")
        if bx is not None and by is not None:
            self.ball.place(float(bx), float(by))
        self.wind_angle    = float(s.get("wind_angle", self.wind_angle))
        self.wind_strength = int(s.get("wind_strength", self.wind_strength))
        self._last_safe_x  = float(s.get("last_safe_x", self.ball.x))
        self._last_safe_y  = float(s.get("last_safe_y", self.ball.y))
        ci = int(s.get("club_idx", self.club_idx))
        if 0 <= ci < len(self.clubs):
            self.club_idx = ci
        # Recentre camera on the restored ball position.
        self.cam_x = self.ball.x - VIEWPORT_W / 2
        self.cam_y = self.ball.y - VIEWPORT_H / 2
        self._clamp_camera()

    def _draw_pause_overlay(self, surface):
        dim = pygame.Surface((VIEWPORT_W, VIEWPORT_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))

        panel, resume, quit_ = self._pause_rects()
        pygame.draw.rect(surface, (14, 22, 14), panel, border_radius=12)
        pygame.draw.rect(surface, (58, 98, 58), panel, 2, border_radius=12)

        title_font = pygame.font.SysFont("arial", 28, bold=True)
        body_font  = pygame.font.SysFont("arial", 18)
        btn_font   = pygame.font.SysFont("arial", 20, bold=True)

        title = title_font.render("Paused", True, (168, 224, 88))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 22))

        hint = body_font.render(
            "Save & Quit returns to the main menu. You can load this save to continue.",
            True, (190, 200, 180))
        if hint.get_width() > panel.width - 32:
            # Wrap on two lines if it's too wide.
            hint1 = body_font.render("Save & Quit returns to the main menu.", True, (190, 200, 180))
            hint2 = body_font.render("Load this save to continue.",            True, (190, 200, 180))
            surface.blit(hint1, (panel.centerx - hint1.get_width() // 2, panel.y + 56))
            surface.blit(hint2, (panel.centerx - hint2.get_width() // 2, panel.y + 74))
        else:
            surface.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 60))

        for rect, key, label in [(resume, "resume", "Resume (Esc)"),
                                 (quit_,  "quit",   "Save & Quit to Menu")]:
            hov = (self._pause_hover == key)
            bg  = (48, 120, 48) if hov else (28, 78, 28)
            pygame.draw.rect(surface, bg, rect, border_radius=7)
            pygame.draw.rect(surface, (58, 98, 58), rect, 2, border_radius=7)
            lbl = btn_font.render(label, True, (255, 255, 255))
            surface.blit(lbl, lbl.get_rect(center=rect.center))

    def _draw_aim_arrow(self, surface, start, end, power):
        from src.golf.shot import ShotShape, SHAPE_CURVE_FRACTION
        r = int(min(255, power * 2 * 255))
        g = int(min(255, (1.0 - power) * 2 * 255))
        color = (r, g, 0)

        sx, sy = int(start[0]), int(start[1])
        ex, ey = int(end[0]),   int(end[1])

        dx, dy = ex - sx, ey - sy
        mag = math.sqrt(dx * dx + dy * dy)

        # If the player has a non-straight shot shape and the club allows
        # shaping, draw a quadratic-bezier aim line that previews the curve.
        shape = self.shot_ctrl.shot_shape
        can_shape = self.current_club.can_shape
        if (mag > 0 and can_shape
                and shape in (ShotShape.DRAW, ShotShape.FADE)):
            # Perpendicular offset matches the in-flight shape maths in shot.py:
            # DRAW curves to the left (perp = (-dy, dx)/mag, negated),
            # FADE curves to the right.
            sign = -1.0 if shape == ShotShape.DRAW else 1.0
            perp_x = -dy / mag
            perp_y =  dx / mag
            control_offset = mag * SHAPE_CURVE_FRACTION * sign
            cx = (sx + ex) / 2 + perp_x * control_offset
            cy = (sy + ey) / 2 + perp_y * control_offset
            # Sample the bezier at 16 segments.
            prev = (sx, sy)
            for i in range(1, 17):
                t = i / 16.0
                u = 1.0 - t
                x = int(u * u * sx + 2 * u * t * cx + t * t * ex)
                y = int(u * u * sy + 2 * u * t * cy + t * t * ey)
                pygame.draw.line(surface, color, prev, (x, y), 3)
                prev = (x, y)
            # Arrow-head tangent at t=1: derivative 2*(1-t)*(cp-p0)+2*t*(p1-cp)
            # at t=1 that's 2*(p1-cp).
            tx, ty = (ex - cx), (ey - cy)
        else:
            pygame.draw.line(surface, color, (sx, sy), (ex, ey), 3)
            tx, ty = dx, dy

        tmag = math.sqrt(tx * tx + ty * ty)
        if tmag > 0:
            ndx, ndy = tx / tmag, ty / tmag
            size = 12
            tip   = (ex, ey)
            left  = (int(ex - ndx * size + ndy * 5), int(ey - ndy * size - ndx * 5))
            right = (int(ex - ndx * size - ndy * 5), int(ey - ndy * size + ndx * 5))
            pygame.draw.polygon(surface, color, [tip, left, right])

    def _draw_pin_indicator(self, surface):
        psx, psy = self._pin_screen_pos()
        if 20 <= psx <= VIEWPORT_W - 20 and 20 <= psy <= VIEWPORT_H - 20:
            return

        cx, cy = VIEWPORT_W // 2, VIEWPORT_H // 2
        angle  = math.atan2(psy - cy, psx - cx)
        margin = 38
        ind_x  = int(cx + math.cos(angle) * (VIEWPORT_W // 2 - margin))
        ind_y  = int(cy + math.sin(angle) * (VIEWPORT_H // 2 - margin))
        ind_x  = clamp(ind_x, margin, VIEWPORT_W - margin)
        ind_y  = clamp(ind_y, margin, VIEWPORT_H - margin)

        pygame.draw.circle(surface, C_YELLOW, (ind_x, ind_y), 14, 2)

        pin_wx, pin_wy = self._pin_world_pos()
        dist_yd = int(math.sqrt((self.ball.x - pin_wx) ** 2 +
                                (self.ball.y - pin_wy) ** 2)
                      / self.tile_sz * 10)
        lbl = self.font_med.render(f"{dist_yd}y", True, C_YELLOW)
        surface.blit(lbl, (ind_x - lbl.get_width() // 2, ind_y + 16))

    def _draw_distance_to_pin(self, surface):
        pin_wx, pin_wy = self._pin_world_pos()
        dist_yd = int(math.sqrt((self.ball.x - pin_wx) ** 2 +
                                (self.ball.y - pin_wy) ** 2)
                      / self.tile_sz * 10)
        bsx, bsy = self._ball_screen_pos()
        lbl = self.font_med.render(f"{dist_yd} yds to pin", True, C_YELLOW)
        lx  = clamp(bsx - lbl.get_width() // 2, 4, VIEWPORT_W - lbl.get_width() - 4)
        ly  = clamp(bsy - 26, 4, VIEWPORT_H - 20)
        surface.blit(lbl, (lx, ly))

    def _draw_message(self, surface):
        lbl = self.font_med.render(self.message, True, (255, 230, 80))
        x   = (VIEWPORT_W - lbl.get_width()) // 2
        surface.blit(lbl, (x, 28))

    def _draw_complete_overlay(self, surface):
        overlay = pygame.Surface((VIEWPORT_W, VIEWPORT_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 155))
        surface.blit(overlay, (0, 0))

        cx = VIEWPORT_W // 2

        diff = self.strokes - self.hole.par
        if self.strokes == 1:
            label, color = "Hole in One!", C_YELLOW
        else:
            score_labels = {
                -3: ("Albatross!",   C_YELLOW),
                -2: ("Eagle!",       C_GREEN),
                -1: ("Birdie!",      C_GREEN),
                 0: ("Par",          C_WHITE),
                 1: ("Bogey",        C_RED),
                 2: ("Double Bogey", C_RED),
            }
            label, color = score_labels.get(
                diff, (f"+{diff}" if diff > 0 else str(diff), C_RED))

        self._blit_centred(surface, f"Hole {self.hole.number} Complete!",
                           self.font_big, C_WHITE, cx, 220)
        self._blit_centred(surface, label, self.font_big, color, cx, 278)
        self._blit_centred(surface,
                           f"{self.strokes} strokes   (Par {self.hole.par})",
                           self.font_med, (190, 190, 190), cx, 340)

        # Running total vs course par
        total_strokes = sum(self.scores) + self.strokes
        total_par     = self.course.total_par_through(self.hole_index + 1)
        total_diff    = total_strokes - total_par
        total_txt     = (f"Round total: {total_strokes}  "
                         f"({'E' if total_diff == 0 else ('+' + str(total_diff) if total_diff > 0 else str(total_diff))})")
        self._blit_centred(surface, total_txt, self.font_med, (160, 200, 160), cx, 372)

        if self.complete_timer > 1.2:
            next_label = ("Click to see final scorecard"
                          if self.hole_index >= 17
                          else "Click to continue to next hole")
            self._blit_centred(surface, next_label,
                               self.font_med, (155, 155, 155), cx, 416)

    def _blit_centred(self, surface, text, font, color, cx, y):
        surf = font.render(text, True, color)
        surface.blit(surf, (cx - surf.get_width() // 2, y))
