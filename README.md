# NEON//BREACH

A neon arena survival game built with Python and Pygame for a school creative-programming project.

## Play

On Windows, double-click `start.bat`. The first launch creates an isolated Python environment and installs Pygame.

- `WASD` or arrow keys: move (a quick tap always produces a visible step)
- Mouse: aim and hold left-click to fire
- `Space`: dash
- `Esc`: pause
- Upgrade choice: click a card, press `1` / `2` / `3`, or use arrows and Enter
- Defeat screen: press `R`, Enter, Space, or click the reboot button

## Development

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

See `用户手册.md` for the Chinese user guide and `CHANGELOG.md` for progress.

## Python file map

- `main.py`: window setup, game states, input, combat, collisions and drawing.
- `game_logic.py`: player stats, upgrades and level/experience formulas.
- `tests/test_game_logic.py`: automated checks for the pure rules above.
