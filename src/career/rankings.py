"""
rankings.py — World Golf Rankings system.

Points are earned at Tour Level 4+ (Continental Tour and above).
Majors award double points.  The player's world rank is computed against
a pool of 200 simulated world-tour professionals.

Expected career arc to reach World No. 1:
  ~2 full Grand Tour seasons performing well + winning 2+ majors ≈ 450-550 pts
  The #1 spot in the pool starts at ~500 pts.
"""

import random as _random

# ── Points per finishing position per tour level ──────────────────────────────
# Index 0 = 1st place
_PTS: dict[int, list[float]] = {
    4: [10,  6,  4,  3,  2,  1,  1,  1,  1,  1],
    5: [25, 15, 10,  7,  5,  3,  3,  3,  2,  2,
         1,  1,  1,  1,  1,  1,  1,  1,  1,  1],
    6: [50, 30, 20, 14, 10,  6,  6,  6,  4,  4,
         4,  4,  4,  2,  2,  2,  2,  2,  2,  2],
}

MAJOR_MULTIPLIER = 2.0


def get_ranking_points(tour_level: int, position: int,
                       is_major: bool = False) -> float:
    """Ranking points for a given finishing position at a tour level."""
    pts_list = _PTS.get(tour_level, [])
    if not pts_list:
        return 0.0
    idx = min(position - 1, len(pts_list) - 1)
    pts = pts_list[idx] if idx >= 0 else 0.0
    return pts * (MAJOR_MULTIPLIER if is_major else 1.0)


# ── World ranking pool ────────────────────────────────────────────────────────
# 200 simulated world-tour professionals with pre-seeded career points.
# Fixed seed so the pool is always the same — only the player's points change.

def _build_pool() -> list[float]:
    rng = _random.Random(2024)
    pts = []
    # Slots 1-10:  450-530 pts (elite)
    for _ in range(10):
        pts.append(rng.uniform(450, 530))
    # Slots 11-30: 300-450 pts
    for _ in range(20):
        pts.append(rng.uniform(290, 450))
    # Slots 31-80: 120-300 pts
    for _ in range(50):
        pts.append(rng.uniform(100, 300))
    # Slots 81-150: 30-120 pts
    for _ in range(70):
        pts.append(rng.uniform(20, 120))
    # Slots 151-200: 1-30 pts
    for _ in range(50):
        pts.append(rng.uniform(1, 30))
    return sorted(pts, reverse=True)


_POOL: list[float] = _build_pool()


def compute_world_rank(player_points: float) -> int:
    """Return the player's 1-based world ranking given their career points."""
    rank = 1
    for p in _POOL:
        if p > player_points:
            rank += 1
        else:
            break
    return rank


def rank_label(rank: int) -> str:
    """Human-readable rank label, e.g. 'World No. 1' or 'No. 47 in the World'."""
    if rank == 1:
        return "World No. 1"
    if rank <= 10:
        return f"World No. {rank}"
    if rank <= 200:
        return f"No. {rank} in the World"
    return "Unranked"
