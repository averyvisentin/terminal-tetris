"""Terminal Tetris - Entry point using refactored modules."""

from .database import delete_save_state, initialize_database, load_game_state, load_settings
from .input import handle_input
from .menus import handle_game_over, show_main_menu
from .models import Game
from .rendering import Screen, Styles, render_game
from .settings import SETTINGS


def game_loop(term, screen, styles, game):
    """Main game loop."""
    import time
    last_render_time = 0.0
    while not game.game_over:
        handle_input(term, game)
        game.update()
        now = time.time()
        if (now - last_render_time) * 1000 >= SETTINGS["RENDER_THROTTLE_MS"]:
            if not render_game(screen, styles, game):
                game.set_paused(True)
            last_render_time = now

    if game.quit_after_save:
        render_game(screen, styles, game, message="GAME SAVED")
        time.sleep(1)


def run(term, screen, styles):
    """Main run loop."""
    while True:
        gamemode, start_level = show_main_menu(term, screen, styles)
        if gamemode is None:
            return

        game = (
            load_game_state()
            if gamemode == "RESUME"
            else Game(gamemode=gamemode, start_level=start_level)
        )
        if game is None:
            continue

        game_loop(term, screen, styles, game)
        if game.quit_after_save:
            return
        if game.gamemode == "standard":
            delete_save_state()
        if not handle_game_over(term, screen, styles, game):
            return


def main():
    initialize_database()
    load_settings()
    from .constants import ERROR_LOG_FILE
    from blessed import Terminal
    import traceback

    term = Terminal()
    screen = Screen(term)
    styles = Styles(term)

    error_text = None
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            run(term, screen, styles)
        except KeyboardInterrupt:
            pass
        except Exception:
            error_text = traceback.format_exc()

    # Report after leaving fullscreen so the message is actually readable.
    if error_text:
        try:
            with open(ERROR_LOG_FILE, "w") as f:
                f.write(f"An unexpected error occurred:\n{error_text}")
            print(f"An unexpected error occurred. Details were written to {ERROR_LOG_FILE}")
        except OSError:
            print(error_text)
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()