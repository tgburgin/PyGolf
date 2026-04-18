"""
Opponent — simulated AI golfer for tournaments.

Score simulation uses a gaussian model per hole:
  mean_diff  = (12.0 - skill * 22.0) / 18   per hole
  std_per_hole = max(0.4, 0.9 - skill * 0.5)

Resulting expected round totals (vs par):
  skill 0.22 (weakest amateur) ≈ +7    std ≈ 3.4
  skill 0.38 (best amateur)    ≈ +3.5  std ≈ 3.0
  skill 0.74 (World Tour low)  ≈ -4.3  std ≈ 2.2
  skill 0.98 (Grand Tour best) ≈ -9.6  std ≈ 1.7
"""

import random


class Opponent:
    def __init__(self, name: str, nationality: str, skill: float):
        self.name        = name
        self.nationality = nationality
        self.skill       = skill   # 0.0–1.0

    def simulate_round(self, course_par: int, rng: "random.Random | None" = None) -> int:
        """Simulate one 18-hole round; returns total strokes.

        Pass a `random.Random` instance to make the result reproducible.
        Falls back to the global `random` module when no RNG is supplied.
        """
        r = rng if rng is not None else random
        mean_diff = 12.0 - self.skill * 22.0
        std       = max(1.5, 3.5 - self.skill * 2.0)
        diff      = int(round(r.gauss(mean_diff, std)))
        diff      = max(-12, min(30, diff))
        return course_par + diff

    def simulate_holes(self, hole_pars: list,
                       rng: "random.Random | None" = None) -> list:
        """Simulate hole-by-hole scores; returns list of stroke counts.

        Pass a `random.Random` instance to make the result reproducible.
        """
        r = rng if rng is not None else random
        scores = []
        mean_per_hole = (12.0 - self.skill * 22.0) / 18.0
        std_per_hole  = max(0.4, 0.9 - self.skill * 0.5)
        for par in hole_pars:
            diff = int(round(r.gauss(mean_per_hole, std_per_hole)))
            diff = max(-2, min(4, diff))
            scores.append(par + diff)
        return scores

    def to_dict(self) -> dict:
        return {"name": self.name, "nationality": self.nationality,
                "skill": self.skill}

    @classmethod
    def from_dict(cls, data: dict) -> "Opponent":
        return cls(data["name"], data["nationality"], data["skill"])
