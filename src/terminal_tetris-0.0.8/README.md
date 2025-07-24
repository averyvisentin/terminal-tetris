# Terminal Tetris

This is a terminal-based Tetris game written in Python. It aims to be a feature-rich implementation of the classic game with modern mechanics. This project was created for personal use.
-----

![screenshot](./screenshots/game.png) ![screenshot](./screenshots/settings.png)
-----

## Features

  * **Classic Tetris Gameplay**: A fully-featured Tetris implementation for the terminal.
  * **GAMEMODES**: We've got Marathon, Sprint, Timed. We even got Garbage.
  * **Modern Mechanics**: Includes advanced mechanics like T-Spin detection and a back-to-back bonus system.
  * **Save state**: Includes a save state feature that allows you to pause the game and resume it later. (hit 's' while game is paused). Saving will close the game. Resume from Main Menu on next startup. **only works on marathon right now**
  * **Hold Functionality**: Swap out the current piece with a stored piece.
  * **Persistent Database**: All high scores and user settings are saved to a local tetris.db file, so your progress and customizations are always remembered.
  * **Settings Menu**: Customize everything from keybindings to game physics and scoring values.
  * **Ghost Piece**: A preview of where the current piece will land. (Toggle in Settings Menu)
  * **High Score Tracking**: The top 5 scores are saved and displayed on the main menu.
  * **Level Progression**: The game's speed increases as you clear more lines.
  * **Proper Lock Delay**: A half-second delay after a piece touches a surface, allowing for last-second adjustments. (adjustable in Settings Menu)
  * **Bag Randomization**: A 7-bag randomization system ensures that all seven tetrominoes will appear in a random order before any are repeated.

-----
![screenshot](./screenshots/main-menu.png)
-----

## How to Play

### Installation

Install with pip or whatver you use:
    ```bash
    pip install terminal-tetris
    ```
We're [NOW ON THE AUR](https://aur.archlinux.org/packages/terminal-tetris)

Install with your favourite thing using
    ```bash
    yay -S terminal-tetris
    ```

### Running the Game

You can run the game using the following command:

```bash
terminal-tetris
```

-----
![screenshot](./screenshots/garbage.png)
-----
## Controls

| Key         | Action        |
| :---------- | :------------ |
| `←` / `→`   | Move          |
| `↑`         | Rotate        |
| `↓`         | Soft Drop     |
| `Space`     | Hard Drop     |
| `c`         | Hold          |
| `p`         | Pause         |
| `s`         | Save (paused) |
| `q`         | Quit          |

-----

![sceenshot](./screenshots/game-paused.png)

-----

## Scoring

The scoring system is based on modern Tetris guidelines, with the base score multiplied by the current level.

| Action              | Score     |
| :------------------ | :-------- |
| Single              | 100       |
| Double              | 300       |
| Triple              | 500       |
| Tetris              | 800       |
| T-Spin Mini         | 100       |
| T-Spin              | 400       |
| T-Spin Single       | 800       |
| T-Spin Double       | 1200      |
| T-Spin Triple       | 1600      |
| Back-to-Back Bonus  | 1.5x      |


-----

![screenshot](./screenshots/new-score.png)

-----
## High Scores

The game keeps track of the top 5 high scores in a `tetris.db` file. If you achieve a high score, you will be prompted to enter a three-character name.

-----

![screenshot](./screenshots/game-over.png)

-----

## Inspirations

I really wanted something lightweight and fun to play while I waited for things to load, compile, laundry to finish, and other mundane tasks.
I was heavily inspired by the classic Tetris game on the gameboy, shtris, and vitetris.

## Credits

Tetris © 1985~2025 Tetris Holding.
Tetris logos, Tetris theme song and Tetriminos are trademarks of Tetris Holding.
The Tetris trade dress is owned by Tetris Holding.
Licensed to The Tetris Company.
Tetris Game Design by Alexey Pajitnov.
Tetris Logo Design by Roger Dean.
All Rights Reserved.

- [blessed @ github](https://github.com/jquast/blessed)
- [blessed @ pypi](https://pypi.org/project/blessed/)
- [shtris @ github](https://github.com/ContentsViewer/shtris)
- [viteris @ victornils](https://www.victornils.net/tetris/)

- [terminal-tetris @ github](https://github.com/ContentsViewer/terminal-tetris)
- [terminal-tetris @ pypi](https://pypi.org/project/terminal-tetris/)
