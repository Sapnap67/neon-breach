import random
import unittest

from game_logic import Stats, apply_upgrade, damage_after_resistance, level_for_xp, upgrade_choices, xp_ceiling, xp_floor


class GameLogicTests(unittest.TestCase):
    def test_level_boundaries(self):
        self.assertEqual(level_for_xp(0), 1)
        self.assertEqual(level_for_xp(59), 1)
        self.assertEqual(level_for_xp(60), 2)
        self.assertEqual(xp_floor(3), 240)
        self.assertEqual(xp_ceiling(3), 540)

    def test_upgrade_is_applied(self):
        stats, hp = apply_upgrade(Stats(), 50, "CORE PATCH")
        self.assertEqual(stats.max_hp, 125)
        self.assertEqual(hp, 75)

    def test_choices_are_unique(self):
        choices = upgrade_choices(random.Random(4))
        self.assertEqual(len(choices), len(set(choices)))
        self.assertEqual(len(choices), 3)

    def test_regeneration_upgrade_stacks(self):
        stats = Stats()
        stats, hp = apply_upgrade(stats, 50, "REGENERATION")
        stats, hp = apply_upgrade(stats, hp, "REGENERATION")
        self.assertEqual(stats.regen_per_tick, 4)
        self.assertEqual(hp, 50)

    def test_resistance_stacks_and_caps_at_sixty_percent(self):
        stats = Stats()
        for _ in range(8):
            stats, _ = apply_upgrade(stats, 100, "RESISTANCE")
        self.assertAlmostEqual(stats.resistance, 0.60)
        self.assertAlmostEqual(damage_after_resistance(20, stats.resistance), 8)


if __name__ == "__main__":
    unittest.main()
