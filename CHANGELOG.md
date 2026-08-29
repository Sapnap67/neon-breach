# Changelog

## 0.2.6 - 2026-08-29

- Expanded regular enemy spawns from one edge to the top, bottom and right edges.
- Kept the left edge as a limited retreat route and preserved right-side boss entrances.
- Added deterministic coverage for all three regular-enemy spawn edges.

## 0.2.5 - 2026-08-28

- Changed all regular enemy spawns to the right edge of the arena.
- Replaced timed boss encounters with level 10, 20, 30 and later ten-level milestones.
- Scaled later boss health, speed, bullet count, projectile speed, fire rate, damage and rewards.
- Updated boss warnings to show the triggering level.

## 0.2.4 - 2026-08-28

- Removed `RESISTANCE` from future upgrade choices after reaching the 60% cap.
- Added regression coverage for capped and uncapped resistance pools.

## 0.2.3 - 2026-08-28

- Added the stackable `RESISTANCE` upgrade.
- Each stack reduces incoming damage by 12%, capped at 60% damage reduction.
- Added the current resistance percentage to the live attributes panel.

## 0.2.2 - 2026-08-28

- Added a live `CORE ATTRIBUTES` panel in the upper-right corner.
- Displayed damage, movement speed, fire rate, projectile count, dash cooldown and regeneration.
- Made the panel update immediately after upgrades are applied.

## 0.2.1 - 2026-08-26

- Added the stackable `REGENERATION` upgrade.
- Regeneration heals 2 HP per stack every four seconds without exceeding maximum HP.
- Added a HUD status label and green healing particles when regeneration triggers.

## 0.2.0 - 2026-08-26

- Added a boss every 45 seconds with aimed spread-shot projectiles.
- Added kill combos and score multipliers.
- Added healing-core drops, damage invulnerability frames and player blinking.
- Added a dash cooldown meter and encounter messages.

## 0.1.4 - 2026-08-26

- Added Windows native physical-key polling when Pygame reports focus but misses keyboard input.
- Made the main-menu initialize control clickable.

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
