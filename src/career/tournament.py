"""
Tournament — one event in a tour season.

Standard event : 1 round (18 holes).  Complete after the player finishes
                 their round.

Major event    : 2 rounds (Grand Tour only).  Complete after the player
                 finishes both rounds.

Opponents' hole-by-hole scores are pre-simulated at tournament creation so
the outcome is fixed — the player just needs to beat those scores.

Live leaderboard
----------------
get_live_leaderboard(holes_done, current_hole_scores) compares the player's
score through the first N holes against every opponent's score through the
same N holes.  This gives a fair running comparison after every hole.
"""

# Prize fund (total $) per tour level
PRIZE_FUNDS = {
    1: 0,
    2: 10_000,
    3: 25_000,
    4: 75_000,
    5: 200_000,
    6: 1_000_000,
}

# Majors use their own prize fund (set in majors.py; this is a fallback)
MAJOR_PRIZE_FUND = 4_500_000

# Events per season per tour level
EVENTS_PER_SEASON = {1: 8, 2: 10, 3: 12, 4: 14, 5: 16, 6: 18}

# Top-N finish required for promotion at end of season
PROMOTION_THRESHOLD = {1: 3, 2: 5, 3: 3, 4: 5, 5: 10, 6: None}

# Prize % per finishing position (index 0 = 1st)
_PRIZE_PCTS = [
    18, 11,  7,  5,  4,
     3,  3,  3,  3,  3,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
]

# Season-standing points per finishing position
_SEASON_PTS = [
    100, 60, 40, 30, 25,
     15, 15, 15, 15, 15,
      8,  8,  8,  8,  8,  8,  8,  8,  8,  8,
      3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
]

TOUR_DISPLAY_NAMES = {
    1: "Amateur Circuit",
    2: "Challenger Tour",
    3: "Development Tour",
    4: "Continental Tour",
    5: "World Tour",
    6: "The Grand Tour",
}


class Tournament:
    """A single tour event — 1 round for standard events, 2 for Majors."""

    def __init__(self, name: str, tour_level: int, hole_pars: list,
                 opponents: list, is_major: bool = False,
                 event_number: int = 1, total_events: int = 8,
                 major_id: str | None = None,
                 major_prize_fund: int | None = None,
                 is_qschool: bool = False,
                 rng_seed: int | None = None):
        import random as _random
        self.name         = name
        self.tour_level   = tour_level
        self.hole_pars    = list(hole_pars)
        self.course_par   = sum(hole_pars)
        self.opponents    = opponents
        self.is_major     = is_major
        self.major_id     = major_id
        self.is_qschool   = is_qschool
        self.total_rounds = 2 if is_major else 1
        self.event_number = event_number
        self.total_events = total_events
        if is_major:
            self.prize_fund = major_prize_fund or MAJOR_PRIZE_FUND
        elif is_qschool:
            self.prize_fund = 20_000   # modest qualifier prize fund
        else:
            self.prize_fund = PRIZE_FUNDS.get(tour_level, 0)

        # Deterministic seed for opponent simulation. If the caller doesn't
        # supply one, derive a stable value from event metadata so repeated
        # construction with the same args reproduces the same field.
        if rng_seed is None:
            rng_seed = hash((name, tour_level, event_number,
                             bool(is_major), bool(is_qschool))) & 0xFFFFFFFF
        self.rng_seed = int(rng_seed)
        rng = _random.Random(self.rng_seed)

        # player_rounds[i] = list of 18 hole scores for round i
        self.player_rounds: list[list[int]] = []

        # _opp_holes[name][round_idx][hole_idx] = strokes
        self._opp_holes: dict[str, list[list[int]]] = {}
        for opp in self.opponents:
            self._opp_holes[opp.name] = [
                opp.simulate_holes(self.hole_pars, rng=rng)
                for _ in range(self.total_rounds)
            ]

    # ── Round tracking ────────────────────────────────────────────────────────

    @property
    def current_round_index(self) -> int:
        """0-based index of the round currently being played."""
        return len(self.player_rounds)

    @property
    def current_round_number(self) -> int:
        return self.current_round_index + 1

    def record_player_round(self, hole_scores: list) -> None:
        """Record the player's completed round (list of 18 hole scores)."""
        self.player_rounds.append(list(hole_scores))

    def is_complete(self) -> bool:
        return len(self.player_rounds) >= self.total_rounds

    # ── Live leaderboard (during a round) ────────────────────────────────────

    def get_live_leaderboard(self, holes_done: int,
                             current_hole_scores: list) -> list[dict]:
        """
        Running leaderboard after `holes_done` holes of the current round.
        Everyone is compared through the same number of holes for a fair
        side-by-side ranking.

        Returns list of dicts sorted by vs_par (best first):
          name, is_player, vs_par, thru, nationality
        """
        rnd = min(self.current_round_index, self.total_rounds - 1)

        # Cumulative par and strokes from fully completed rounds
        completed_par     = rnd * self.course_par
        partial_hole_par  = sum(self.hole_pars[:holes_done])

        # Player
        prev_strokes = sum(sum(r) for r in self.player_rounds)
        curr_strokes = sum(current_hole_scores)
        player_vs_par = (prev_strokes + curr_strokes) - (completed_par + partial_hole_par)

        entries = [{
            "name":        "You",
            "is_player":   True,
            "vs_par":      player_vs_par,
            "thru":        holes_done,
            "nationality": "",
        }]

        for opp in self.opponents:
            opp_prev = sum(sum(self._opp_holes[opp.name][r]) for r in range(rnd))
            opp_curr = sum(self._opp_holes[opp.name][rnd][:holes_done])
            opp_vs_par = (opp_prev + opp_curr) - (completed_par + partial_hole_par)
            entries.append({
                "name":        opp.name,
                "is_player":   False,
                "vs_par":      opp_vs_par,
                "thru":        holes_done,
                "nationality": opp.nationality,
            })

        return sorted(entries, key=lambda e: (e["vs_par"], e["name"]))

    # ── Final leaderboard (after all rounds) ─────────────────────────────────

    def get_leaderboard(self) -> list[dict]:
        """
        Final leaderboard based on all completed rounds.
        Each entry: name, is_player, rounds (list of totals), total, vs_par, nationality
        """
        rnd_count = len(self.player_rounds)
        if rnd_count == 0:
            return []

        entries = [{
            "name":        "You",
            "is_player":   True,
            "rounds":      [sum(r) for r in self.player_rounds],
            "total":       sum(sum(r) for r in self.player_rounds),
            "vs_par":      sum(sum(r) for r in self.player_rounds) - rnd_count * self.course_par,
            "nationality": "",
        }]

        for opp in self.opponents:
            rounds = [sum(self._opp_holes[opp.name][r]) for r in range(rnd_count)]
            total  = sum(rounds)
            entries.append({
                "name":        opp.name,
                "is_player":   False,
                "rounds":      rounds,
                "total":       total,
                "vs_par":      total - rnd_count * self.course_par,
                "nationality": opp.nationality,
            })

        return sorted(entries, key=lambda e: (e["total"], e["name"]))

    def get_player_position(self) -> int:
        for i, e in enumerate(self.get_leaderboard()):
            if e["is_player"]:
                return i + 1
        return len(self.opponents) + 1

    # ── Prize / points ────────────────────────────────────────────────────────

    def get_prize_money(self, position: int) -> int:
        if self.prize_fund == 0:
            return 0
        idx = min(position - 1, len(_PRIZE_PCTS) - 1)
        return int(self.prize_fund * _PRIZE_PCTS[idx] / 100)

    def get_season_points(self, position: int) -> int:
        idx = min(position - 1, len(_SEASON_PTS) - 1)
        return _SEASON_PTS[idx]

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "tour_level":    self.tour_level,
            "hole_pars":     self.hole_pars,
            "is_major":      self.is_major,
            "major_id":      self.major_id,
            "is_qschool":    self.is_qschool,
            "total_rounds":  self.total_rounds,
            "event_number":  self.event_number,
            "total_events":  self.total_events,
            "prize_fund":    self.prize_fund,
            "rng_seed":      self.rng_seed,
            "player_rounds": [list(r) for r in self.player_rounds],
            "opp_holes":     {k: [list(r) for r in v]
                              for k, v in self._opp_holes.items()},
            "opponents":     [o.to_dict() for o in self.opponents],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tournament":
        from src.career.opponent import Opponent
        opponents = [Opponent.from_dict(o) for o in data["opponents"]]

        t = cls.__new__(cls)
        t.name         = data["name"]
        t.tour_level   = data["tour_level"]
        t.hole_pars    = list(data.get("hole_pars", [4] * 18))
        t.course_par   = sum(t.hole_pars)
        t.opponents    = opponents
        t.is_major     = data.get("is_major", False)
        t.major_id     = data.get("major_id", None)
        t.is_qschool   = data.get("is_qschool", False)
        t.total_rounds = data.get("total_rounds", 1)
        t.event_number = data.get("event_number", 1)
        t.total_events = data.get("total_events", 8)
        t.prize_fund   = data.get("prize_fund", 0)
        t.rng_seed     = int(data.get("rng_seed", 0))
        t.player_rounds = [list(r) for r in data.get("player_rounds", [])]
        t._opp_holes    = {k: [list(r) for r in v]
                           for k, v in data.get("opp_holes", {}).items()}
        return t
