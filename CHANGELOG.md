# Changelog

## 0.1.3 - 2026-08-26

- Added a minimum movement step for very short key taps.
- Added Enter, Space and a clickable button as defeat-screen restart controls.
- Added real-time keyboard polling as a fallback for missed key events.
- Added an on-screen warning when the game window does not have keyboard focus.
- Added regression tests for tap movement and restarting.

## 0.1.2 - 2026-08-26

- Fixed unreliable movement input by tracking held key-down/key-up events.
- Added arrow-key movement alongside WASD.
- Added mouse, number row, numpad and keyboard navigation to the upgrade screen.
- Added hover/selection feedback and clearer upgrade instructions.

## 0.1.1 - 2026-08-26

- Added Chinese section comments and function explanations throughout the main Python files.
- Expanded the Chinese manual with a map of the code structure.
- Reformatted dense statements to make the game loop easier to read without changing gameplay.

## 0.1.0 - 2026-08-26

- Added the first playable arena-survival loop.
- Added movement, mouse aiming, shooting, dash, enemy waves, collisions and scoring.
- Added six randomized upgrades and level progression.
- Added menu, pause, defeat/restart flow and local high-score saving.
- Added neon grid visuals, particles, hit flash and three enemy types.
- Added Windows launcher, README, Chinese user manual and rule tests.
