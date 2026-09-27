"""Entry point: initialise Pygame and run the game."""

from flappy_bird.game import Game


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
