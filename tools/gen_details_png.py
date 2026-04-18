"""Generate placeholder Details.png RGBA tileset (8x5 grid of 16x16 tiles)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

pygame.init()

COLS, ROWS = 8, 5
TILE = 16
W, H = COLS * TILE, ROWS * TILE

surf = pygame.Surface((W, H), pygame.SRCALPHA)
surf.fill((0, 0, 0, 0))

def draw_tile(col, row, fn):
    tile = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    tile.fill((0, 0, 0, 0))
    fn(tile)
    surf.blit(tile, (col * TILE, row * TILE))

DARK_GREEN  = (30,  100, 30,  220)
MED_GREEN   = (50,  140, 50,  210)
LIGHT_GREEN = (80,  170, 60,  200)
TRUNK       = (100, 65,  30,  255)
GREY        = (140, 140, 140, 220)
BROWN       = (110, 80,  50,  220)
ROCK        = (120, 115, 110, 230)
BEIGE       = (200, 180, 140, 230)
RED         = (200, 50,  50,  230)
WHITE       = (240, 240, 240, 220)

# ── Row 0 — Single trees ──────────────────────────────────────────────────────
def tree_pine(t):
    pygame.draw.circle(t, DARK_GREEN, (8, 6), 5)
    pygame.draw.rect(t, TRUNK, (7, 11, 2, 4))

def tree_oak(t):
    pygame.draw.circle(t, MED_GREEN, (8, 7), 6)
    pygame.draw.circle(t, LIGHT_GREEN, (6, 5), 3)
    pygame.draw.rect(t, TRUNK, (7, 13, 2, 3))

def bush_small(t):
    pygame.draw.circle(t, MED_GREEN, (8, 10), 5)
    pygame.draw.circle(t, LIGHT_GREEN, (5, 8), 3)

def bush_large(t):
    pygame.draw.circle(t, DARK_GREEN, (8, 9), 6)
    pygame.draw.circle(t, MED_GREEN, (4, 7), 4)
    pygame.draw.circle(t, MED_GREEN, (12, 7), 4)

def tree_dead(t):
    pygame.draw.rect(t, (90, 60, 30, 200), (7, 2, 2, 12))
    pygame.draw.line(t, (90, 60, 30, 200), (8, 5), (3, 3), 1)
    pygame.draw.line(t, (90, 60, 30, 200), (8, 5), (13, 3), 1)
    pygame.draw.line(t, (90, 60, 30, 200), (8, 8), (4, 6), 1)
    pygame.draw.line(t, (90, 60, 30, 200), (8, 8), (12, 6), 1)

def tree_tall(t):
    pygame.draw.circle(t, DARK_GREEN, (8, 5), 4)
    pygame.draw.circle(t, MED_GREEN,  (8, 8), 5)
    pygame.draw.rect(t, TRUNK, (7, 13, 2, 3))

def tree_wide(t):
    pygame.draw.ellipse(t, MED_GREEN,   (1, 3, 14, 10))
    pygame.draw.ellipse(t, LIGHT_GREEN, (3, 4, 10,  7))
    pygame.draw.rect(t, TRUNK, (7, 13, 2, 3))

def tree_round(t):
    pygame.draw.circle(t, MED_GREEN,   (8, 8), 6)
    pygame.draw.circle(t, LIGHT_GREEN, (8, 7), 4)
    pygame.draw.rect(t, TRUNK, (7, 14, 2, 2))

for i, fn in enumerate([tree_pine, tree_oak, bush_small, bush_large,
                         tree_dead, tree_tall, tree_wide, tree_round]):
    draw_tile(i, 0, fn)

# ── Row 1 — Clusters ──────────────────────────────────────────────────────────
def cluster_2(t):
    pygame.draw.circle(t, DARK_GREEN, (5, 8), 4)
    pygame.draw.circle(t, MED_GREEN,  (11, 7), 4)

def cluster_3(t):
    pygame.draw.circle(t, DARK_GREEN,  (4, 9), 4)
    pygame.draw.circle(t, MED_GREEN,   (12, 9), 4)
    pygame.draw.circle(t, LIGHT_GREEN, (8, 5), 4)

def cluster_dense(t):
    pygame.draw.ellipse(t, DARK_GREEN,  (0, 2, 16, 12))
    pygame.draw.circle(t, MED_GREEN,   (5, 6), 3)
    pygame.draw.circle(t, LIGHT_GREEN, (11, 5), 3)

def cluster_row(t):
    for x in [3, 8, 13]:
        pygame.draw.circle(t, MED_GREEN, (x, 8), 3)

def undergrowth(t):
    for pt in [(3, 12), (7, 11), (11, 12), (5, 13), (9, 13)]:
        pygame.draw.circle(t, (40, 100, 40, 180), pt, 2)

def fern(t):
    for i in range(5):
        pygame.draw.line(t, (30, 120, 50, 200),
                         (8, 12), (8 + (i - 2) * 3, 6 + i % 2), 2)

def canopy(t):
    pygame.draw.ellipse(t, (25, 80, 25, 200), (1, 1, 14, 14))

def forest_edge(t):
    pygame.draw.ellipse(t, DARK_GREEN, (0, 0, 10, 16))
    pygame.draw.ellipse(t, MED_GREEN,  (6, 2, 10, 14))

for i, fn in enumerate([cluster_2, cluster_3, cluster_dense, cluster_row,
                         undergrowth, fern, canopy, forest_edge]):
    draw_tile(i, 1, fn)

# ── Row 2 — Structures ────────────────────────────────────────────────────────
def fence_h(t):
    pygame.draw.rect(t, BROWN, (0, 7, 16, 2))
    for x in [2, 6, 10, 14]:
        pygame.draw.rect(t, BROWN, (x - 1, 4, 2, 8))

def fence_v(t):
    pygame.draw.rect(t, BROWN, (7, 0, 2, 16))
    for y in [2, 6, 10, 14]:
        pygame.draw.rect(t, BROWN, (4, y - 1, 8, 2))

def fence_corner(t):
    pygame.draw.rect(t, BROWN, (7, 7, 2, 9))
    pygame.draw.rect(t, BROWN, (0, 7, 9, 2))

def low_wall(t):
    pygame.draw.rect(t, GREY, (0, 9, 16, 5))
    for x in range(0, 16, 4):
        pygame.draw.line(t, (100, 100, 100, 220), (x, 9), (x, 14))

def gate(t):
    pygame.draw.rect(t, BROWN, (0, 5, 3, 10))
    pygame.draw.rect(t, BROWN, (13, 5, 3, 10))
    pygame.draw.line(t, BROWN, (3, 7), (13, 7), 1)
    pygame.draw.line(t, BROWN, (3, 10), (13, 10), 1)

def path_h(t):
    pygame.draw.rect(t, (180, 170, 140, 200), (0, 6, 16, 4))

def path_v(t):
    pygame.draw.rect(t, (180, 170, 140, 200), (6, 0, 4, 16))

def path_cross(t):
    pygame.draw.rect(t, (180, 170, 140, 200), (0, 6, 16, 4))
    pygame.draw.rect(t, (180, 170, 140, 200), (6, 0, 4, 16))

for i, fn in enumerate([fence_h, fence_v, fence_corner, low_wall,
                         gate, path_h, path_v, path_cross]):
    draw_tile(i, 2, fn)

# ── Row 3 — Rocks & props ─────────────────────────────────────────────────────
def rock_small(t):
    pygame.draw.ellipse(t, ROCK, (4, 9, 8, 5))
    pygame.draw.ellipse(t, (160, 155, 150, 200), (5, 10, 3, 2))

def rock_large(t):
    pygame.draw.ellipse(t, ROCK, (2, 6, 12, 8))
    pygame.draw.ellipse(t, (150, 145, 140, 180), (3, 7, 5, 3))

def boulder(t):
    pygame.draw.circle(t, ROCK, (8, 9), 6)
    pygame.draw.ellipse(t, (150, 145, 140, 180), (5, 8, 5, 3))

def flower_patch(t):
    for pos, col in [((4, 10), (255, 200, 50, 220)),
                     ((9, 8),  (255, 100, 150, 220)),
                     ((12, 11),(100, 180, 255, 220)),
                     ((7, 12), (255, 150, 50, 220))]:
        pygame.draw.circle(t, col, pos, 2)
        pygame.draw.circle(t, (255, 255, 255, 200), pos, 1)

def tall_grass(t):
    for x in [3, 6, 9, 12]:
        pygame.draw.line(t, (80, 140, 40, 200), (x, 14), (x - 1, 4), 1)
        pygame.draw.line(t, (60, 120, 30, 180), (x, 14), (x + 1, 5), 1)

def mushroom(t):
    pygame.draw.ellipse(t, (200, 50, 50, 220), (4, 5, 8, 5))
    pygame.draw.rect(t, (220, 200, 180, 220), (7, 10, 2, 4))

def log(t):
    pygame.draw.ellipse(t, (120, 80, 50, 220), (1, 8, 14, 5))
    pygame.draw.ellipse(t, (150, 100, 60, 200), (1, 8, 4, 5))
    pygame.draw.ellipse(t, (150, 100, 60, 200), (11, 8, 4, 5))

def pond(t):
    pygame.draw.ellipse(t, (50, 100, 200, 200), (2, 4, 12, 9))
    pygame.draw.ellipse(t, (100, 160, 240, 150), (5, 6, 5, 4))

for i, fn in enumerate([rock_small, rock_large, boulder, flower_patch,
                         tall_grass, mushroom, log, pond]):
    draw_tile(i, 3, fn)

# ── Row 4 — Buildings / markers ───────────────────────────────────────────────
def shed(t):
    pygame.draw.rect(t, BEIGE, (3, 7, 10, 7))
    pygame.draw.polygon(t, (150, 130, 100, 230), [(3, 7), (8, 2), (13, 7)])
    pygame.draw.rect(t, (80, 60, 40, 220), (6, 10, 4, 4))

def score_hut(t):
    pygame.draw.rect(t, WHITE, (2, 8, 12, 6))
    pygame.draw.polygon(t, RED, [(2, 8), (8, 3), (14, 8)])
    pygame.draw.rect(t, (60, 60, 60, 200), (6, 11, 4, 3))

def flag_pole(t):
    pygame.draw.line(t, (200, 200, 200, 230), (8, 2), (8, 14), 1)
    pygame.draw.polygon(t, RED, [(8, 2), (14, 5), (8, 8)])

def dist_red(t):
    pygame.draw.rect(t, (200, 60, 60, 220), (4, 3, 8, 10))
    pygame.draw.rect(t, WHITE, (5, 4, 6, 8))

def dist_yellow(t):
    pygame.draw.rect(t, (200, 180, 50, 220), (4, 3, 8, 10))
    pygame.draw.rect(t, WHITE, (5, 4, 6, 8))

def dist_blue(t):
    pygame.draw.rect(t, (60, 60, 200, 220), (4, 3, 8, 10))
    pygame.draw.rect(t, WHITE, (5, 4, 6, 8))

def bunker_edge(t):
    pygame.draw.arc(t, (220, 200, 150, 220),
                    pygame.Rect(0, 0, 16, 16), 0, 3.14159, 3)

def water_lily(t):
    pygame.draw.circle(t, (50, 150, 80, 200), (8, 8), 6)
    pygame.draw.circle(t, (255, 220, 100, 220), (8, 8), 2)

for i, fn in enumerate([shed, score_hut, flag_pole, dist_red, dist_yellow,
                         dist_blue, bunker_edge, water_lily]):
    draw_tile(i, 4, fn)

# ── Save ──────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "..", "assets", "tilemaps", "Details.png")
pygame.image.save(surf, out)
print(f"Saved {W}x{H} RGBA PNG to: {out}")
