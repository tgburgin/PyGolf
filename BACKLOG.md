# PyGolf — Outstanding Backlog

A prioritised list of issues, improvements and ideas from the architecture / UX / UI review. Items are grouped by priority so they can be picked off in any order, and each entry names the file(s), the problem, and a minimum-viable fix.

**Status:** most items from the original review have shipped. The remaining entries sit under **Deferred** and **Ideas** below.

---

## Shipped

**First pass (commit `0c87b33`):**
- Aim-click radius raised to 50 px; faint click-zone ring around the ball while idle.
- Shot-shape curve fraction raised to 0.15.
- Toasts for trees / deep rough / bunker landings.
- Save-format version check; corrupt saves labelled and disabled in the UI.
- Deterministic `Tournament(rng_seed=…)` seeded per `(player, season, tour, event)`.
- First-round tutorial modal gated by `Player.tutorial_seen`.

**Second pass (a series of focused commits):**
- **Mid-round save/resume** via ESC pause overlay. Tournament now persists `course_name`; the save file carries a `round_state` payload; `main_menu._resume_round` rebuilds the course and drops straight back into `GolfRoundState`.
- **Two Q-School attempts per qualified season.** `Player.qschool_attempts_remaining` tracks attempts; failure re-sets `qschool_pending` while attempts remain; Q-School seeds differ per attempt.
- **Promotion requirements surfaced on the Career Hub.** Tour 4 shows "Finish top 5 to earn Q-School" (or attempts-ready); Tour 5 shows both the top-10 requirement and the top-50 world rank with live current rank; tints green when satisfied.
- **Curved aim preview.** `_draw_aim_arrow` draws a 16-segment quadratic bezier matching the in-flight shape when Draw/Fade is selected with a shapeable club.
- **Out-of-bounds toast.** Tree strikes within two tiles of the grid edge show "Out of bounds — dropped back" instead of the generic "In the trees".
- **Course-building helper extracted** to `src/data/_hole_factory.build_hole`; `courses_data` and `courses_library` call through it.
- **`courses_library.get_courses_for_tour_id` renamed** to `python_courses_for_tour`, with a docstring pointing at `tours_data.get_courses_for_tour` as the single gameplay entry point.
- **`validate_course()`** runs on load: logic layer presence, grid dimensions, tee/pin bounds, at-least-one-tee/green. Invalid courses raise `CourseValidationError` (caught by `tours_data._load_json_courses` so a single bad file just drops out of the pool).
- **`SOURCE_TILE` centralised** in `src/constants.py`; game loader, renderer, editor canvas and tileset panel all import it.
- **`SCREEN_W` / `SCREEN_H` / `FPS` centralised** in `src/constants.py`; `main.py` and every state file now import rather than redeclare.
- **`CareerService`** in `src/career/service.py` owns round-end transitions and autosave; `RoundSummaryState` delegates via `record_round(course, scores)`.
- **Deferred imports lifted in `Player`.** `apply_tournament_result` now delegates to `service.process_tournament_result` (which imports `rankings` / `staff` at module scope); the remaining `staff`/`sponsorship`/`majors` deferred imports are hoisted to the top of `player.py`.
- **Putter/Sand Wedge auto-select toast** (suppressed when another terrain toast is still on screen).
- **Career Hub tab recommendation:** thin gold accent under Equipment / Staff / Sponsors when they currently offer the highest-value action.
- **Locked club tiers** now name the unlocking tour, e.g. "Unlocks on Continental Tour (Tour 4)".
- **Losing-streak nudge:** after three rounds at +3 or worse, the Career Hub flashes a hint naming the weakest non-maxed stat.
- **`AudioSettingsPanel`** extracted to `src/ui/audio_settings.py`; `main_menu` and the `GolfRoundState` pause overlay both use it so audio settings are reachable mid-round.
- **Colour-blind hatch** on Rough (step 4) and Deep Rough (step 2) in `renderer.py`.
- **Shape-button glyphs** (curved arrows / up-arrow) drawn next to Draw/Straight/Fade labels in the HUD.
- **Disabled-button palette** shifted to a warm desaturated taupe in main_menu, career_hub, character_creation so it's obviously distinct from the active-green UI.
- **"Last place" marker** on the tour standings table when the player row is dead last.
- **Scorecard header** bumped from 13 pt to 15 pt.

---

## Deferred (not shipped — reason noted)

- **Shared button helper with click-press feedback** — every state has bespoke button-drawing code. Extracting a cross-state helper is a structural refactor with high regression risk relative to the payoff (a 100 ms press animation). Left for a future focused pass.
- **Pixel font bundled with the game** — needs a licensing decision and a binary asset choice that belongs to the project owner; the code change itself is trivial once a font is picked (wire it through `pygame.font.Font(path, size)` in a new `src/ui/fonts.py`).
- **Per-frame overlay surface caching** — overlays only render when visible (not every frame), so the measurable CPU win is tiny while the code churn touches 5+ files. Revisit if a profiler points here.
- **Resolution scaling pass (1280×720 → scalable)** — explicitly a future project; the constants are now centralised, which is the prerequisite.
- **Keyboard-only play** — a full alternate-input mode (arrow-keys aim, space-hold power, space-release fire). Out of scope as a small fix; worth filing as a proper accessibility feature.

## Ideas / bigger bets

- **Practice / driving-range mode** — one hole, no score, free club switching. Would reuse `GolfRoundState` with a `practice=True` flag. Best place to teach shot shape without tour pressure.
- **Daily Course seed** — date-derived, shared across all players. Course generation is already data-driven, so cheap to add.
- **Caddie suggestions** — "Caddie recommends 7 Iron, slight fade" tip whose accuracy scales with the Caddie staff tier. Makes the existing staff upgrade feel meaningful.
- **Replay of the final hole of a tournament win** — save ball positions for the last hole, auto-pan the camera. Cheap drama.

---

## Review methodology

The full original review (with reasoning) lives at `C:\Users\tdp\.claude-tdp\plans\this-project-belongs-to-lexical-marshmallow.md`.
