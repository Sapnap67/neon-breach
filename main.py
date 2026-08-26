from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

from game_logic import Stats, UPGRADES, apply_upgrade, level_for_xp, upgrade_choices, xp_ceiling, xp_floor

W, H = 1280, 720
BG, CYAN, PINK, VIOLET = (4, 7, 18), (40, 235, 255), (255, 45, 143), (145, 80, 255)
WHITE, MUTED, RED = (235, 248, 255), (110, 142, 166), (255, 65, 80)
SAVE = Path(__file__).with_name("save.json")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_load():
    try:
        return json.loads(SAVE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"high_score": 0, "runs": 0}


def save_data(score):
    data = safe_load()
    data["high_score"] = max(int(score), int(data.get("high_score", 0)))
    data["runs"] = int(data.get("runs", 0)) + 1
    SAVE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclass
class Bullet:
    pos: pygame.Vector2
    vel: pygame.Vector2
    damage: float


@dataclass
class Enemy:
    pos: pygame.Vector2
    hp: float
    speed: float
    radius: int
    kind: str


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("NEON//BREACH")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.big = pygame.font.SysFont("consolas", 64, bold=True)
        self.small = pygame.font.SysFont("consolas", 16)
        self.state = "menu"
        self.high = safe_load().get("high_score", 0)
        self.reset()

    def reset(self):
        self.player = pygame.Vector2(W / 2, H / 2)
        self.stats, self.hp = Stats(), 100.0
        self.bullets, self.enemies, self.particles = [], [], []
        self.score = self.xp = 0
        self.level = 1
        self.time = self.shot_t = self.spawn_t = self.dash_t = 0.0
        self.flash = self.shake = 0.0
        self.choices = []

    def spawn_enemy(self):
        side = random.randrange(4)
        pos = [pygame.Vector2(random.randrange(W), -30), pygame.Vector2(W + 30, random.randrange(H)),
               pygame.Vector2(random.randrange(W), H + 30), pygame.Vector2(-30, random.randrange(H))][side]
        roll = random.random()
        if roll < min(.2, self.time / 150):
            kind, hp, speed, radius = "TANK", 85, 75, 25
        elif roll < .48:
            kind, hp, speed, radius = "DART", 22, 175, 12
        else:
            kind, hp, speed, radius = "HUNTER", 38, 110, 17
        scale = 1 + self.time / 170
        self.enemies.append(Enemy(pos, hp * scale, speed * min(1.55, scale), radius, kind))

    def burst(self, pos, color, n=10):
        for _ in range(n):
            a, s = random.random() * math.tau, random.uniform(60, 260)
            self.particles.append([pygame.Vector2(pos), pygame.Vector2(math.cos(a), math.sin(a)) * s, .45, color])

    def update(self, dt):
        if self.state != "playing": return
        self.time += dt; self.shot_t -= dt; self.spawn_t -= dt; self.dash_t -= dt
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        if move.length_squared(): move = move.normalize()
        self.player += move * self.stats.speed * dt
        self.player.x, self.player.y = clamp(self.player.x, 20, W - 20), clamp(self.player.y, 20, H - 20)
        if pygame.mouse.get_pressed()[0] and self.shot_t <= 0:
            aim = pygame.Vector2(pygame.mouse.get_pos()) - self.player
            if aim.length_squared():
                base = math.atan2(aim.y, aim.x)
                for i in range(self.stats.projectiles):
                    offset = (i - (self.stats.projectiles - 1) / 2) * .105
                    vel = pygame.Vector2(math.cos(base + offset), math.sin(base + offset)) * self.stats.bullet_speed
                    self.bullets.append(Bullet(self.player.copy(), vel, self.stats.damage))
                self.shot_t = self.stats.fire_delay
        if self.spawn_t <= 0:
            self.spawn_enemy(); self.spawn_t = max(.22, .82 - self.time * .006)
        for b in self.bullets: b.pos += b.vel * dt
        self.bullets = [b for b in self.bullets if -20 < b.pos.x < W + 20 and -20 < b.pos.y < H + 20]
        for e in self.enemies:
            delta = self.player - e.pos
            if delta.length_squared(): e.pos += delta.normalize() * e.speed * dt
            if delta.length() < e.radius + 14:
                self.hp -= 28 * dt; self.flash = .08; self.shake = 5
        for b in self.bullets[:]:
            hit = next((e for e in self.enemies if b.pos.distance_to(e.pos) < e.radius + 4), None)
            if hit:
                hit.hp -= b.damage
                if b in self.bullets: self.bullets.remove(b)
                self.burst(b.pos, CYAN, 3)
        for e in self.enemies[:]:
            if e.hp <= 0:
                self.enemies.remove(e); self.score += 10 if e.kind != "TANK" else 30
                self.xp += 18 if e.kind != "TANK" else 35; self.burst(e.pos, PINK, 14)
        new_level = level_for_xp(self.xp)
        if new_level > self.level:
            self.level = new_level; self.choices = upgrade_choices(); self.state = "upgrade"
        for p in self.particles:
            p[0] += p[1] * dt; p[1] *= .94; p[2] -= dt
        self.particles = [p for p in self.particles if p[2] > 0]
        self.flash = max(0, self.flash - dt); self.shake = max(0, self.shake - 20 * dt)
        if self.hp <= 0:
            save_data(self.score); self.high = max(self.high, self.score); self.state = "dead"

    def text(self, s, pos, color=WHITE, font=None, center=False):
        img = (font or self.font).render(str(s), True, color); rect = img.get_rect()
        rect.center = pos if center else rect.center; rect.topleft = pos if not center else rect.topleft
        self.screen.blit(img, rect)

    def draw_world(self):
        self.screen.fill(BG)
        for x in range(0, W, 64): pygame.draw.line(self.screen, (8, 23, 40), (x, 0), (x, H))
        for y in range(0, H, 64): pygame.draw.line(self.screen, (8, 23, 40), (0, y), (W, y))
        for p in self.particles: pygame.draw.circle(self.screen, p[3], p[0], max(1, int(4 * p[2] / .45)))
        for b in self.bullets:
            pygame.draw.line(self.screen, CYAN, b.pos - b.vel.normalize() * 13, b.pos, 4)
        for e in self.enemies:
            color = VIOLET if e.kind == "TANK" else PINK
            pygame.draw.circle(self.screen, color, e.pos, e.radius, 3)
            pygame.draw.circle(self.screen, color, e.pos, max(3, e.radius // 3))
        pygame.draw.circle(self.screen, CYAN, self.player, 14, 3)
        aim = pygame.Vector2(pygame.mouse.get_pos()) - self.player
        if aim.length_squared(): pygame.draw.line(self.screen, WHITE, self.player, self.player + aim.normalize() * 24, 3)
        pygame.draw.rect(self.screen, (20, 32, 50), (28, 26, 270, 16))
        pygame.draw.rect(self.screen, RED, (28, 26, 270 * max(0, self.hp) / self.stats.max_hp, 16))
        self.text(f"CORE {int(max(0,self.hp)):03d}/{self.stats.max_hp}", (28, 49), MUTED, self.small)
        self.text(f"SCORE {self.score:06d}", (W - 220, 24), WHITE)
        self.text(f"LEVEL {self.level:02d}", (W - 220, 52), CYAN)
        lo, hi = xp_floor(self.level), xp_ceiling(self.level)
        pygame.draw.rect(self.screen, (20, 32, 50), (28, H - 28, W - 56, 7))
        pygame.draw.rect(self.screen, CYAN, (28, H - 28, (W - 56) * (self.xp - lo) / max(1, hi - lo), 7))

    def draw(self):
        self.draw_world()
        if self.state == "menu":
            veil = pygame.Surface((W,H), pygame.SRCALPHA); veil.fill((0,0,0,165)); self.screen.blit(veil,(0,0))
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
            veil = pygame.Surface((W,H), pygame.SRCALPHA); veil.fill((2,5,15,220)); self.screen.blit(veil,(0,0))
            self.text("SELECT AN INJECTION", (W/2,145), CYAN, self.big, True)
            for i, name in enumerate(self.choices):
                rect = pygame.Rect(180 + i*320, 260, 280, 190)
                pygame.draw.rect(self.screen, (12,24,45), rect); pygame.draw.rect(self.screen, CYAN, rect, 2)
                self.text(str(i+1), (rect.centerx, rect.y+35), PINK, self.big, True)
                self.text(name, (rect.centerx, rect.y+105), WHITE, self.font, True)
                self.text(UPGRADES[name], (rect.centerx, rect.y+145), MUTED, self.small, True)
        if self.flash:
            f = pygame.Surface((W,H), pygame.SRCALPHA); f.fill((255,30,70,65)); self.screen.blit(f,(0,0))
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(self.clock.tick(144) / 1000, .033)
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and self.state == "menu": self.reset(); self.state = "playing"
                    elif event.key == pygame.K_ESCAPE and self.state in ("playing","paused"): self.state = "paused" if self.state == "playing" else "playing"
                    elif event.key == pygame.K_r and self.state == "dead": self.reset(); self.state = "playing"
                    elif self.state == "upgrade" and event.unicode in "123":
                        idx = int(event.unicode)-1
                        if idx < len(self.choices): self.stats, self.hp = apply_upgrade(self.stats, self.hp, self.choices[idx]); self.state = "playing"
                    elif event.key == pygame.K_SPACE and self.state == "playing" and self.dash_t <= 0:
                        keys = pygame.key.get_pressed(); move = pygame.Vector2(keys[pygame.K_d]-keys[pygame.K_a], keys[pygame.K_s]-keys[pygame.K_w])
                        if move.length_squared(): self.player += move.normalize()*125; self.dash_t = self.stats.dash_cooldown; self.burst(self.player, CYAN, 20)
            self.update(dt); self.draw()


if __name__ == "__main__":
    Game().run()
