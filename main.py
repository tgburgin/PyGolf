"""
Let's Golf! - Main entry point.
Run this file to start the game: python main.py

The main loop is `async` so the same file can be built for the web/Android
with pygbag (`pygbag main.py`). On CPython `asyncio.run(main())` behaves
exactly like a normal loop; on Emscripten pygbag rewrites the `while True`
into a requestAnimationFrame driver, and the `await asyncio.sleep(0)` at the
bottom of the loop is what hands control back to the browser each frame.
"""

import asyncio
import sys

import pygame

from src.constants import SCREEN_W, SCREEN_H, FPS
from src.game import Game
from src.utils import web


def _create_display():
    """Open the window/canvas at the logical 1280×720 size.

    On Emscripten (pygbag → phone browser) we also request FULLSCREEN and
    SCALED so the canvas fills the device and pygame auto-scales the logical
    surface — including translating mouse/touch event positions back into
    1280×720 coordinates, which is what every state expects.

    On desktop SCALED alone lets the player resize the window without any
    layout code having to care.
    """
    pygame.display.set_caption("Let's Golf!")
    flags = pygame.SCALED
    if web.IS_WEB:
        flags |= pygame.FULLSCREEN
    return pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)


def _draw_portrait_overlay(screen):
    """Fill the screen with a 'rotate to landscape' prompt.

    Called in place of normal game drawing while the browser viewport is
    portrait-oriented. Keeps the prompt self-contained so it also works
    before the first state has drawn anything.
    """
    screen.fill((8, 14, 8))
    title_font = pygame.font.SysFont("arial", 56, bold=True)
    body_font  = pygame.font.SysFont("arial", 28)
    title = title_font.render("Rotate your phone", True, (168, 224, 88))
    body  = body_font.render("Let's Golf! plays in landscape.", True, (200, 220, 200))
    sw, sh = screen.get_size()
    screen.blit(title, title.get_rect(center=(sw // 2, sh // 2 - 30)))
    screen.blit(body,  body.get_rect(center=(sw // 2, sh // 2 + 30)))


async def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    screen = _create_display()
    clock  = pygame.time.Clock()

    # Pre-build all synthetic sounds (< 0.5 s; happens before the first frame)
    from src.utils.sound_manager import SoundManager
    SoundManager.instance().init()

    game = Game(screen)

    # Browsers typically only grant fullscreen + orientation-lock requests
    # that originate inside a user gesture, so the startup call is a
    # best-effort (it'll usually be a no-op) and we retry after the first
    # input event below.
    web.try_lock_landscape()
    _gesture_claimed = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        portrait = web.is_portrait()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # First real input unlocks fullscreen + orientation lock on web.
            # Gated to once per session so we don't spam the browser with
            # requestFullscreen calls, which some browsers throttle.
            if (web.IS_WEB and not _gesture_claimed
                    and event.type in (pygame.MOUSEBUTTONDOWN,
                                       pygame.FINGERDOWN,
                                       pygame.KEYDOWN)):
                web.try_enter_fullscreen()
                web.try_lock_landscape()
                _gesture_claimed = True

            # While the phone is held in portrait, swallow input so a stray
            # tap on the rotate prompt doesn't click buttons underneath.
            if portrait:
                continue

            game.handle_event(event)

        if not running:
            break

        if portrait:
            _draw_portrait_overlay(screen)
        else:
            game.update(dt)
            game.draw()

        pygame.display.flip()

        # Yield to the browser event loop on Emscripten; no-op on desktop.
        await asyncio.sleep(0)

    pygame.quit()
    if not web.IS_WEB:
        sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
