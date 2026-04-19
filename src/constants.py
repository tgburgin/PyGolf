"""
Shared constants used across gameplay, rendering, and the editor.

Keep this module import-cheap — it should not depend on pygame or any
game state so it can be pulled in anywhere without circular-import risk.
"""

# Screen / viewport
SCREEN_W = 1280
SCREEN_H = 720
FPS      = 60

# The editor paints at this resolution; the game loader and renderer extract
# tiles at this pitch; importing from one place means editor and game cannot
# drift out of sync by mistake.
SOURCE_TILE = 16
