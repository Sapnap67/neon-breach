from __future__ import annotations

import json
import math
import random
import sys
import ctypes
from dataclasses import dataclass
from pathlib import Path

import pygame

from game_logic import (
    Stats,
    UPGRADES,
    apply_upgrade,
    damage_after_resistance,
    level_for_xp,
    upgrade_choices,
    xp_ceiling,
    xp_floor,
)

# ---------- 全局设置：窗口、颜色和存档位置 ----------

W, H = 1280, 720
BG, CYAN, PINK, VIOLET = (4, 7, 18), (40, 235, 255), (255, 45, 143), (145, 80, 255)
WHITE, MUTED, RED = (235, 248, 255), (110, 142, 166), (255, 65, 80)
SAVE = Path(__file__).with_name("save.json")

# Windows 虚拟键码。某些机器上 Pygame 窗口有焦点却读不到键盘，
# 所以 Windows 版会再直接查询一次物理按键状态。
WINDOWS_VK = {
    pygame.K_a: 0x41, pygame.K_d: 0x44, pygame.K_w: 0x57, pygame.K_s: 0x53,
    pygame.K_r: 0x52, pygame.K_LEFT: 0x25, pygame.K_UP: 0x26,
    pygame.K_RIGHT: 0x27, pygame.K_DOWN: 0x28, pygame.K_RETURN: 0x0D,
    pygame.K_SPACE: 0x20, pygame.K_1: 0x31, pygame.K_2: 0x32, pygame.K_3: 0x33,
    pygame.K_KP1: 0x61, pygame.K_KP2: 0x62, pygame.K_KP3: 0x63,
}


def physical_key_down(key):
    """读取物理按键；Windows 原生读取作为 Pygame 的备用方案。"""

    pressed = pygame.key.get_pressed()
    if pressed[key]:
        return True
    if sys.platform == "win32" and key in WINDOWS_VK:
        return bool(ctypes.windll.user32.GetAsyncKeyState(WINDOWS_VK[key]) & 0x8000)
    return False


def clamp(v, lo, hi):
    """把数值限制在 lo 到 hi 之间，用来防止玩家跑出屏幕。"""

    return max(lo, min(hi, v))


def safe_load():
    """读取存档；文件不存在或损坏时返回一份安全的默认数据。"""

    try:
        return json.loads(SAVE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"high_score": 0, "runs": 0}


def save_data(score):
    """一局结束时更新最高分和总游玩次数。"""

    data = safe_load()
    data["high_score"] = max(int(score), int(data.get("high_score", 0)))
    data["runs"] = int(data.get("runs", 0)) + 1
    SAVE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclass
class Bullet:
    """一颗子弹的数据：位置、速度向量和伤害。"""

    pos: pygame.Vector2
    vel: pygame.Vector2
    damage: float


@dataclass
class Enemy:
    """一个敌人的数据；不同 kind 会使用不同的数值和外观。"""

    pos: pygame.Vector2
    hp: float
    speed: float
    radius: int
    kind: str
    shoot_t: float = 0.0
    power: int = 1


@dataclass
class EnemyBullet:
    """Boss 发射的敌方子弹。"""

    pos: pygame.Vector2
    vel: pygame.Vector2


@dataclass
class Pickup:
    """敌人偶尔掉落的治疗核心。"""

    pos: pygame.Vector2
    life: float = 8.0


class Game:
    """游戏主体：负责初始化、更新、绘制和处理键盘鼠标事件。"""

    def __init__(self):
        # Pygame 初始化只执行一次；reset() 可以在重新开始时重复调用。
        pygame.init()
        pygame.display.set_caption("NEON//BREACH")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.big = pygame.font.SysFont("consolas", 64, bold=True)
        self.small = pygame.font.SysFont("consolas", 16)
        self.state = "menu"
        # 自己记录持续按住的键，比每帧查询键盘状态更稳定。
        self.held_keys: set[int] = set()
        self.move_tap = pygame.Vector2()
        self.upgrade_cursor = 0
        self.action_latched = False
        self.high = safe_load().get("high_score", 0)
        self.reset()

    def reset(self):
        """把所有“本局数据”恢复到开局状态。"""

        self.player = pygame.Vector2(W / 2, H / 2)
        self.stats, self.hp = Stats(), 100.0
        self.bullets, self.enemy_bullets = [], []
        self.enemies, self.particles, self.pickups = [], [], []
        self.score = self.xp = 0
        self.level = 1
        self.time = self.shot_t = self.spawn_t = self.dash_t = 0.0
        self.invulnerable_t = 0.0
        self.regen_t = 4.0
        self.combo = 0
        self.combo_t = 0.0
        self.next_boss_level = 10
        self.wave_message_t = 2.0
        self.wave_message = "BREACH INITIALIZED"
        self.flash = self.shake = 0.0
        self.choices = []
        self.held_keys.clear()
        self.move_tap.update(0, 0)
        self.upgrade_cursor = 0
        self.action_latched = False

    def movement_vector(self):
        """根据当前按住的 WASD 或方向键计算移动方向。"""

        # 同时使用事件记录和实时键盘状态，两种输入方式互相兜底。
        left = pygame.K_a in self.held_keys or pygame.K_LEFT in self.held_keys or physical_key_down(pygame.K_a) or physical_key_down(pygame.K_LEFT)
        right = pygame.K_d in self.held_keys or pygame.K_RIGHT in self.held_keys or physical_key_down(pygame.K_d) or physical_key_down(pygame.K_RIGHT)
        up = pygame.K_w in self.held_keys or pygame.K_UP in self.held_keys or physical_key_down(pygame.K_w) or physical_key_down(pygame.K_UP)
        down = pygame.K_s in self.held_keys or pygame.K_DOWN in self.held_keys or physical_key_down(pygame.K_s) or physical_key_down(pygame.K_DOWN)
        move = pygame.Vector2(right - left, down - up)
        if move.length_squared():
            move = move.normalize()
        return move

    def note_movement_key(self, key):
        """记录一次移动键按下，让很短的轻点也至少移动一小步。"""

        directions = {
            pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
            pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
            pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
            pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
        }
        if key in directions:
            self.move_tap += pygame.Vector2(directions[key])

    def restart(self):
        """从死亡界面开始新的一局。"""

        self.reset()
        self.state = "playing"

    def poll_state_controls(self):
        """实时轮询菜单按键，防止某些电脑漏掉 KEYDOWN 事件。"""

        confirm = physical_key_down(pygame.K_RETURN) or physical_key_down(pygame.K_SPACE)
        restart = physical_key_down(pygame.K_r) or confirm
        number = None
        for index, keys in enumerate(((pygame.K_1, pygame.K_KP1), (pygame.K_2, pygame.K_KP2), (pygame.K_3, pygame.K_KP3))):
            if any(physical_key_down(key) for key in keys):
                number = index
                break

        action_down = bool(confirm or restart or number is not None)
        if action_down and not self.action_latched:
            if self.state == "menu" and confirm:
                self.reset()
                self.state = "playing"
            elif self.state == "dead" and restart:
                self.restart()
            elif self.state == "upgrade" and number is not None:
                self.choose_upgrade(number)
        self.action_latched = action_down

    @staticmethod
    def restart_rect():
        """死亡界面的可点击重启按钮。"""

        return pygame.Rect(W // 2 - 170, H // 2 + 5, 340, 70)

    @staticmethod
    def start_rect():
        """主菜单可点击的开始区域。"""

        return pygame.Rect(W // 2 - 180, H // 2 + 20, 360, 70)

    def upgrade_rects(self):
        """返回三张升级卡片的位置，绘制和鼠标点击共用同一套坐标。"""

        return [pygame.Rect(180 + i * 320, 260, 280, 190) for i in range(len(self.choices))]

    def choose_upgrade(self, index):
        """选择升级并返回战斗；无效编号直接忽略。"""

        if self.state != "upgrade" or not 0 <= index < len(self.choices):
            return
        self.stats, self.hp = apply_upgrade(self.stats, self.hp, self.choices[index])
        self.state = "playing"
        self.held_keys.clear()
        self.move_tap.update(0, 0)

    def spawn_enemy(self):
        """从屏幕右侧生成一种敌人，并随生存时间增强它。"""

        # 固定从右边进入，让玩家能形成明确的防线和走位方向。
        pos = pygame.Vector2(W + 30, random.randrange(35, H - 35))
        # roll 决定敌人类型；游戏前期不会出现 TANK，之后概率逐渐增加。
        roll = random.random()
        if roll < min(.2, self.time / 150):
            kind, hp, speed, radius = "TANK", 85, 75, 25
        elif roll < .48:
            kind, hp, speed, radius = "DART", 22, 175, 12
        else:
            kind, hp, speed, radius = "HUNTER", 38, 110, 17
        # 生存越久，敌人生命和速度越高，形成自然的难度曲线。
        scale = 1 + self.time / 170
        self.enemies.append(Enemy(pos, hp * scale, speed * min(1.55, scale), radius, kind))

    def spawn_boss(self, boss_level=None):
        """从右侧生成关卡 Boss；10、20、30……级时出现。"""

        boss_level = boss_level or self.level
        tier = max(1, boss_level // 10)
        hp = 700 * (1 + .45 * (tier - 1))
        speed = 65 + 6 * (tier - 1)
        radius = 46 + min(10, 2 * (tier - 1))
        self.enemies.append(Enemy(pygame.Vector2(W + 65, H / 2), hp, speed, radius, "BOSS", .8, tier))
        self.wave_message_t = 3.0
        self.wave_message = f"WARNING // LEVEL {boss_level} BOSS"

    def burst(self, pos, color, n=10):
        """在指定位置产生一圈向外飞散的粒子。"""

        for _ in range(n):
            a, s = random.random() * math.tau, random.uniform(60, 260)
            self.particles.append([pygame.Vector2(pos), pygame.Vector2(math.cos(a), math.sin(a)) * s, .45, color])

    def update(self, dt):
        """推进一帧游戏逻辑。

        dt 是上一帧到这一帧经过的秒数。所有移动都乘以 dt，才能让游戏
        在不同性能的电脑上保持相同速度。
        """

        if self.state != "playing":
            return

        # 所有冷却计时器每帧递减；小于等于 0 就表示可以再次触发。
        self.time += dt
        self.shot_t -= dt
        self.spawn_t -= dt
        self.dash_t -= dt
        self.invulnerable_t -= dt
        self.regen_t -= dt
        self.combo_t -= dt
        self.wave_message_t -= dt
        if self.combo_t <= 0:
            self.combo = 0

        # REGENERATION 每四秒结算一次；层数越高，每次恢复越多。
        if self.regen_t <= 0:
            if self.stats.regen_per_tick > 0 and self.hp < self.stats.max_hp:
                old_hp = self.hp
                self.hp = min(self.stats.max_hp, self.hp + self.stats.regen_per_tick)
                if self.hp > old_hp:
                    self.burst(self.player, (80, 255, 130), 12)
            self.regen_t += 4.0

        # ---------- 玩家移动 ----------
        move = self.movement_vector()
        self.player += move * self.stats.speed * dt
        if self.move_tap.length_squared():
            # 即使 KEYDOWN 和 KEYUP 落在同一帧，轻点也会移动 24 像素。
            self.player += self.move_tap.normalize() * 24
            self.move_tap.update(0, 0)
        self.player.x, self.player.y = clamp(self.player.x, 20, W - 20), clamp(self.player.y, 20, H - 20)

        # ---------- 瞄准和射击 ----------
        if pygame.mouse.get_pressed()[0] and self.shot_t <= 0:
            aim = pygame.Vector2(pygame.mouse.get_pos()) - self.player
            if aim.length_squared():
                base = math.atan2(aim.y, aim.x)
                for i in range(self.stats.projectiles):
                    # 多发子弹以鼠标方向为中心，向两侧均匀散开。
                    offset = (i - (self.stats.projectiles - 1) / 2) * .105
                    vel = pygame.Vector2(math.cos(base + offset), math.sin(base + offset)) * self.stats.bullet_speed
                    self.bullets.append(Bullet(self.player.copy(), vel, self.stats.damage))
                self.shot_t = self.stats.fire_delay

        # ---------- 敌人生成与追踪 ----------
        if self.spawn_t <= 0:
            self.spawn_enemy()
            # 随生存时间缩短生成间隔，但最低保留 0.22 秒。
            self.spawn_t = max(.22, .82 - self.time * .006)
        for b in self.bullets:
            b.pos += b.vel * dt
        self.bullets = [b for b in self.bullets if -20 < b.pos.x < W + 20 and -20 < b.pos.y < H + 20]
        for e in self.enemies:
            delta = self.player - e.pos
            if delta.length_squared():
                e.pos += delta.normalize() * e.speed * dt
            if e.kind == "BOSS":
                e.shoot_t -= dt
                if e.shoot_t <= 0 and delta.length_squared():
                    # Boss 阶数越高，弹幕越密、弹速越快、射击间隔越短。
                    base = math.atan2(delta.y, delta.x)
                    shot_count = min(11, 3 + 2 * e.power)
                    offsets = [(i - (shot_count - 1) / 2) * .14 for i in range(shot_count)]
                    for offset in offsets:
                        bullet_speed = 260 + 25 * (e.power - 1)
                        vel = pygame.Vector2(math.cos(base + offset), math.sin(base + offset)) * bullet_speed
                        self.enemy_bullets.append(EnemyBullet(e.pos.copy(), vel))
                    e.shoot_t = max(.55, 1.25 - .1 * (e.power - 1))
            if delta.length() < e.radius + 14 and self.invulnerable_t <= 0:
                # 伤害乘以 dt，避免帧率越高受伤越快。
                raw_damage = 16 + 2 * (e.power - 1) if e.kind == "BOSS" else 10
                self.hp -= damage_after_resistance(raw_damage, self.stats.resistance)
                self.invulnerable_t = .65
                self.flash = .12
                self.shake = 7

        # 敌方子弹命中后消失，并触发短暂无敌帧。
        for bullet in self.enemy_bullets:
            bullet.pos += bullet.vel * dt
        self.enemy_bullets = [b for b in self.enemy_bullets if -30 < b.pos.x < W + 30 and -30 < b.pos.y < H + 30]
        for bullet in self.enemy_bullets[:]:
            if bullet.pos.distance_to(self.player) < 19 and self.invulnerable_t <= 0:
                self.enemy_bullets.remove(bullet)
                boss_power = max((e.power for e in self.enemies if e.kind == "BOSS"), default=1)
                self.hp -= damage_after_resistance(14 + 2 * (boss_power - 1), self.stats.resistance)
                self.invulnerable_t = .65
                self.flash = .12

        # ---------- 子弹与敌人的碰撞 ----------
        # 使用副本 [:] 遍历，因为命中时会从原列表删除子弹。
        for b in self.bullets[:]:
            hit = next((e for e in self.enemies if b.pos.distance_to(e.pos) < e.radius + 4), None)
            if hit:
                hit.hp -= b.damage
                if b in self.bullets:
                    self.bullets.remove(b)
                self.burst(b.pos, CYAN, 3)
        for e in self.enemies[:]:
            if e.hp <= 0:
                self.enemies.remove(e)
                self.combo += 1
                self.combo_t = 2.6
                base_score = 250 * e.power if e.kind == "BOSS" else (30 if e.kind == "TANK" else 10)
                self.score += int(base_score * (1 + min(20, self.combo) * .05))
                self.xp += 150 * e.power if e.kind == "BOSS" else (35 if e.kind == "TANK" else 18)
                if random.random() < (.55 if e.kind == "BOSS" else .06):
                    self.pickups.append(Pickup(e.pos.copy()))
                self.burst(e.pos, PINK, 14)

        # 治疗核心会在八秒后消失，接触即可恢复 20 点生命。
        for pickup in self.pickups:
            pickup.life -= dt
            if pickup.pos.distance_to(self.player) < 25:
                self.hp = min(self.stats.max_hp, self.hp + 20)
                pickup.life = 0
                self.burst(pickup.pos, (80, 255, 130), 18)
        self.pickups = [p for p in self.pickups if p.life > 0]

        # ---------- 升级、粒子和游戏结束 ----------
        new_level = level_for_xp(self.xp)
        if new_level > self.level:
            self.level = new_level
            if new_level >= self.next_boss_level:
                self.spawn_boss(self.next_boss_level)
                self.next_boss_level = (new_level // 10 + 1) * 10
            self.choices = upgrade_choices(stats=self.stats)
            self.state = "upgrade"
        for p in self.particles:
            p[0] += p[1] * dt
            p[1] *= .94
            p[2] -= dt
        self.particles = [p for p in self.particles if p[2] > 0]
        self.flash = max(0, self.flash - dt)
        self.shake = max(0, self.shake - 20 * dt)
        if self.hp <= 0:
            save_data(self.score)
            self.high = max(self.high, self.score)
            self.state = "dead"

    def text(self, s, pos, color=WHITE, font=None, center=False):
        """统一绘制文字；center=True 时 pos 表示文字中心，否则表示左上角。"""

        img = (font or self.font).render(str(s), True, color)
        rect = img.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(img, rect)

    def stat_lines(self):
        """返回右上角属性面板的文字；属性变化后会自动反映在这里。"""

        fire_rate = 1 / self.stats.fire_delay
        return [
            ("DAMAGE", f"{self.stats.damage:.0f}"),
            ("MOVE SPEED", f"{self.stats.speed:.0f}"),
            ("FIRE RATE", f"{fire_rate:.1f}/s"),
            ("PROJECTILES", str(self.stats.projectiles)),
            ("DASH COOLDOWN", f"{self.stats.dash_cooldown:.2f}s"),
            ("REGEN", f"+{self.stats.regen_per_tick} / 4s"),
            ("RESISTANCE", f"{self.stats.resistance:.0%}"),
        ]

    def draw_stats_panel(self):
        """绘制右上角的实时玩家属性面板。"""

        panel = pygame.Rect(W - 286, 92, 258, 213)
        pygame.draw.rect(self.screen, (7, 16, 30), panel)
        pygame.draw.rect(self.screen, (24, 66, 82), panel, 2)
        self.text("// CORE ATTRIBUTES", (panel.x + 14, panel.y + 12), CYAN, self.small)
        for row, (label, value) in enumerate(self.stat_lines()):
            y = panel.y + 42 + row * 23
            self.text(label, (panel.x + 14, y), MUTED, self.small)
            special = label in ("REGEN", "RESISTANCE")
            value_image = self.small.render(value, True, (80, 255, 130) if special else WHITE)
            self.screen.blit(value_image, (panel.right - 14 - value_image.get_width(), y))

    def draw_world(self):
        """绘制战场、实体和 HUD，不处理菜单等覆盖层。"""

        self.screen.fill(BG)
        # 背景网格只负责视觉效果，不参与碰撞。
        for x in range(0, W, 64):
            pygame.draw.line(self.screen, (8, 23, 40), (x, 0), (x, H))
        for y in range(0, H, 64):
            pygame.draw.line(self.screen, (8, 23, 40), (0, y), (W, y))
        for p in self.particles:
            pygame.draw.circle(self.screen, p[3], p[0], max(1, int(4 * p[2] / .45)))
        for b in self.bullets:
            pygame.draw.line(self.screen, CYAN, b.pos - b.vel.normalize() * 13, b.pos, 4)
        for b in self.enemy_bullets:
            pygame.draw.circle(self.screen, RED, b.pos, 7)
            pygame.draw.circle(self.screen, WHITE, b.pos, 3)
        for pickup in self.pickups:
            pulse = 8 + int(math.sin(self.time * 8) * 2)
            pygame.draw.circle(self.screen, (80, 255, 130), pickup.pos, pulse, 3)
            pygame.draw.line(self.screen, (80, 255, 130), pickup.pos + (-4, 0), pickup.pos + (4, 0), 2)
            pygame.draw.line(self.screen, (80, 255, 130), pickup.pos + (0, -4), pickup.pos + (0, 4), 2)
        for e in self.enemies:
            color = RED if e.kind == "BOSS" else (VIOLET if e.kind == "TANK" else PINK)
            pygame.draw.circle(self.screen, color, e.pos, e.radius, 3)
            pygame.draw.circle(self.screen, color, e.pos, max(3, e.radius // 3))
        player_color = WHITE if self.invulnerable_t > 0 and int(self.time * 18) % 2 else CYAN
        pygame.draw.circle(self.screen, player_color, self.player, 14, 3)
        aim = pygame.Vector2(pygame.mouse.get_pos()) - self.player
        if aim.length_squared():
            pygame.draw.line(self.screen, WHITE, self.player, self.player + aim.normalize() * 24, 3)

        # 左上角生命条、右上角分数等级、底部经验条。
        pygame.draw.rect(self.screen, (20, 32, 50), (28, 26, 270, 16))
        pygame.draw.rect(self.screen, RED, (28, 26, 270 * max(0, self.hp) / self.stats.max_hp, 16))
        self.text(f"CORE {int(max(0,self.hp)):03d}/{self.stats.max_hp}", (28, 49), MUTED, self.small)
        self.text(f"SCORE {self.score:06d}", (W - 220, 24), WHITE)
        self.text(f"LEVEL {self.level:02d}", (W - 220, 52), CYAN)
        if self.combo > 1:
            self.text(f"COMBO x{self.combo}", (W - 440, 52), PINK)
        self.draw_stats_panel()
        dash_ready = clamp(1 - max(0, self.dash_t) / self.stats.dash_cooldown, 0, 1)
        pygame.draw.rect(self.screen, (20, 32, 50), (28, 76, 150, 7))
        pygame.draw.rect(self.screen, CYAN, (28, 76, 150 * dash_ready, 7))
        self.text("DASH", (184, 69), MUTED, self.small)
        lo, hi = xp_floor(self.level), xp_ceiling(self.level)
        pygame.draw.rect(self.screen, (20, 32, 50), (28, H - 28, W - 56, 7))
        pygame.draw.rect(self.screen, CYAN, (28, H - 28, (W - 56) * (self.xp - lo) / max(1, hi - lo), 7))
        if self.wave_message_t > 0:
            self.text(self.wave_message, (W/2, 95), RED if "BOSS" in self.wave_message else CYAN, self.font, True)

    def draw(self):
        """根据 self.state 在战场上覆盖对应的菜单界面。"""

        self.draw_world()
        if self.state == "menu":
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 165))
            self.screen.blit(veil, (0, 0))
            self.text("NEON//BREACH", (W/2,H/2-85), CYAN, self.big, True)
            self.text("SURVIVE THE SYSTEM COLLAPSE", (W/2,H/2-20), MUTED, self.font, True)
            start_button = self.start_rect()
            hovered = start_button.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (20, 40, 62) if hovered else (10, 20, 36), start_button)
            pygame.draw.rect(self.screen, PINK if hovered else CYAN, start_button, 3)
            self.text("[ ENTER / CLICK ] INITIALIZE", start_button.center, WHITE, self.font, True)
            self.text("WASD move  |  mouse aim/fire  |  SPACE dash  |  ESC pause", (W/2,H-70), MUTED, self.small, True)
            self.text(f"HIGH SCORE {self.high:06d}", (W/2,H/2+100), PINK, self.small, True)
        elif self.state == "paused":
            self.text("// PAUSED", (W/2,H/2), WHITE, self.big, True)
        elif self.state == "dead":
            self.text("SIGNAL LOST", (W/2,H/2-60), RED, self.big, True)
            button = self.restart_rect()
            hovered = button.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (28, 48, 70) if hovered else (12, 24, 45), button)
            pygame.draw.rect(self.screen, PINK if hovered else CYAN, button, 3)
            self.text(f"SCORE {self.score:06d}  //  REBOOT", button.center, WHITE, self.font, True)
            self.text("R / ENTER / SPACE / CLICK", (W/2, button.bottom+28), MUTED, self.small, True)
        elif self.state == "upgrade":
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((2, 5, 15, 220))
            self.screen.blit(veil, (0, 0))
            self.text("SELECT AN INJECTION", (W/2,145), CYAN, self.big, True)
            mouse_pos = pygame.mouse.get_pos()
            for i, (name, rect) in enumerate(zip(self.choices, self.upgrade_rects())):
                hovered = rect.collidepoint(mouse_pos)
                selected = i == self.upgrade_cursor
                fill = (20, 40, 68) if hovered or selected else (12, 24, 45)
                border = PINK if hovered else CYAN
                pygame.draw.rect(self.screen, fill, rect)
                pygame.draw.rect(self.screen, border, rect, 4 if hovered or selected else 2)
                self.text(str(i+1), (rect.centerx, rect.y+35), PINK, self.big, True)
                self.text(name, (rect.centerx, rect.y+105), WHITE, self.font, True)
                self.text(UPGRADES[name], (rect.centerx, rect.y+145), MUTED, self.small, True)
            self.text("CLICK A CARD  |  1 2 3  |  LEFT/RIGHT + ENTER", (W/2, 500), MUTED, self.small, True)
        if self.flash:
            f = pygame.Surface((W, H), pygame.SRCALPHA)
            f.fill((255, 30, 70, 65))
            self.screen.blit(f, (0, 0))

        if not pygame.key.get_focused():
            focus_box = pygame.Rect(W // 2 - 190, H - 72, 380, 42)
            pygame.draw.rect(self.screen, (40, 12, 28), focus_box)
            pygame.draw.rect(self.screen, PINK, focus_box, 2)
            self.text("CLICK THE GAME WINDOW TO ENABLE KEYS", focus_box.center, WHITE, self.small, True)

        # 所有东西画完后，一次性把这一帧显示到窗口。
        pygame.display.flip()

    def run(self):
        """主循环：读取输入 -> 更新游戏 -> 绘制画面，直到玩家关闭窗口。"""

        while True:
            # 限制最高 144 FPS，并避免窗口卡顿后 dt 突然过大。
            dt = min(self.clock.tick(144) / 1000, .033)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                if event.type == pygame.KEYUP:
                    self.held_keys.discard(event.key)
                if event.type == pygame.KEYDOWN:
                    was_held = event.key in self.held_keys
                    self.held_keys.add(event.key)
                    if not was_held:
                        self.note_movement_key(event.key)
                    if event.key == pygame.K_RETURN and self.state == "menu":
                        self.reset()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE and self.state in ("playing", "paused"):
                        self.state = "paused" if self.state == "playing" else "playing"
                    elif self.state == "dead" and event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                        self.restart()
                    elif self.state == "upgrade" and event.key in (
                        pygame.K_1, pygame.K_2, pygame.K_3,
                        pygame.K_KP1, pygame.K_KP2, pygame.K_KP3,
                    ):
                        number_keys = {
                            pygame.K_1: 0, pygame.K_KP1: 0,
                            pygame.K_2: 1, pygame.K_KP2: 1,
                            pygame.K_3: 2, pygame.K_KP3: 2,
                        }
                        self.choose_upgrade(number_keys[event.key])
                    elif self.state == "upgrade" and event.key in (pygame.K_LEFT, pygame.K_a):
                        self.upgrade_cursor = (self.upgrade_cursor - 1) % len(self.choices)
                    elif self.state == "upgrade" and event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.upgrade_cursor = (self.upgrade_cursor + 1) % len(self.choices)
                    elif self.state == "upgrade" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.choose_upgrade(self.upgrade_cursor)
                    elif event.key == pygame.K_SPACE and self.state == "playing" and self.dash_t <= 0:
                        move = self.movement_vector()
                        if move.length_squared():
                            self.player += move.normalize() * 125
                            self.dash_t = self.stats.dash_cooldown
                            self.burst(self.player, CYAN, 20)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "upgrade":
                    for index, rect in enumerate(self.upgrade_rects()):
                        if rect.collidepoint(event.pos):
                            self.choose_upgrade(index)
                            break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "dead":
                    if self.restart_rect().collidepoint(event.pos):
                        self.restart()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "menu":
                    if self.start_rect().collidepoint(event.pos):
                        self.reset()
                        self.state = "playing"
            # 菜单操作额外使用实时轮询，避免系统漏发单次按键事件。
            self.poll_state_controls()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    # 只有直接运行 main.py 时才启动；被测试代码导入时不会自动弹出窗口。
    Game().run()
