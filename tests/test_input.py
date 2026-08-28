import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from main import Game


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.game.reset()

    def test_wasd_and_arrow_keys_produce_movement(self):
        self.game.held_keys.add(pygame.K_d)
        self.assertGreater(self.game.movement_vector().x, 0)
        self.game.held_keys = {pygame.K_UP}
        self.assertLess(self.game.movement_vector().y, 0)

    def test_quick_tap_moves_even_after_key_is_released(self):
        start_x = self.game.player.x
        self.game.note_movement_key(pygame.K_d)
        self.game.state = "playing"
        self.game.spawn_t = 999
        self.game.update(1 / 60)
        self.assertGreater(self.game.player.x, start_x)

    def test_upgrade_selection_returns_to_game(self):
        self.game.state = "upgrade"
        self.game.choices = ["HEAVY ROUNDS", "VECTOR BOOTS", "CORE PATCH"]
        old_damage = self.game.stats.damage
        self.game.choose_upgrade(0)
        self.assertEqual(self.game.state, "playing")
        self.assertGreater(self.game.stats.damage, old_damage)

    def test_restart_accepts_a_shared_restart_path(self):
        self.game.state = "dead"
        self.game.score = 999
        self.game.restart()
        self.assertEqual(self.game.state, "playing")
        self.assertEqual(self.game.score, 0)

    def test_boss_has_expected_combat_properties(self):
        self.game.spawn_boss()
        boss = self.game.enemies[-1]
        self.assertEqual(boss.kind, "BOSS")
        self.assertGreaterEqual(boss.hp, 650)
        self.assertEqual(boss.radius, 46)

    def test_regeneration_heals_on_four_second_tick(self):
        self.game.stats.regen_per_tick = 4
        self.game.hp = 50
        self.game.regen_t = 0.01
        self.game.state = "playing"
        self.game.spawn_t = 999
        self.game.update(0.02)
        self.assertEqual(self.game.hp, 54)
        self.assertGreater(self.game.regen_t, 3.9)

    def test_stats_panel_reflects_upgraded_values(self):
        self.game.stats.damage = 32
        self.game.stats.projectiles = 3
        self.game.stats.regen_per_tick = 6
        self.game.stats.resistance = .24
        rows = dict(self.game.stat_lines())
        self.assertEqual(rows["DAMAGE"], "32")
        self.assertEqual(rows["PROJECTILES"], "3")
        self.assertEqual(rows["REGEN"], "+6 / 4s")
        self.assertEqual(rows["RESISTANCE"], "24%")


if __name__ == "__main__":
    unittest.main()
