"""不依赖游戏窗口的核心规则。

把升级和等级计算单独放在这里有两个好处：
1. ``main.py`` 不会塞满计算公式；
2. 自动测试不需要真的打开 Pygame 窗口。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Stats:
    """玩家所有可以被升级改变的属性。"""

    # 这些是每局游戏开始时的基础数值。
    max_hp: int = 100
    damage: float = 18.0
    speed: float = 290.0
    fire_delay: float = 0.22
    bullet_speed: float = 720.0
    projectiles: int = 1
    dash_cooldown: float = 1.8
    regen_per_tick: int = 0
    resistance: float = 0.0


# 字典的键是程序内部使用的升级名称，值是升级界面显示的说明。
UPGRADES = {
    "OVERCLOCK": "Fire 18% faster",
    "HEAVY ROUNDS": "+7 bullet damage",
    "VECTOR BOOTS": "+35 movement speed",
    "MULTI SHOT": "+1 projectile",
    "CORE PATCH": "+25 max HP and heal 25",
    "PHASE DRIVE": "Dash recharges 20% faster",
    "REGENERATION": "Heal +2 every 4 seconds (stacks)",
    "RESISTANCE": "Take 12% less damage (max 60%)",
}


def apply_upgrade(stats: Stats, hp: float, name: str) -> tuple[Stats, float]:
    """把玩家选中的强化应用到属性上，并返回属性和当前生命值。"""

    if name == "OVERCLOCK":
        stats.fire_delay = max(0.07, stats.fire_delay * 0.82)
    elif name == "HEAVY ROUNDS":
        stats.damage += 7
    elif name == "VECTOR BOOTS":
        stats.speed += 35
    elif name == "MULTI SHOT":
        stats.projectiles = min(5, stats.projectiles + 1)
    elif name == "CORE PATCH":
        # 上限增加以后同时治疗，但生命值不能超过新的上限。
        stats.max_hp += 25
        hp = min(stats.max_hp, hp + 25)
    elif name == "PHASE DRIVE":
        stats.dash_cooldown = max(0.45, stats.dash_cooldown * 0.8)
    elif name == "REGENERATION":
        # 每次选择都增加每轮回血量，所以技能可以无限叠加。
        stats.regen_per_tick += 2
    elif name == "RESISTANCE":
        # 抗性可以叠加，但限制在 60%，避免玩家完全免疫伤害。
        stats.resistance = min(0.60, stats.resistance + 0.12)
    else:
        raise ValueError(f"Unknown upgrade: {name}")
    return stats, hp


def level_for_xp(xp: int) -> int:
    """根据累计经验值计算当前等级。等级越高，升级所需经验越多。"""

    return 1 + int(math.sqrt(max(0, xp) / 60))


def damage_after_resistance(amount: float, resistance: float) -> float:
    """计算抗性减免后的实际伤害。"""

    resistance = max(0.0, min(0.60, resistance))
    return amount * (1 - resistance)


def xp_floor(level: int) -> int:
    """返回当前等级经验条的起点。"""

    return 60 * (max(1, level) - 1) ** 2


def xp_ceiling(level: int) -> int:
    """返回升到下一级所需的累计经验值。"""

    return 60 * level**2


def upgrade_choices(
    rng: random.Random | None = None,
    count: int = 3,
    stats: Stats | None = None,
) -> list[str]:
    """不重复地随机抽出有效升级；已经满级的抗性不会再次出现。"""

    rng = rng or random.Random()
    available = list(UPGRADES)
    if stats is not None and stats.resistance >= 0.60 - 1e-9:
        available.remove("RESISTANCE")
    return rng.sample(available, min(count, len(available)))
