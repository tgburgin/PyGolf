# Let's Golf! ⛳

A top-down 2D pixel art golf career game built in Python. Work your way up from the Amateur Circuit to the Grand Tour, win the 4 Majors, and reach World No. 1.

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/Golf.git
cd Golf

# 2. Install the one dependency
pip install pygame-ce

# 3. Play
python main.py
```

> **Note:** The game uses `pygame-ce` (the community edition fork), not standard `pygame`. If you have standard `pygame` installed, uninstall it first: `pip uninstall pygame`

**Python 3.11+ required.**

---

## What Is It?

Let's Golf! is a full career golf game where you create a golfer and guide them from local amateur tournaments all the way to the sport's biggest stage. Between rounds you train your stats, upgrade your clubs, hire staff, and sign sponsorship deals.

The game is entirely mouse-driven and plays out in top-down 2D with tile-based courses.

---

## Controls

| Action | Control |
|---|---|
| Start aiming | Left-click on the ball |
| Set power & direction | Drag away from the ball |
| Hit the shot | Release the mouse button |
| Cancel shot | Right-click |
| Change club | Scroll wheel  or  ← → arrow keys |
| Select club from bag | Click the club name in the HUD |
| Set shot shape (Draw/Straight/Fade) | Click the shape buttons in the HUD |

---

## Features

### On the Course
- **Click-drag-release** shot mechanic with a live power bar and aim line
- **Shot shaping** — play Draws (right-to-left curve) and Fades (left-to-right) as well as straight shots
- **Wind** — randomised direction and strength each hole, shown by a compass arrow in the HUD
- **Terrain system** — every surface affects your shot differently:

| Terrain | Distance | Accuracy |
|---|---|---|
| Tee / Fairway | Full | Full |
| Rough | −25% | −20% |
| Deep Rough | −45% | −40% |
| Bunker | −40% | −30% |
| Trees | −60% | −70% |
| Water | Penalty + drop | — |

- **Camera** follows the ball in flight; a pin indicator and distance readout keep you oriented
- **Putting** — putter auto-selects on the green; short putts are unaffected by wind
- **Hole-in-one, Eagle, Birdie, Par, Bogey** — all called out with sound and colour

### Career Progression

Six tour levels, each with its own schedule, courses, prize fund, and AI field:

| Level | Tour | Events | Prize Fund |
|---|---|---|---|
| 1 | Amateur Circuit | 8 | Trophies only |
| 2 | Challenger Tour | 10 | Small |
| 3 | Development Tour | 12 | Medium |
| 4 | Continental Tour | 14 | Good |
| 5 | World Tour | 16 | Large |
| 6 | The Grand Tour | 18 | Major prize |

- Finish in the **top positions** at season end to earn promotion
- Tour 4 → 5 requires passing a **Q-School Qualifier** against a World Tour field
- Tour 5 → 6 also requires a **World Ranking of top 50**

### Between Rounds — Career Hub

- **Training** — spend prize money to raise any of your 6 stats (Power, Accuracy, Short Game, Putting, Mental, Fitness). Each stat directly affects your shots in play.
- **Equipment** — upgrade your club set through 5 tiers, unlocked as you reach higher tours
- **Staff** *(Continental Tour and above)* — hire a Coach, Caddie, Sports Psychologist, or Fitness Trainer, each giving permanent stat bonuses
- **Sponsors** *(Continental Tour and above)* — sign deals for a signing fee and a season bonus if you hit a performance target (top-5 finishes, wins, etc.)
- **Career Stats** — full career history, achievements, world ranking, majors won

### The Grand Tour & Majors

Four major championships are held at fixed points in the Grand Tour season:

- The Green Jacket Invitational
- The Heritage Open
- The Royal Championship
- The Grand Classic

Majors are 2-round events with prize funds of up to $5,000,000 and award double world ranking points.

**Win condition:** win all 4 Majors AND reach World No. 1.

### World Rankings

From the Continental Tour onward, every result earns ranking points. You are ranked against a field of 200 simulated professionals — reaching No. 1 is the final milestone of the career.

### Saving

The game auto-saves after every round. Multiple save slots are supported; load and delete saves from the main menu.

---

## Project Structure

```
Golf/
├── main.py              ← run this to play
├── editor.py            ← course editor (developer tool)
├── requirements.txt
├── src/
│   ├── game.py          ← state machine & main loop
│   ├── career/          ← player, opponents, tournaments, staff, sponsors, rankings
│   ├── course/          ← hole layout, renderer, course loader
│   ├── data/            ← courses, tour configs, opponent pools
│   ├── golf/            ← ball physics, shot mechanics, clubs, terrain
│   ├── states/          ← one file per screen (menu, hub, round, results…)
│   ├── ui/              ← HUD, scorecard
│   └── utils/           ← save system, sound manager, maths helpers
├── assets/
│   ├── tilemaps/        ← terrain tile PNGs used by the renderer
│   └── sounds/          ← drop WAV/OGG files here to replace synthetic audio
├── data/
│   └── courses/         ← JSON course files output by the editor
└── saves/               ← auto-created; not committed to the repo
```

---

## Course Editor

A separate tile-based course editor is included for building new holes:

```bash
pip install pygame-ce pygame_gui
python editor.py
```

The editor lets you paint terrain tiles, set gameplay attributes (fairway, rough, bunker, water, etc.), place tee and pin positions, and export finished courses directly into the game's JSON format.

---

## Audio

The game generates all sounds synthetically at startup — no audio files are required to run. If you want higher-quality audio, drop your own WAV or OGG files into `assets/sounds/` using these names:

`swing.wav` · `hit.wav` · `hit_rough.wav` · `hit_bunker.wav` · `hit_water.wav` · `hit_trees.wav` · `ball_in_hole.wav` · `birdie.wav` · `eagle.wav` · `hole_in_one.wav` · `ambient_crowd.ogg` · `bird_tweet.wav`

Volume for Master, Sound Effects, and Ambient can be adjusted in the Settings panel on the main menu.

---

## Dependencies

| Package | Purpose | Install |
|---|---|---|
| `pygame-ce` | Game rendering, input, audio | `pip install pygame-ce` |
| `pygame_gui` | Editor UI panels | `pip install pygame_gui` *(editor only)* |

No other dependencies. Everything else uses the Python standard library.
