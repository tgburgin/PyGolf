# Game Balance Plan

## Problem Statement

A test round was completed at 22 under par on the Amateur Circuit. Real scratch amateurs
shoot around even par; a beginner amateur shoots 90–100 (18–28 over par). 22 under par on
a par-72 course means the player scored roughly 50 strokes on 18 holes — an average of 2.8
strokes on a par-4. This is elite professional territory before any career progression.

---

## Root Cause Analysis

### 1. Hole capture radius is enormous (most critical bug)
**Current:** `HOLE_CAPTURE_RADIUS = 14` px  
`tile_size = 32` px, scale = 10 yards per tile → 1 px ≈ 0.31 yards  
14 px ≈ **4.4 yards** capture radius around the hole.

A real golf hole is 4.25 inches in diameter (≈ 0.35 feet). A generous game capture zone
should be about 1 yard (3 px). At 4.4 yards, any approach shot that lands on the green
near the flag simply auto-sinks. The player never has to putt. This alone likely accounts
for most of the under-par scoring.

**Target:** 3 px (≈ 1 yard). Enough that a perfectly placed approach can still one-putt,
but not automatic.

---

### 2. Scatter is lateral-only and too tight
**Current formula:**
```
scatter_range = (1.0 - effective_accuracy) * shot_dist_px * 0.18
scatter = random.uniform(-scatter_range, scatter_range)  # lateral only
```

**Driver example (fairway):**
- effective_accuracy = 0.68 × 1.0 = 0.68
- scatter_range = 0.32 × 800 px × 0.18 = **46 px ≈ 14 yards** (±14 yards)
- Average absolute miss: only 7 yards (uniform distribution centres near zero)
- No distance scatter — you always land at exactly the right distance

Real amateur driver scatter: ±30–50 yards lateral, and ±15–20% in distance.

**Problems:**
- Multiplier of 0.18 is too small — should be 0.35–0.45 for amateur clubs
- No distance scatter — ball always lands at the correct yardage
- Uniform distribution — in real life errors cluster toward zero (bell curve). A uniform
  random gives too many wild misses and not enough small ones

---

### 3. Putter is nearly perfect at any distance
**Current:**
```
Putter: max_distance_yards=55, accuracy=0.96
scatter_range = (1 - 0.96) * 176 px * 0.18 = 1.3 px ≈ 0.4 yards
```
A 40-yard putt has the same 0.4-yard scatter as a 5-yard putt. The putter is effectively
a precision laser. Combined with the huge capture radius, the player virtually never
three-putts.

Real putting: a scratch golfer two-putts from 20 feet about 85% of the time. From 40 feet,
one-putts are rare and three-putts are common.

---

### 4. Club accuracy values too high for amateur tier
**Current starter bag accuracy ratings:**
| Club             | Accuracy |
|------------------|----------|
| Driver           | 0.68     |
| 3-Wood           | 0.72     |
| 5-Iron           | 0.78     |
| 7-Iron           | 0.82     |
| 9-Iron           | 0.86     |
| Pitching Wedge   | 0.90     |
| Sand Wedge       | 0.86     |
| Putter           | 0.96     |

These feel more like mid-handicap recreational values. A true beginner/amateur should be
materially less accurate. These values should be the target for a skilled amateur AFTER
stat investment. At tour level 1 (Amateur Circuit) they should start lower.

---

### 5. No distance control penalty
The current system only scatters shots laterally. In real golf, distance control is
equally important. Missing the green by 10 yards long is just as problematic as missing
10 yards right. Without it, the player can always guarantee landing on the green if they
aim well.

---

### 6. Wind impact too subtle
**Current:** `wind_scale = tile_sz * 0.4 = 12.8 px per strength unit`  
Max wind (strength 5): 64 px ≈ 20 yards of drift on a full shot.  
This is reasonable in isolation, but because scatter is so tight, the player can just
aim 20 yards into the wind and hit a near-perfect shot every time.

Wind only becomes a genuine difficulty factor once scatter is also realistic. When both
scatter AND wind are unpredictable, their combination makes long approach shots genuinely
uncertain.

---

### 7. Terrain penalties insufficient for rough and bunkers
**Current:**
| Terrain   | dist_mod | acc_mod |
|-----------|----------|---------|
| Rough     | 0.75     | 0.80    |
| Deep Rough| 0.55     | 0.60    |
| Bunker    | 0.60     | 0.70    |

At 0.80 accuracy mod, shots from the rough are only marginally worse than the fairway.
Since scatter is already low, an 80% multiplier barely changes the outcome.
Bunker shots should feel genuinely difficult — a 0.70 acc_mod on an already-accurate
club barely pushes the ball offline.

---

### 8. Player stats don't affect gameplay yet
All six stats (Power, Accuracy, Short Game, Putting, Mental, Fitness) are stored but
never applied. A base stat of 50 gives the same performance as 80. The stat system was
intentionally deferred to a later phase, but it means character creation has no
mechanical meaning yet — and there's no feedback loop to encourage improvement.

---

## Rebalance Plan

### Phase B1 — Critical fixes (implement immediately)

These changes address the most game-breaking issues. They can be made in isolation with
no new systems required.

#### B1-1: Reduce hole capture radius
**File:** `src/golf/ball.py`
```
HOLE_CAPTURE_RADIUS: 14 → 7   (implemented)
HOLE_ROLL_RADIUS:    12        (unchanged)
```
Reduced from 14 to 7 px (~2.2 yards). This is the implemented value — it strikes a balance
between requiring accurate putting and still allowing clean hole capture on well-struck putts.
The original target of 3 px was found to be too punishing in play.

---

#### B1-2: Increase scatter multiplier and add distance scatter
**File:** `src/golf/shot.py`

Replace the current lateral-only scatter with a two-component system:

```python
# Lateral scatter (perpendicular to shot direction) — misses left/right
SCATTER_LATERAL = 0.40     # was 0.18

# Distance scatter (along shot direction) — over/undershoot
SCATTER_DISTANCE = 0.12    # new — fraction of total shot distance
```

**Lateral scatter:** unchanged formula structure, just bigger multiplier.  
**Distance scatter:** add `random.gauss(0, scatter_range * SCATTER_DISTANCE)` along the
shot direction. This means a 200-yard driver shot might land 185–215 yards instead of
exactly 200.

Use `random.gauss(0, scatter_range / 2.5)` clamped to ±scatter_range instead of
`random.uniform` — bell-curve distribution means most shots miss by a small amount and
truly wild shots are rarer.

---

#### B1-3: Putter distance accuracy by distance
**File:** `src/golf/shot.py`

Putting scatter should scale significantly with putt length. Propose a distance-based
accuracy degradation for the putter:

```
effective_putter_accuracy = max(0.50, club.accuracy - (shot_dist_yards / 100) * 0.40)
```

Examples:
- 5-yard putt: accuracy = 0.96 − (5/100 × 0.40) = 0.94  (nearly perfect)
- 15-yard putt: accuracy = 0.96 − 0.06 = 0.90 (manageable)
- 30-yard putt: accuracy = 0.96 − 0.12 = 0.84 (tricky)
- 50-yard putt: accuracy = 0.84 (max penalty floor)

This is only applied when club.name == "Putter". Combined with B1-1 (smaller capture
radius), long putts will require accurate play.

---

#### B1-4: Reduce amateur club accuracy values
**File:** `src/golf/club.py`

Introduce a clear distinction between the starter bag (amateur) and future upgraded bags
(pro tour). Lower all accuracy values by ~0.08–0.12:

| Club            | Current | Amateur Target |
|-----------------|---------|----------------|
| Driver          | 0.68    | 0.56           |
| 3-Wood          | 0.72    | 0.60           |
| 5-Iron          | 0.78    | 0.66           |
| 7-Iron          | 0.82    | 0.70           |
| 9-Iron          | 0.86    | 0.74           |
| Pitching Wedge  | 0.90    | 0.80           |
| Sand Wedge      | 0.86    | 0.74           |
| Putter          | 0.96    | 0.92           |

These amateur values represent the floor. Upgraded clubs (purchased in later phases) will
restore accuracy toward the current values and beyond for pro-level play.

---

#### B1-5: Harden terrain accuracy penalties
**File:** `src/golf/terrain.py`

| Terrain   | Original acc_mod | Implemented acc_mod |
|-----------|------------------|---------------------|
| Rough     | 0.80             | 0.70                |
| Deep Rough| 0.60             | 0.50                |
| Bunker    | 0.70             | 0.78                |

Rough and Deep Rough penalties were tightened as planned. Bunker was left at 0.78 (slightly
loosened from the original 0.70) — bunker play in the game requires a precision flop shot and
the 0.78 value gives a meaningful but recoverable penalty without making sand shots feel
impossible, especially at amateur level. The planned 0.55 was found to be too severe.

---

### Phase B2 — Stat integration (implement when Phase 7 training is built)

Once the training shop exists and players can raise stats, stats should directly modify
the shot mechanics.

#### B2-1: Power stat → distance multiplier
```python
# In golf_round.py, _on_left_release()
power_mod = 0.70 + (player.stats['power'] / 100) * 0.60
# stat=50 → ×1.00,  stat=65 → ×1.09,  stat=80 → ×1.18
```
Applies to `aim_x/aim_y` scaling (shot distance), not to the aim point calculation in
`shot.py`. This keeps separation of concerns: shot.py handles input, golf_round.py applies
player modifiers.

#### B2-2: Accuracy stat → scatter multiplier
```python
acc_player_mod = 1.40 - (player.stats['accuracy'] / 100) * 0.80
# stat=50 → ×0.90,  stat=65 → ×0.68,  stat=80 → ×0.76
```
Multiplied against the scatter_range before drawing the random value. Higher accuracy
tightens the dispersion meaningfully.

#### B2-3: Putting stat → putter accuracy
The putter distance-accuracy degradation from B1-3 is softened by the putting stat:
```python
degradation = (shot_dist_yards / 100) * 0.40 * (1.0 - player.stats['putting'] / 100)
```
A putting stat of 80 nearly eliminates the distance degradation. This makes the putting
stat feel essential for competitive play.

#### B2-4: Short Game stat → wedge accuracy
Apply a similar multiplier to Pitching Wedge and Sand Wedge shots:
```python
if club.name in ("Pitching Wedge", "Sand Wedge"):
    scatter_range *= (1.40 - player.stats['short_game'] / 100 * 0.80)
```

#### B2-5: Mental stat → pressure penalty (tournament play)
In tournament rounds, apply a scatter multiplier when the player is within 3 strokes of
the lead on the back nine:
```python
pressure_extra = max(0.0, (3 - strokes_back) / 3) * (1.0 - player.stats['mental'] / 100)
scatter_range *= (1.0 + pressure_extra * 0.25)
```

#### B2-6: Fitness stat → late-round fatigue
After hole 12, degrade accuracy slightly each hole:
```python
fatigue = max(0, hole_index - 11) * 0.01 * (1.0 - player.stats['fitness'] / 100)
scatter_range *= (1.0 + fatigue)
```

---

### Phase B3 — Wind difficulty (implement with Phase B1)

#### B3-1: Scale wind effect up slightly
```python
wind_scale = tile_sz * 0.55   # was 0.40
```
At strength 5 this gives 88 px ≈ 27 yards — significant but not absurd on a full driver.
Combined with realistic scatter, high-wind holes become genuinely tactical.

#### B3-2: Wind affects putts slightly
Long putts (>15 yards) on exposed greens should drift slightly in wind. Apply 20% of
normal wind drift to putts over 15 yards.

---

## Expected Score Ranges After B1 Changes

| Player Type          | Expected Score (Par 72) |
|----------------------|------------------------|
| Pure beginner        | +18 to +28  (90–100)   |
| Learning the course  | +8 to +15   (80–87)    |
| Skilled amateur      | +2 to +8    (74–80)    |
| Near-scratch play    | -2 to +2    (70–74)    |
| Exceptional round    | -4 to -7    (65–68)    |

These targets match the Amateur Circuit difficulty. As the player progresses through tours
and raises stats, scoring should gradually improve to mirror real tour score distributions
(-6 to -12 under par on the World Tour and Grand Tour).

---

## Implementation Priority

| Priority | Change  | File(s)            | Effort |
|----------|---------|--------------------|--------|
| 1        | B1-1 capture radius | `ball.py`     | 1 line |
| 2        | B1-4 club accuracy  | `club.py`     | 8 lines|
| 3        | B1-2 scatter formula| `shot.py`     | ~15 lines |
| 4        | B1-3 putter distance| `shot.py`     | ~8 lines  |
| 5        | B1-5 terrain acc    | `terrain.py`  | 3 lines   |
| 6        | B3-1 wind scale     | `golf_round.py` | 1 line  |
| 7        | B2-x stat effects   | `golf_round.py` | ~40 lines |

All Phase B1 changes are small, targeted, and independently testable. Implement B1-1
first and test before proceeding — it may alone move scores from -22 to something closer
to the target range.
