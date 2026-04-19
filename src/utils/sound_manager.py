"""
sound_manager.py — Audio system for Golf!

Real audio files are loaded from assets/sounds/ when present (WAV or OGG).
If a file is missing the manager synthesises a simple procedural replacement
so the game always has some audio without requiring any asset downloads.

Sound IDs
---------
  swing           club whoosh on shot release
  hit             generic ball-landing sound
  hit_rough       ball in rough
  hit_bunker      ball in bunker (sand thud)
  hit_water       splash
  hit_trees       wood knock
  ball_in_hole    satisfying plop as ball sinks
  birdie          two-note ascending jingle
  eagle           three-note ascending jingle
  hole_in_one     short fanfare
  crowd_cheer     burst of crowd noise
  ambient_birds   (looping) outdoor birdsong
  ambient_crowd   (looping) crowd murmur

Volume
------
  master_vol, sfx_vol, ambient_vol — each 0.0–1.0
  Effective SFX vol  = master_vol * sfx_vol
  Effective ambient  = master_vol * ambient_vol
"""

import array
import math
import os
import random

import pygame

SAMPLE_RATE = 44100
_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sounds"))
_SETTINGS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings.json"))


# ── Synthesis helpers ─────────────────────────────────────────────────────────

def _buf(mono: list) -> pygame.mixer.Sound:
    """Convert a mono float[-1..1] list to a stereo pygame.mixer.Sound."""
    raw = array.array('h')
    for s in mono:
        v = int(max(-32767, min(32767, s * 32767)))
        raw.append(v)   # left
        raw.append(v)   # right
    return pygame.mixer.Sound(buffer=raw)


def _silence(duration: float) -> list:
    return [0.0] * int(SAMPLE_RATE * duration)


def _env(n: int, attack: float = 0.05, decay: float = 0.3) -> list:
    """Simple attack-decay amplitude envelope, length n samples."""
    env = []
    atk = max(1, int(n * attack))
    for i in range(n):
        if i < atk:
            env.append(i / atk)
        else:
            t = (i - atk) / max(1, n - atk)
            env.append(math.exp(-decay * 10 * t))
    return env


def _noise(n: int, rng: random.Random) -> list:
    return [rng.uniform(-1, 1) for _ in range(n)]


def _sine(freq: float, n: int) -> list:
    return [math.sin(2 * math.pi * freq * i / SAMPLE_RATE) for i in range(n)]


def _tone(freq: float, duration: float, vol: float = 0.6,
          attack: float = 0.02, decay: float = 0.5) -> list:
    n = int(SAMPLE_RATE * duration)
    wave = _sine(freq, n)
    e    = _env(n, attack, decay)
    return [wave[i] * e[i] * vol for i in range(n)]


def _mix(*tracks) -> list:
    """Mix multiple same-length sample lists by averaging."""
    n = max(len(t) for t in tracks)
    result = [0.0] * n
    for t in tracks:
        for i in range(len(t)):
            result[i] += t[i]
    peak = max(abs(s) for s in result) if result else 1.0
    if peak > 1.0:
        result = [s / peak for s in result]
    return result


def _concat(*tracks) -> list:
    out = []
    for t in tracks:
        out.extend(t)
    return out


# ── Sound synthesis recipes ────────────────────────────────────────────────────

def _synth_swing(rng: random.Random) -> list:
    n = int(SAMPLE_RATE * 0.22)
    noise = _noise(n, rng)
    # bell-curve envelope peaking at 30% of the way through
    result = []
    for i in range(n):
        t = i / n
        amp = 0.7 * math.exp(-((t - 0.28) ** 2) / 0.025)
        result.append(noise[i] * amp)
    return result


def _synth_hit(rng: random.Random, pitch: float = 900, decay: float = 40.0,
               noise_mix: float = 0.4) -> list:
    n = int(SAMPLE_RATE * 0.14)
    result = []
    for i in range(n):
        t = i / n
        env = math.exp(-decay * t)
        click = math.sin(2 * math.pi * pitch * i / SAMPLE_RATE) * math.exp(-60 * t)
        noise = rng.uniform(-1, 1) * noise_mix
        result.append((click * (1 - noise_mix) + noise) * env * 0.7)
    return result


def _synth_splash(rng: random.Random) -> list:
    n = int(SAMPLE_RATE * 0.38)
    result = []
    for i in range(n):
        t = i / n
        env = math.exp(-8 * t) * (1 - math.exp(-60 * t))  # fast attack
        noise = rng.uniform(-1, 1)
        # Low-freq oscillation for water character
        osc = math.sin(2 * math.pi * 80 * t) * 0.3
        result.append((noise * 0.6 + osc) * env * 0.8)
    return result


def _synth_bunker(rng: random.Random) -> list:
    n = int(SAMPLE_RATE * 0.20)
    result = []
    for i in range(n):
        t = i / n
        # Dull low thud + sand hiss
        thud  = math.sin(2 * math.pi * 120 * i / SAMPLE_RATE) * math.exp(-25 * t)
        hiss  = rng.uniform(-1, 1) * math.exp(-15 * t) * 0.25
        result.append((thud * 0.6 + hiss) * 0.7)
    return result


def _synth_trees(rng: random.Random) -> list:
    n = int(SAMPLE_RATE * 0.16)
    result = []
    for i in range(n):
        t = i / n
        thud  = math.sin(2 * math.pi * 200 * i / SAMPLE_RATE) * math.exp(-40 * t)
        rustle = rng.uniform(-1, 1) * math.exp(-12 * t) * 0.3
        result.append((thud * 0.5 + rustle) * 0.75)
    return result


def _synth_hole(rng: random.Random) -> list:
    plop = []
    n    = int(SAMPLE_RATE * 0.18)
    for i in range(n):
        t = i / n
        plop.append(math.sin(2 * math.pi * 200 * i / SAMPLE_RATE) * math.exp(-20 * t) * 0.6)
    tones = _concat(
        _tone(523, 0.10, 0.35),   # C
        _tone(659, 0.10, 0.35),   # E
        _tone(784, 0.18, 0.35),   # G
    )
    gap = [0.0] * int(SAMPLE_RATE * 0.05)
    return _concat(plop, gap, tones)


def _synth_birdie() -> list:
    return _concat(
        _tone(784, 0.12, 0.5),    # G5
        _tone(1047, 0.20, 0.5),   # C6
    )


def _synth_eagle() -> list:
    return _concat(
        _tone(784, 0.10, 0.55),
        _tone(988, 0.10, 0.55),
        _tone(1175, 0.28, 0.55),
    )


def _synth_hole_in_one() -> list:
    return _concat(
        _tone(523, 0.08, 0.5),
        _tone(659, 0.08, 0.5),
        _tone(784, 0.08, 0.5),
        _tone(1047, 0.40, 0.6),
    )


def _synth_cheer(rng: random.Random) -> list:
    n = int(SAMPLE_RATE * 0.55)
    result = []
    for i in range(n):
        t = i / n
        # Crescendo then decay
        env = math.exp(-((t - 0.35) ** 2) / 0.04) * 0.75
        noise = rng.uniform(-1, 1)
        # Add some formant-like colour
        mod = 0.4 * math.sin(2 * math.pi * 180 * t) + 0.3 * math.sin(2 * math.pi * 320 * t)
        result.append((noise * 0.6 + mod * 0.4) * env)
    return result


def _synth_bird_tweet(rng: random.Random) -> list:
    """A single short bird tweet — 0.5 s, two or three chirp syllables."""
    n   = int(SAMPLE_RATE * 0.5)
    out = [0.0] * n

    def chirp(start_i, base_freq, rise=0.15, duration=0.07):
        dur = int(SAMPLE_RATE * duration)
        for j in range(dur):
            t   = j / dur
            f   = base_freq * (1 + t * rise)
            env = math.sin(math.pi * t) ** 0.7
            s   = math.sin(2 * math.pi * f * j / SAMPLE_RATE) * env * 0.30
            if start_i + j < n:
                out[start_i + j] += s

    base = rng.uniform(2400, 3600)
    # Two or three syllables with a short gap between each
    syllables = rng.randint(2, 3)
    offset = 0
    for _ in range(syllables):
        chirp(offset, base, rise=rng.uniform(0.08, 0.22))
        offset += int(SAMPLE_RATE * rng.uniform(0.10, 0.16))

    return out


def _synth_crowd_ambient(rng: random.Random) -> list:
    """2-second looping crowd murmur."""
    n   = int(SAMPLE_RATE * 2.0)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        # Low formant chatter
        v   = (rng.uniform(-1, 1) * 0.18
               + math.sin(2 * math.pi * 160 * t) * 0.06
               + math.sin(2 * math.pi * 280 * t) * 0.05
               + math.sin(2 * math.pi * 420 * t) * 0.04)
        out.append(v)
    return out


# ── SoundManager ─────────────────────────────────────────────────────────────

class SoundManager:
    """Singleton audio manager — call SoundManager.instance() everywhere."""

    _instance: "SoundManager | None" = None

    @classmethod
    def instance(cls) -> "SoundManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._sounds:  dict[str, pygame.mixer.Sound] = {}
        self._ready    = False
        self._ambient_channel: pygame.mixer.Channel | None = None

        # Bird tweet scheduling
        self._bird_mode  = False
        self._bird_timer = 0.0        # counts down to next tweet
        self._bird_rng   = random.Random()

        # Crowd murmur scheduling
        self._crowd_mode  = False
        self._crowd_timer = 0.0
        self._crowd_rng   = random.Random()

        # Volume settings
        self.master_vol  = 1.0
        self.sfx_vol     = 0.9
        self.ambient_vol = 0.5

        self._load_settings()

    # ── Initialise ────────────────────────────────────────────────────────────

    def init(self) -> None:
        """Call once after pygame.mixer.init()."""
        if self._ready:
            return
        rng = random.Random(99)
        _RECIPES = {
            "swing":         lambda: _buf(_synth_swing(rng)),
            "hit":           lambda: _buf(_synth_hit(rng, 900, 40, 0.35)),
            "hit_rough":     lambda: _buf(_synth_hit(rng, 650, 30, 0.55)),
            "hit_bunker":    lambda: _buf(_synth_bunker(rng)),
            "hit_water":     lambda: _buf(_synth_splash(rng)),
            "hit_trees":     lambda: _buf(_synth_trees(rng)),
            "ball_in_hole":  lambda: _buf(_synth_hole(rng)),
            "birdie":        lambda: _buf(_synth_birdie()),
            "eagle":         lambda: _buf(_synth_eagle()),
            "hole_in_one":   lambda: _buf(_synth_hole_in_one()),
            "crowd_cheer":   lambda: _buf(_synth_cheer(rng)),
            "bird_tweet":    lambda: _buf(_synth_bird_tweet(rng)),
            "ambient_crowd": lambda: _buf(_synth_crowd_ambient(rng)),
        }
        for sid, recipe in _RECIPES.items():
            path = os.path.join(_ASSETS_DIR, f"{sid}.ogg")
            if not os.path.exists(path):
                path = os.path.join(_ASSETS_DIR, f"{sid}.wav")
            if os.path.exists(path):
                try:
                    self._sounds[sid] = pygame.mixer.Sound(path)
                    continue
                except Exception:
                    pass
            try:
                self._sounds[sid] = recipe()
            except Exception as e:
                print(f"[SoundManager] Could not create '{sid}': {e}")

        self._apply_volumes()
        self._ready = True

    # ── Playback ──────────────────────────────────────────────────────────────

    def play(self, sid: str) -> None:
        if not self._ready:
            return
        s = self._sounds.get(sid)
        if s:
            s.play()

    def play_crowd_cheer(self) -> None:
        """Play a crowd cheer only when crowd ambient is active for this course."""
        if self._crowd_mode:
            self.play("crowd_cheer")

    def play_ambient(self, sid: str) -> None:
        if not self._ready:
            return
        self.stop_ambient()
        if sid == "ambient_birds":
            self._bird_mode  = True
            self._bird_timer = self._bird_rng.uniform(4.0, 10.0)
        elif sid == "ambient_crowd":
            self._crowd_mode  = True
            self._crowd_timer = self._crowd_rng.uniform(30.0, 90.0)
        else:
            s = self._sounds.get(sid)
            if s:
                self._ambient_channel = s.play(loops=-1)

    def stop_ambient(self) -> None:
        self._bird_mode  = False
        self._crowd_mode = False
        if self._ambient_channel is not None:
            self._ambient_channel.stop()
            self._ambient_channel = None

    def update(self, dt: float) -> None:
        """Call every frame to drive occasional ambient sounds."""
        if not self._ready:
            return
        if self._bird_mode:
            self._bird_timer -= dt
            if self._bird_timer <= 0.0:
                s = self._sounds.get("bird_tweet")
                if s:
                    s.set_volume(self.master_vol * self.ambient_vol)
                    s.play()
                self._bird_timer = self._bird_rng.uniform(8.0, 25.0)
        if self._crowd_mode:
            self._crowd_timer -= dt
            if self._crowd_timer <= 0.0:
                s = self._sounds.get("ambient_crowd")
                if s:
                    s.set_volume(self.master_vol * self.ambient_vol)
                    s.play()
                self._crowd_timer = self._crowd_rng.uniform(30.0, 90.0)

    # ── Volume ────────────────────────────────────────────────────────────────

    def set_master(self, v: float) -> None:
        self.master_vol = max(0.0, min(1.0, v))
        self._apply_volumes()
        self._save_settings()

    def set_sfx(self, v: float) -> None:
        self.sfx_vol = max(0.0, min(1.0, v))
        self._apply_volumes()
        self._save_settings()

    def set_ambient(self, v: float) -> None:
        self.ambient_vol = max(0.0, min(1.0, v))
        self._apply_volumes()
        self._save_settings()

    def _apply_volumes(self) -> None:
        """Bake master * category volume into each Sound object."""
        ambient_ids = {"ambient_birds"}
        for sid, s in self._sounds.items():
            if sid in ambient_ids:
                s.set_volume(self.master_vol * self.ambient_vol)
            else:
                s.set_volume(self.master_vol * self.sfx_vol)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_settings(self) -> None:
        try:
            import json
            with open(_SETTINGS_PATH, "r") as f:
                data = json.load(f)
            self.master_vol  = float(data.get("master_vol",  1.0))
            self.sfx_vol     = float(data.get("sfx_vol",     0.9))
            self.ambient_vol = float(data.get("ambient_vol", 0.5))
        except Exception:
            pass

    def _save_settings(self) -> None:
        try:
            import json, os as _os
            _os.makedirs(_os.path.dirname(_SETTINGS_PATH), exist_ok=True)
            with open(_SETTINGS_PATH, "w") as f:
                json.dump({
                    "master_vol":  round(self.master_vol,  2),
                    "sfx_vol":     round(self.sfx_vol,     2),
                    "ambient_vol": round(self.ambient_vol, 2),
                }, f, indent=2)
        except Exception:
            pass
