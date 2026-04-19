"""
Shot controller — manages the click-drag input system for taking shots.

How it works
------------
1. Player LEFT-CLICKS near the ball → enters AIMING state.
2. Player DRAGS the mouse away from click point → the direction of drag
   becomes the shot direction; drag distance sets power (capped at MAX_DRAG).
3. Player RELEASES the mouse button → shot fires, returns the world-pixel
   landing position.

Shot shaping
------------
DRAW curves the ball slightly to the left (relative to shot direction).
FADE curves it right. Straight goes true.
"""

import math
import random
from collections import namedtuple
from enum import Enum, auto

from src.golf.terrain import Terrain, TERRAIN_PROPS
from src.utils.math_utils import normalize, clamp

ShotResult = namedtuple('ShotResult', ['target_x', 'target_y', 'aim_x', 'aim_y', 'shape_x', 'shape_y'])

# How far (px) the player must drag to reach 100% power.
MAX_DRAG_PIXELS = 130

# Click must be within this many screen pixels of the ball to start aiming.
AIM_CLICK_RADIUS = 50

# How much lateral curve is applied as a fraction of total shot distance.
SHAPE_CURVE_FRACTION = 0.15

# Scatter multipliers (fraction of shot distance).
# Lateral: perpendicular miss — bell-curve via gauss.
# Distance: over/under-shoot along the shot direction.
SCATTER_LATERAL   = 0.40
SCATTER_DISTANCE  = 0.12


class ShotShape(Enum):
    DRAW     = "Draw"
    STRAIGHT = "Straight"
    FADE     = "Fade"


class ShotState(Enum):
    IDLE      = auto()   # No shot in progress, waiting for click
    AIMING    = auto()   # Player is dragging to set direction and power
    EXECUTING = auto()   # Ball is currently flying


class ShotController:
    """Manages all shot input and calculates the landing position."""

    def __init__(self):
        self.state       = ShotState.IDLE
        self.shot_shape  = ShotShape.STRAIGHT

        # Mouse positions in screen coordinates
        self._drag_start   = None
        self._drag_current = None

    # ── Mouse event handlers ───────────────────────────────────────────────────

    def handle_mousedown(self, screen_pos, ball_screen_pos):
        """
        Called on left mouse button press.
        Only starts aiming if the click is close enough to the ball.
        """
        if self.state != ShotState.IDLE:
            return

        bx, by = ball_screen_pos
        mx, my = screen_pos
        if math.sqrt((mx - bx) ** 2 + (my - by) ** 2) <= AIM_CLICK_RADIUS:
            self.state         = ShotState.AIMING
            self._drag_start   = screen_pos
            self._drag_current = screen_pos

    def handle_mousemove(self, screen_pos):
        """Called on every mouse-move event."""
        if self.state == ShotState.AIMING:
            self._drag_current = screen_pos

    def handle_mouseup(self, screen_pos, ball_world_pos, club, current_terrain, tile_size):
        """
        Called on left mouse button release.
        Calculates the landing position and returns it as (world_x, world_y),
        or None if the drag was too small / invalid.
        """
        if self.state != ShotState.AIMING:
            return None

        self._drag_current = screen_pos

        dx = self._drag_current[0] - self._drag_start[0]
        dy = self._drag_current[1] - self._drag_start[1]
        drag_dist = math.sqrt(dx * dx + dy * dy)

        # Ignore tiny drags (accidental clicks)
        if drag_dist < 6:
            self.state = ShotState.IDLE
            return None

        # Power fraction 0..1 based on drag distance
        power = clamp(drag_dist / MAX_DRAG_PIXELS, 0.0, 1.0)

        # Normalised shot direction (same direction as drag)
        dir_x, dir_y = normalize(dx, dy)

        # Fetch terrain modifiers for where the ball currently sits
        props    = TERRAIN_PROPS[current_terrain]
        dist_mod = props['dist_mod']
        acc_mod  = props['acc_mod']

        # Can't hit from water (handled as a penalty elsewhere)
        if current_terrain == Terrain.WATER:
            self.state = ShotState.IDLE
            return None

        # Convert club distance (yards) to world pixels
        # Scale: 10 yards per tile, tile_size pixels per tile
        yards_per_pixel = 10.0 / tile_size
        max_dist_px = (club.max_distance_yards / 10.0) * tile_size

        # Apply power and terrain penalty
        shot_dist_px = power * max_dist_px * dist_mod

        # Shot shaping: lateral offset perpendicular to the shot direction
        # Perpendicular clockwise = (dir_y, -dir_x), counter-clockwise = (-dir_y, dir_x)
        perp_x = -dir_y   # perpendicular left
        perp_y =  dir_x
        shape_offset_px = 0.0
        shape_frac = SHAPE_CURVE_FRACTION * getattr(club, "shape_mult", 1.0)
        if self.shot_shape == ShotShape.DRAW and club.can_shape:
            shape_offset_px = -shot_dist_px * shape_frac   # left curve
        elif self.shot_shape == ShotShape.FADE and club.can_shape:
            shape_offset_px =  shot_dist_px * shape_frac   # right curve

        # Effective accuracy — putter degrades with distance; other clubs use terrain mod
        if club.name == "Putter":
            shot_dist_yards = shot_dist_px / tile_size * 10.0
            degradation = (shot_dist_yards / 100.0) * 0.40
            effective_accuracy = max(0.50, club.accuracy - degradation) * acc_mod
        else:
            effective_accuracy = club.accuracy * acc_mod

        # Lateral scatter (perpendicular) — bell-curve via gauss, clamped to ±range
        lat_range = (1.0 - effective_accuracy) * shot_dist_px * SCATTER_LATERAL
        lateral   = clamp(random.gauss(0, lat_range / 2.5), -lat_range, lat_range)

        # Distance scatter (along shot direction) — over/undershoot
        dist_range   = shot_dist_px * SCATTER_DISTANCE
        dist_scatter = clamp(random.gauss(0, dist_range / 2.5), -dist_range, dist_range)

        # Straight aim point adjusted for distance scatter
        bx, by = ball_world_pos
        aim_x = bx + dir_x * (shot_dist_px + dist_scatter)
        aim_y = by + dir_y * (shot_dist_px + dist_scatter)

        # Shape + lateral scatter as perpendicular offset (applied quadratically by ball.py)
        total_offset = shape_offset_px + lateral
        shape_x = perp_x * total_offset
        shape_y = perp_y * total_offset

        # Actual landing position (wind added separately in golf_round.py)
        target_x = aim_x + shape_x
        target_y = aim_y + shape_y

        self.state = ShotState.EXECUTING
        return ShotResult(target_x, target_y, aim_x, aim_y, shape_x, shape_y)

    def on_ball_landed(self):
        """Call this when the ball finishes its flight animation."""
        self.state = ShotState.IDLE

    def cancel(self):
        """Cancel an in-progress aim (e.g. right-click)."""
        self.state         = ShotState.IDLE
        self._drag_start   = None
        self._drag_current = None

    # ── Query helpers ──────────────────────────────────────────────────────────

    def get_power(self):
        """Current power fraction 0..1. Only meaningful during AIMING."""
        if self.state != ShotState.AIMING or not self._drag_current:
            return 0.0
        dx = self._drag_current[0] - self._drag_start[0]
        dy = self._drag_current[1] - self._drag_start[1]
        return clamp(math.sqrt(dx * dx + dy * dy) / MAX_DRAG_PIXELS, 0.0, 1.0)

    def get_aim_line(self, ball_screen_pos):
        """
        Return ((start_x, start_y), (end_x, end_y), power) for drawing
        the aim arrow, or None if not currently aiming.
        The line originates at the ball and points in the shot direction.
        """
        if self.state != ShotState.AIMING or not self._drag_current:
            return None

        bx, by = ball_screen_pos
        dx = self._drag_current[0] - self._drag_start[0]
        dy = self._drag_current[1] - self._drag_start[1]
        drag_dist = math.sqrt(dx * dx + dy * dy)

        if drag_dist == 0:
            return None

        power  = clamp(drag_dist / MAX_DRAG_PIXELS, 0.0, 1.0)
        ndx, ndy = dx / drag_dist, dy / drag_dist

        # Arrow length scales slightly with power so player gets visual feedback
        line_len = 60 + power * 50
        end_x = bx + ndx * line_len
        end_y = by + ndy * line_len

        return ((bx, by), (end_x, end_y), power)
