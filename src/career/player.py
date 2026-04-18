"""
Player — the human golfer's profile, stats, inventory, and career history.
"""

from src.golf.club         import STARTER_BAG, get_club_bag, CLUB_SETS, CLUB_SET_ORDER
from src.career.staff       import STAFF_TYPES
from src.career.sponsorship import is_target_met
from src.career.majors      import MAJOR_ORDER

NATIONALITIES = [
    "American", "English", "Scottish", "Irish", "Welsh",
    "Australian", "South African", "Spanish", "German", "Swedish",
    "Canadian", "Japanese", "South Korean", "Argentine", "French",
    "Italian", "Danish", "Norwegian", "New Zealander", "Zimbabwean",
]

STAT_KEYS = ["power", "accuracy", "short_game", "putting", "mental", "fitness"]
BASE_STAT  = 50
MAX_STAT   = 80

STARTING_MONEY = 500

# ── Achievements registry ─────────────────────────────────────────────────────
ACHIEVEMENTS = {
    "first_round":   {"label": "First Step",     "desc": "Play your first round"},
    "first_subpar":  {"label": "Under Par",       "desc": "Finish a round under par"},
    "first_top5":    {"label": "Top 5",           "desc": "Finish in the top 5"},
    "first_win":     {"label": "Winner!",         "desc": "Win your first tournament"},
    "challenger":    {"label": "Going Up",        "desc": "Reach the Challenger Tour"},
    "going_pro":     {"label": "Turning Pro",     "desc": "Reach the Continental Tour"},
    "grand_tour":    {"label": "Grand Stage",     "desc": "Reach the Grand Tour"},
    "max_stat":      {"label": "Dedicated",       "desc": "Max out a stat to 80"},
    "pro_clubs":     {"label": "Gear Up",         "desc": "Buy the Pro Set or better"},
    "hired_staff":   {"label": "Team Player",     "desc": "Hire your first staff member"},
    "millionaire":   {"label": "Millionaire",     "desc": "Earn $1,000,000 in career prize money"},
    "veteran":       {"label": "Veteran",         "desc": "Play 50 events"},
    "hat_trick":     {"label": "Hat Trick",       "desc": "Win 3 tournaments"},
    "first_major":   {"label": "Major Winner",    "desc": "Win your first Major championship"},
    "grand_slam":    {"label": "Grand Slam",      "desc": "Win all 4 Majors"},
    "world_no1":     {"label": "World No. 1",     "desc": "Reach World Ranking #1"},
}


class Player:
    """Everything that persists about the human player across the career."""

    def __init__(self, name: str, nationality: str):
        self.name        = name
        self.nationality = nationality
        self.money       = STARTING_MONEY
        self.tour_level  = 1
        self.season      = 1
        self.events_played = 0
        self.career_log: list[dict] = []

        self.stats = {k: BASE_STAT for k in STAT_KEYS}

        self.club_set_name = "starter"

        # Season tracking
        self.season_points:       int  = 0
        self.events_this_season:  int  = 0
        self.opp_season_points:   dict = {}

        # Career stats
        self.career_wins:    int       = 0
        self.career_top5:    int       = 0
        self.career_top10:   int       = 0
        self.total_earnings: int       = 0
        self.best_round:     int | None = None  # best score vs par (most negative)

        # Staff & sponsorship
        self.hired_staff:     list[str]   = []
        self.active_sponsor:  dict | None = None
        self.sponsor_progress: dict       = {}

        # Achievements
        self.achievements: list[str] = []

        # World rankings & majors
        self.world_ranking_points: float      = 0.0
        self.world_rank:           int        = 201   # starts unranked
        self.majors_won:           list[str]  = []

        # Q-School qualifying flag (set when Tour 4 season ends top-5) and
        # the number of Q-School attempts remaining before the player must
        # re-qualify with another top-5 season finish.
        self.qschool_pending: bool           = False
        self.qschool_attempts_remaining: int = 0

        # One-time tutorial shown on the player's first round.
        self.tutorial_seen: bool = False

    @property
    def clubs(self):
        return get_club_bag(self.club_set_name)

    # ── Stat bonuses from character creation ──────────────────────────────────

    def set_bonus_stats(self, bonus: dict[str, int]) -> None:
        for k, v in bonus.items():
            if k in self.stats:
                self.stats[k] = min(MAX_STAT, BASE_STAT + v)

    # ── Training ──────────────────────────────────────────────────────────────

    def training_cost(self, stat_key: str) -> int | None:
        """Cost to raise stat_key by 1, or None if already at MAX_STAT."""
        current = self.stats.get(stat_key, BASE_STAT)
        if current >= MAX_STAT:
            return None
        above_base = current - BASE_STAT   # 0..29
        return (above_base + 1) * 200       # $200 → $6 000

    def train_stat(self, stat_key: str) -> bool:
        """Spend money to increase a stat by 1. Returns True on success."""
        cost = self.training_cost(stat_key)
        if cost is None:
            return False
        if self.spend_money(cost):
            self.stats[stat_key] = min(MAX_STAT, self.stats[stat_key] + 1)
            self._check_achievements()
            return True
        return False

    # ── Equipment ─────────────────────────────────────────────────────────────

    def upgrade_club_set(self, set_name: str) -> bool:
        """
        Buy a club set.  Returns True on success.
        Fails if: tour level too low, already own equal/better, or can't afford.
        """
        if set_name not in CLUB_SETS:
            return False
        info = CLUB_SETS[set_name]
        if info["min_tour"] > self.tour_level:
            return False
        current_idx = CLUB_SET_ORDER.index(self.club_set_name)
        target_idx  = CLUB_SET_ORDER.index(set_name)
        if target_idx <= current_idx:
            return False
        if self.spend_money(info["cost"]):
            self.club_set_name = set_name
            self._check_achievements()
            return True
        return False

    # ── Staff ─────────────────────────────────────────────────────────────────

    def staff_stat_bonus(self, stat_key: str) -> int:
        """Sum of stat bonuses from all hired staff members."""
        total = 0
        for sid in self.hired_staff:
            total += STAFF_TYPES.get(sid, {}).get("bonuses", {}).get(stat_key, 0)
        return total

    def hire_staff(self, staff_id: str) -> bool:
        """Pay hire cost and add staff member. Returns True on success."""
        if staff_id in self.hired_staff:
            return False
        info = STAFF_TYPES.get(staff_id)
        if not info:
            return False
        if info["min_tour"] > self.tour_level:
            return False
        if not self.spend_money(info["hire_cost"]):
            return False
        self.hired_staff.append(staff_id)
        self._check_achievements()
        return True

    def fire_staff(self, staff_id: str) -> bool:
        if staff_id in self.hired_staff:
            self.hired_staff.remove(staff_id)
            return True
        return False

    # ── Sponsorship ───────────────────────────────────────────────────────────

    def accept_sponsor(self, sponsor: dict) -> bool:
        """Accept a sponsor deal.  Signing fee paid immediately."""
        if self.active_sponsor is not None:
            return False
        self.active_sponsor   = dict(sponsor)
        self.sponsor_progress = {sponsor["target"]["type"]: 0}
        self.earn_money(sponsor["signing_fee"])
        return True

    def drop_sponsor(self) -> None:
        self.active_sponsor   = None
        self.sponsor_progress = {}

    def _pay_out_sponsor(self) -> None:
        """Called at season reset — pay bonus if target met."""
        if self.active_sponsor is None:
            return
        if is_target_met(self.active_sponsor, self.sponsor_progress):
            bonus = self.active_sponsor["season_bonus"]
            self.earn_money(bonus)
            self.total_earnings += bonus
        self.active_sponsor   = None
        self.sponsor_progress = {}

    # ── Career tracking ───────────────────────────────────────────────────────

    def log_round(self, course_name: str, strokes: int, par: int) -> None:
        diff = strokes - par
        self.career_log.append({
            "course":  course_name,
            "strokes": strokes,
            "par":     par,
            "diff":    diff,
        })
        self.events_played += 1
        if self.best_round is None or diff < self.best_round:
            self.best_round = diff
        self._check_achievements()

    def apply_tournament_result(self, tournament) -> dict:
        # Logic lives in CareerService so the rankings/staff imports it
        # needs can be at module scope without introducing a circular import.
        from src.career.service import process_tournament_result
        return process_tournament_result(self, tournament)

    def reset_season(self) -> None:
        self._pay_out_sponsor()
        self.season            += 1
        self.season_points      = 0
        self.events_this_season = 0
        self.opp_season_points  = {}

    def earn_money(self, amount: int) -> None:
        self.money += amount

    def spend_money(self, amount: int) -> bool:
        if self.money >= amount:
            self.money -= amount
            return True
        return False

    # ── Achievements ──────────────────────────────────────────────────────────

    def has_won_game(self) -> bool:
        """Win condition: all 4 Majors won AND World No. 1."""
        all_majors = all(m in self.majors_won for m in MAJOR_ORDER)
        return all_majors and self.world_rank == 1

    def _check_achievements(self) -> None:
        """Unlock any achievements whose conditions are now met."""
        def unlock(key):
            if key not in self.achievements:
                self.achievements.append(key)

        if self.events_played >= 1:
            unlock("first_round")
        if self.best_round is not None and self.best_round < 0:
            unlock("first_subpar")
        if self.career_top5 >= 1:
            unlock("first_top5")
        if self.career_wins >= 1:
            unlock("first_win")
        if self.career_wins >= 3:
            unlock("hat_trick")
        if self.tour_level >= 2:
            unlock("challenger")
        if self.tour_level >= 4:
            unlock("going_pro")
        if self.tour_level >= 6:
            unlock("grand_tour")
        if any(v >= MAX_STAT for v in self.stats.values()):
            unlock("max_stat")
        club_tier = CLUB_SET_ORDER.index(self.club_set_name)
        if club_tier >= CLUB_SET_ORDER.index("pro"):
            unlock("pro_clubs")
        if len(self.hired_staff) >= 1:
            unlock("hired_staff")
        if self.total_earnings >= 1_000_000:
            unlock("millionaire")
        if self.events_played >= 50:
            unlock("veteran")
        if len(self.majors_won) >= 1:
            unlock("first_major")
        if len(self.majors_won) >= 4:
            unlock("grand_slam")
        if self.world_rank == 1:
            unlock("world_no1")

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version":            2,
            "name":               self.name,
            "nationality":        self.nationality,
            "money":              self.money,
            "tour_level":         self.tour_level,
            "season":             self.season,
            "events_played":      self.events_played,
            "stats":              dict(self.stats),
            "club_set_name":      self.club_set_name,
            "career_log":         list(self.career_log),
            "season_points":      self.season_points,
            "events_this_season": self.events_this_season,
            "opp_season_points":  dict(self.opp_season_points),
            # Phase 7 additions
            "career_wins":        self.career_wins,
            "career_top5":        self.career_top5,
            "career_top10":       self.career_top10,
            "total_earnings":     self.total_earnings,
            "best_round":         self.best_round,
            "hired_staff":        list(self.hired_staff),
            "active_sponsor":     self.active_sponsor,
            "sponsor_progress":   dict(self.sponsor_progress),
            "achievements":         list(self.achievements),
            # Phase 8 additions
            "world_ranking_points": self.world_ranking_points,
            "world_rank":           self.world_rank,
            "majors_won":           list(self.majors_won),
            "qschool_pending":              self.qschool_pending,
            "qschool_attempts_remaining":   self.qschool_attempts_remaining,
            "tutorial_seen":                self.tutorial_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        p = cls(data["name"], data.get("nationality", "American"))
        p.money               = data.get("money", STARTING_MONEY)
        p.tour_level          = data.get("tour_level", 1)
        p.season              = data.get("season", 1)
        p.events_played       = data.get("events_played", 0)
        p.stats               = {k: data.get("stats", {}).get(k, BASE_STAT)
                                 for k in STAT_KEYS}
        p.club_set_name       = data.get("club_set_name", "starter")
        p.career_log          = data.get("career_log", [])
        p.season_points       = data.get("season_points", 0)
        p.events_this_season  = data.get("events_this_season", 0)
        p.opp_season_points   = data.get("opp_season_points", {})
        # Phase 7 additions (graceful defaults for old saves)
        p.career_wins         = data.get("career_wins", 0)
        p.career_top5         = data.get("career_top5", 0)
        p.career_top10        = data.get("career_top10", 0)
        p.total_earnings      = data.get("total_earnings", 0)
        p.best_round          = data.get("best_round", None)
        p.hired_staff         = data.get("hired_staff", [])
        p.active_sponsor      = data.get("active_sponsor", None)
        p.sponsor_progress    = data.get("sponsor_progress", {})
        p.achievements          = data.get("achievements", [])
        p.world_ranking_points  = data.get("world_ranking_points", 0.0)
        p.world_rank            = data.get("world_rank", 201)
        p.majors_won            = data.get("majors_won", [])
        p.qschool_pending              = data.get("qschool_pending", False)
        p.qschool_attempts_remaining   = data.get("qschool_attempts_remaining", 0)
        p.tutorial_seen                = data.get("tutorial_seen", False)
        return p
