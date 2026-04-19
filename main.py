"""
Let's Golf! - Main entry point.
Run this file to start the game: python main.py
"""

import pygame
import sys

from src.constants import SCREEN_W, SCREEN_H, FPS
from src.game import Game


def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.display.set_caption("Let's Golf!")

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    # Pre-build all synthetic sounds (< 0.5 s; happens before the first frame)
    from src.utils.sound_manager import SoundManager
    SoundManager.instance().init()

    game = Game(screen)

    while True:
        # Delta time in seconds — keeps game speed independent of frame rate
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        game.update(dt)
        game.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()
