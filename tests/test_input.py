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

    def test_upgrade_selection_returns_to_game(self):
        self.game.state = "upgrade"
        self.game.choices = ["HEAVY ROUNDS", "VECTOR BOOTS", "CORE PATCH"]
        old_damage = self.game.stats.damage
        self.game.choose_upgrade(0)
        self.assertEqual(self.game.state, "playing")
        self.assertGreater(self.game.stats.damage, old_damage)


if __name__ == "__main__":
    unittest.main()
