"""Pure game rules that can be tested without opening a window."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Stats:
    max_hp: int = 100
    damage: float = 18.0
    speed: float = 290.0
    fire_delay: float = 0.22
    bullet_speed: float = 720.0
    projectiles: int = 1
    dash_cooldown: float = 1.8


UPGRADES = {
    "OVERCLOCK": "Fire 18% faster",
    "HEAVY ROUNDS": "+7 bullet damage",
    "VECTOR BOOTS": "+35 movement speed",
    "MULTI SHOT": "+1 projectile",
    "CORE PATCH": "+25 max HP and heal 25",
    "PHASE DRIVE": "Dash recharges 20% faster",
}


def apply_upgrade(stats: Stats, hp: float, name: str) -> tuple[Stats, float]:
    if name == "OVERCLOCK":
        stats.fire_delay = max(0.07, stats.fire_delay * 0.82)
    elif name == "HEAVY ROUNDS":
        stats.damage += 7
    elif name == "VECTOR BOOTS":
        stats.speed += 35
    elif name == "MULTI SHOT":
        stats.projectiles = min(5, stats.projectiles + 1)
    elif name == "CORE PATCH":
        stats.max_hp += 25
        hp = min(stats.max_hp, hp + 25)
    elif name == "PHASE DRIVE":
        stats.dash_cooldown = max(0.45, stats.dash_cooldown * 0.8)
    else:
        raise ValueError(f"Unknown upgrade: {name}")
    return stats, hp


def level_for_xp(xp: int) -> int:
    return 1 + int(math.sqrt(max(0, xp) / 60))


def xp_floor(level: int) -> int:
    return 60 * (max(1, level) - 1) ** 2


def xp_ceiling(level: int) -> int:
    return 60 * level**2


def upgrade_choices(rng: random.Random | None = None, count: int = 3) -> list[str]:
    rng = rng or random.Random()
    return rng.sample(list(UPGRADES), min(count, len(UPGRADES)))
