"""Hard-only walls, collision, food count and incremental acceleration."""
import importlib.util
from pathlib import Path
import random
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('hard_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class HardRulesTests(unittest.TestCase):
    def test_hard_leaving_any_edge_ends_run_without_wrapping(self):
        for direction, start in [('Right', (31, 8)), ('Left', (0, 8)),
                                 ('Up', (7, 0)), ('Down', (7, 31))]:
            with self.subTest(direction=direction):
                game = preview.MovementPreview(rng=random.Random(9), difficulty='Hard')
                game.snake[0] = start
                game.direction = direction
                game.foods = set()
                before = list(game.snake)
                game.step()
                self.assertTrue(game.game_over)
                self.assertEqual(game.game_over_reason, 'wall collision')
                self.assertEqual(game.snake, before)
                self.assertEqual(game.score, 0)
                game.step()
                self.assertEqual(game.snake, before)

    def test_hard_self_collision_is_fatal_below_the_old_ten_square_threshold(self):
        body = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                (12, 11), (13, 11), (13, 10), (14, 10)]
        for length in (5, 6, 9):
            with self.subTest(length=length):
                game = preview.MovementPreview(difficulty='Hard')
                game.snake = body[:length]
                game.foods = set()
                game.step()
                self.assertTrue(game.game_over)
                self.assertEqual(game.game_over_reason, 'self collision')
                self.assertEqual(game.snake, body[:length])

    def test_hard_keeps_ten_distinct_orange_dots_after_collection(self):
        game = preview.MovementPreview(rng=random.Random(13), difficulty='Hard')
        self.assertEqual(len(game.foods), 10)
        game.foods = {(8, 8)} | {(x, 20) for x in range(10, 19)}
        game.green_dot = (20, 21)
        game.step()
        self.assertEqual((game.score, len(game.snake)), (1, 7))
        self.assertEqual(len(game.foods), 10)
        self.assertTrue(game.foods.isdisjoint(game.snake))
        self.assertNotIn(game.green_dot, game.foods)
        self.assertTrue(all(0 <= x < 32 and 0 <= y < 32 for x, y in game.foods))

    def test_each_hard_orange_dot_reduces_step_time_by_2_point_3_milliseconds(self):
        game = preview.MovementPreview(rng=random.Random(23), difficulty='Hard')
        self.assertTrue(hasattr(game, 'step_interval_ms'), 'Per-dot speed increases are missing')
        self.assertEqual(game.step_interval_ms, 150)
        game.foods = {(8, 8), (9, 8)}
        game.step()
        self.assertEqual((game.score, game.step_interval_ms), (1, 147.7))
        game.step()
        self.assertEqual((game.score, game.step_interval_ms), (2, 145.4))
        game.foods = set()
        game.step()
        self.assertEqual((game.score, game.step_interval_ms), (2, 145.4))

    def test_hard_green_cooldown_uses_the_configured_step_duration_by_default(self):
        game = preview.MovementPreview(difficulty='Hard')
        game.score = 10
        game.foods = set()
        game.step()
        self.assertEqual(game.green_elapsed_ms, 127)
        game.step(elapsed_ms=42)
        self.assertEqual(game.green_elapsed_ms, 169)

    def test_green_dot_does_not_undo_acceleration_and_reset_restores_starting_speed(self):
        game = preview.MovementPreview(difficulty='Hard')
        game.score = 2
        game.foods = set()
        game.green_dot = (8, 8)
        game.step()
        self.assertEqual((game.score, len(game.snake), game.step_interval_ms), (2, 4, 145.4))
        game.reset()
        self.assertEqual((game.score, len(game.snake), game.step_interval_ms), (0, 6, 150))
        self.assertEqual(len(game.foods), 10)
        self.assertIsNone(game.game_over_reason)

    def test_acceleration_never_produces_a_zero_or_negative_step_delay(self):
        game = preview.MovementPreview(difficulty='Hard')
        for score, delay in [(60, 12), (64, 2.8), (65, 1), (1000000, 1)]:
            with self.subTest(score=score):
                game.score = score
                self.assertEqual(game.step_interval_ms, delay)
        game.reset()
        self.assertEqual(game.step_interval_ms, 150)

    def test_easy_and_normal_keep_five_dots_fixed_speed_wrapping_and_old_collision_threshold(self):
        body = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10), (12, 11)]
        for difficulty in ('Easy', 'Normal'):
            with self.subTest(difficulty=difficulty):
                game = preview.MovementPreview(difficulty=difficulty)
                self.assertEqual(len(game.foods), 5)
                game.foods = {(8, 8)}
                game.step()
                self.assertEqual((game.score, game.step_interval_ms), (1, 150))
                game.foods = set()
                game.snake = list(body)
                game.step()
                self.assertFalse(game.game_over)
                game.snake = [(game.grid_cells - 1, 8), (8, 8), (7, 8)]
                game.step()
                self.assertEqual(game.snake[0], (0, 8))
                self.assertFalse(game.game_over)

    def test_hard_can_still_enter_a_tail_cell_that_vacates_on_the_same_step(self):
        game = preview.MovementPreview(difficulty='Hard')
        game.foods = set()
        game.snake = [(10, 10), (10, 11), (11, 11), (11, 10)]
        game.step()
        self.assertFalse(game.game_over)
        self.assertEqual(game.snake[0], (11, 10))


if __name__ == '__main__':
    unittest.main()
