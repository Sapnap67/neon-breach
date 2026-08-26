from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import pygame

from game_logic import Stats, UPGRADES, apply_upgrade, level_for_xp, upgrade_choices, xp_ceiling, xp_floor

# ---------- 全局设置：窗口、颜色和存档位置 ----------

W, H = 1280, 720
BG, CYAN, PINK, VIOLET = (4, 7, 18), (40, 235, 255), (255, 45, 143), (145, 80, 255)
WHITE, MUTED, RED = (235, 248, 255), (110, 142, 166), (255, 65, 80)
SAVE = Path(__file__).with_name("save.json")


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
        self.upgrade_cursor = 0
        self.high = safe_load().get("high_score", 0)
        self.reset()

    def reset(self):
        """把所有“本局数据”恢复到开局状态。"""

        self.player = pygame.Vector2(W / 2, H / 2)
        self.stats, self.hp = Stats(), 100.0
        self.bullets, self.enemies, self.particles = [], [], []
        self.score = self.xp = 0
        self.level = 1
        self.time = self.shot_t = self.spawn_t = self.dash_t = 0.0
        self.flash = self.shake = 0.0
        self.choices = []
        self.held_keys.clear()
        self.upgrade_cursor = 0

    def movement_vector(self):
        """根据当前按住的 WASD 或方向键计算移动方向。"""

        left = pygame.K_a in self.held_keys or pygame.K_LEFT in self.held_keys
        right = pygame.K_d in self.held_keys or pygame.K_RIGHT in self.held_keys
        up = pygame.K_w in self.held_keys or pygame.K_UP in self.held_keys
        down = pygame.K_s in self.held_keys or pygame.K_DOWN in self.held_keys
        move = pygame.Vector2(right - left, down - up)
        if move.length_squared():
            move = move.normalize()
        return move

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

    def spawn_enemy(self):
        """在屏幕四周随机生成一种敌人，并随生存时间增强它。"""

        # 0/1/2/3 分别代表上、右、下、左四条边。
        side = random.randrange(4)
        pos = [pygame.Vector2(random.randrange(W), -30), pygame.Vector2(W + 30, random.randrange(H)),
               pygame.Vector2(random.randrange(W), H + 30), pygame.Vector2(-30, random.randrange(H))][side]
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

        # ---------- 玩家移动 ----------
        move = self.movement_vector()
        self.player += move * self.stats.speed * dt
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
            if delta.length() < e.radius + 14:
                # 伤害乘以 dt，避免帧率越高受伤越快。
                self.hp -= 28 * dt
                self.flash = .08
                self.shake = 5

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
                self.score += 10 if e.kind != "TANK" else 30
                self.xp += 18 if e.kind != "TANK" else 35
                self.burst(e.pos, PINK, 14)

        # ---------- 升级、粒子和游戏结束 ----------
        new_level = level_for_xp(self.xp)
        if new_level > self.level:
            self.level = new_level
            self.choices = upgrade_choices()
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
        for e in self.enemies:
            color = VIOLET if e.kind == "TANK" else PINK
            pygame.draw.circle(self.screen, color, e.pos, e.radius, 3)
            pygame.draw.circle(self.screen, color, e.pos, max(3, e.radius // 3))
        pygame.draw.circle(self.screen, CYAN, self.player, 14, 3)
        aim = pygame.Vector2(pygame.mouse.get_pos()) - self.player
        if aim.length_squared():
            pygame.draw.line(self.screen, WHITE, self.player, self.player + aim.normalize() * 24, 3)

        # 左上角生命条、右上角分数等级、底部经验条。
        pygame.draw.rect(self.screen, (20, 32, 50), (28, 26, 270, 16))
        pygame.draw.rect(self.screen, RED, (28, 26, 270 * max(0, self.hp) / self.stats.max_hp, 16))
        self.text(f"CORE {int(max(0,self.hp)):03d}/{self.stats.max_hp}", (28, 49), MUTED, self.small)
        self.text(f"SCORE {self.score:06d}", (W - 220, 24), WHITE)
        self.text(f"LEVEL {self.level:02d}", (W - 220, 52), CYAN)
        lo, hi = xp_floor(self.level), xp_ceiling(self.level)
        pygame.draw.rect(self.screen, (20, 32, 50), (28, H - 28, W - 56, 7))
        pygame.draw.rect(self.screen, CYAN, (28, H - 28, (W - 56) * (self.xp - lo) / max(1, hi - lo), 7))

    def draw(self):
        """根据 self.state 在战场上覆盖对应的菜单界面。"""

        self.draw_world()
        if self.state == "menu":
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 165))
            self.screen.blit(veil, (0, 0))
            self.text("NEON//BREACH", (W/2,H/2-85), CYAN, self.big, True)
            self.text("SURVIVE THE SYSTEM COLLAPSE", (W/2,H/2-20), MUTED, self.font, True)
            self.text("[ ENTER ] INITIALIZE", (W/2,H/2+55), WHITE, self.font, True)
            self.text("WASD move  |  mouse aim/fire  |  SPACE dash  |  ESC pause", (W/2,H-70), MUTED, self.small, True)
            self.text(f"HIGH SCORE {self.high:06d}", (W/2,H/2+100), PINK, self.small, True)
        elif self.state == "paused":
            self.text("// PAUSED", (W/2,H/2), WHITE, self.big, True)
        elif self.state == "dead":
            self.text("SIGNAL LOST", (W/2,H/2-60), RED, self.big, True)
            self.text(f"SCORE {self.score:06d}   [R] REBOOT", (W/2,H/2+30), WHITE, self.font, True)
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
                    self.held_keys.add(event.key)
                    if event.key == pygame.K_RETURN and self.state == "menu":
                        self.reset()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE and self.state in ("playing", "paused"):
                        self.state = "paused" if self.state == "playing" else "playing"
                    elif event.key == pygame.K_r and self.state == "dead":
                        self.reset()
                        self.state = "playing"
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
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    # 只有直接运行 main.py 时才启动；被测试代码导入时不会自动弹出窗口。
    Game().run()
