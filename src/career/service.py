"""
CareerService — thin coordinator for career-state transitions.

States used to call `game.player.apply_tournament_result(...)` and
`save_game(...)` directly, which made it hard to add logging, validation,
or alternative persistence paths without touching every call site. This
service centralises those transitions so there is one place to instrument.

It also owns the tournament-result processor so Player no longer has to
do deferred imports of `rankings` / `staff` / `majors` from inside its own
methods to dodge a circular import. Player.apply_tournament_result is a
thin wrapper over process_tournament_result().
"""

from __future__ import annotations

from src.career.rankings import get_ranking_points, compute_world_rank
from src.career.staff    import STAFF_TYPES


def process_tournament_result(player, tournament) -> dict:
    """Apply a completed tournament's result to `player` and return a
    summary dict {position, prize, points}.

    Extracted from Player.apply_tournament_result so the cross-cutting
    imports (rankings, staff) can live at module scope here instead of
    being deferred into a method on Player to avoid circular imports.
    """
    position   = tournament.get_player_position()
    prize      = tournament.get_prize_money(position)
    pts        = tournament.get_season_points(position)
    is_qschool = getattr(tournament, "is_qschool", False)

    player.earn_money(prize)
    player.total_earnings     += prize
    player.events_this_season += 1

    if not is_qschool:
        player.season_points += pts

        if position == 1:
            player.career_wins += 1
        if position <= 5:
            player.career_top5 += 1
        if position <= 10:
            player.career_top10 += 1

        if position == 1 and tournament.is_major:
            major_id = getattr(tournament, "major_id", None)
            if major_id and major_id not in player.majors_won:
                player.majors_won.append(major_id)

        lb = tournament.get_leaderboard()
        for pos, entry in enumerate(lb, start=1):
            if not entry["is_player"]:
                name = entry["name"]
                opp_pts = tournament.get_season_points(pos)
                player.opp_season_points[name] = (
                    player.opp_season_points.get(name, 0) + opp_pts)

    # World ranking points (Tour 4+). Q-school earns a small boost too.
    rp = get_ranking_points(player.tour_level, position, tournament.is_major)
    player.world_ranking_points += rp
    player.world_rank = compute_world_rank(player.world_ranking_points)

    # Sponsor target progress
    if player.active_sponsor and not is_qschool:
        t_type = player.active_sponsor["target"]["type"]
        inc = False
        if t_type == "win"    and position == 1:  inc = True
        if t_type == "top5"   and position <= 5:  inc = True
        if t_type == "top10"  and position <= 10: inc = True
        if t_type == "played":                    inc = True
        if inc:
            player.sponsor_progress[t_type] = (
                player.sponsor_progress.get(t_type, 0) + 1)

    # Deduct staff salaries
    for sid in player.hired_staff:
        salary = STAFF_TYPES.get(sid, {}).get("salary", 0)
        player.spend_money(salary)

    player._check_achievements()
    return {"position": position, "prize": prize, "points": pts}


class CareerService:
    """Per-game coordinator for career transitions (round end, season end)."""

    def __init__(self, game):
        self.game = game

    @property
    def player(self):
        return self.game.player

    # ── Round lifecycle ────────────────────────────────────────────────────────

    def record_round(self, course, scores: list[int]) -> dict | None:
        """Record a completed round against the active tournament (if any).

        - Appends `scores` to `current_tournament.player_rounds`.
        - If the tournament just completed, applies its result to the player.
        - Logs the round in the player's career log.
        - Autosaves. The tournament is dropped from the save when complete so
          the next load starts cleanly at the Career Hub.

        Returns the dict produced by `Player.apply_tournament_result` when
        the tournament just completed, or None otherwise.
        """
        tournament = self.game.current_tournament
        player     = self.player

        result: dict | None = None
        if tournament is not None:
            tournament.record_player_round(scores)
            if tournament.is_complete() and player is not None:
                result = player.apply_tournament_result(tournament)

        if player is not None:
            player.log_round(course.name, sum(scores), course.par)
            self._autosave()

        return result

    # ── Persistence ────────────────────────────────────────────────────────────

    def _autosave(self) -> None:
        """Save the player and any still-active tournament. Never raises.

        Skipped entirely for players in practice_mode — the course picker
        spawns a throwaway Player and we don't want to clobber real saves.
        """
        player     = self.player
        tournament = self.game.current_tournament
        if player is None or getattr(player, "practice_mode", False):
            return
        persist_tournament = (
            tournament if not (tournament and tournament.is_complete())
            else None)
        try:
            from src.utils.save_system import save_game
            save_game(player, persist_tournament)
        except Exception as e:
            print(f"Auto-save failed: {e}")
