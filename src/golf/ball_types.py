"""
Ball types — a second equipment slot with distinct playstyle trade-offs.

Where club sets are a strictly-linear ladder ("can I afford the next tier?"),
balls are sideways choices: every ball above the starter gives something and
costs something. The player owns any they've bought and freely swaps between
rounds from the Career Hub.

Each ball multiplies/offsets a few things the shot pipeline already uses:

    dist_mult      — scales Club.max_distance_yards
    acc_add        — added to base Club.accuracy (generic clubs)
    short_acc_add  — extra accuracy on Pitching/Sand wedge
    putt_acc_add   — extra accuracy on Putter
    shape_mult     — multiplies SHAPE_CURVE_FRACTION when DRAW/FADE is active

All effects are applied in states/golf_round.py::_effective_club, so shot.py
keeps reading modified Club stats without new plumbing — the one exception
is shape_mult, which is surfaced as an attribute on the returned Club so
shot.py can pick it up via getattr with a default of 1.0.
"""

from __future__ import annotations


BALL_ORDER = ["range", "tour", "distance", "spin", "soft", "pro_tour"]

BALL_TYPES: dict[str, dict] = {
    "range": {
        "label":         "Range Ball",
        "cost":          0,
        "min_tour":      1,
        "dist_mult":     0.95,
        "acc_add":       0.00,
        "short_acc_add": 0.00,
        "putt_acc_add":  0.00,
        "shape_mult":    0.85,
        "tagline":       "Budget practice ball. Short and unforgiving.",
    },
    "tour": {
        "label":         "Tour Ball",
        "cost":          1_500,
        "min_tour":      2,
        "dist_mult":     1.00,
        "acc_add":       0.02,
        "short_acc_add": 0.01,
        "putt_acc_add":  0.01,
        "shape_mult":    1.00,
        "tagline":       "Balanced all-rounder. Your default upgrade.",
    },
    "distance": {
        "label":         "Distance Ball",
        "cost":          5_000,
        "min_tour":      3,
        "dist_mult":     1.07,
        "acc_add":      -0.03,
        "short_acc_add":-0.02,
        "putt_acc_add":  0.00,
        "shape_mult":    0.80,
        "tagline":       "Long and hot off the tee. Less feel, less shape.",
    },
    "spin": {
        "label":         "Spin Ball",
        "cost":          8_000,
        "min_tour":      3,
        "dist_mult":     0.98,
        "acc_add":       0.01,
        "short_acc_add": 0.05,
        "putt_acc_add":  0.01,
        "shape_mult":    1.35,
        "tagline":       "Carves big shapes. Attacks pins with the wedges.",
    },
    "soft": {
        "label":         "Soft Feel",
        "cost":          6_000,
        "min_tour":      3,
        "dist_mult":     0.97,
        "acc_add":       0.01,
        "short_acc_add": 0.02,
        "putt_acc_add":  0.05,
        "shape_mult":    0.95,
        "tagline":       "Soft cover — putts roll true. Gives up a little length.",
    },
    "pro_tour": {
        "label":         "Pro Tour X",
        "cost":          25_000,
        "min_tour":      5,
        "dist_mult":     1.03,
        "acc_add":       0.04,
        "short_acc_add": 0.03,
        "putt_acc_add":  0.02,
        "shape_mult":    1.15,
        "tagline":       "Tour-proven. Better everywhere, priced to match.",
    },
}


def get_ball(ball_id: str) -> dict:
    """Return ball info or the range ball if the id is unknown."""
    return BALL_TYPES.get(ball_id, BALL_TYPES["range"])


def effect_summary(ball_id: str) -> str:
    """One-line numeric summary for UI: the deltas that matter most."""
    b = get_ball(ball_id)
    parts = []
    dm = b["dist_mult"]
    if dm != 1.0:
        parts.append(f"{'+' if dm >= 1 else ''}{int(round((dm - 1) * 100))}% dist")
    aa = b["acc_add"]
    if aa:
        parts.append(f"{'+' if aa >= 0 else ''}{aa:.2f} acc")
    sa = b["short_acc_add"]
    if sa:
        parts.append(f"{'+' if sa >= 0 else ''}{sa:.2f} wedge")
    pa = b["putt_acc_add"]
    if pa:
        parts.append(f"{'+' if pa >= 0 else ''}{pa:.2f} putt")
    sm = b["shape_mult"]
    if sm != 1.0:
        parts.append(f"{'+' if sm >= 1 else ''}{int(round((sm - 1) * 100))}% shape")
    return " · ".join(parts) if parts else "baseline"
