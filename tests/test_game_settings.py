"""Tests for the approved spawn rates and difficulty presets."""
import importlib.util
from pathlib import Path
import random
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('settings_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class GameSettingsTests(unittest.TestCase):
    def test_five_orange_dots_are_distinct_and_replaced_after_collection(self):
        game = preview.MovementPreview(rng=random.Random(123))
        self.assertTrue(hasattr(game, 'foods'), 'Multiple orange dots are not implemented')
        self.assertEqual(len(game.foods), 5)
        self.assertTrue(game.foods.isdisjoint(game.snake))
        game.foods = {(8, 8), (20, 20), (21, 20), (22, 20), (23, 20)}
        game.step()
        self.assertEqual((game.score, len(game.snake)), (1, 7))
        self.assertEqual(len(game.foods), 5)
        self.assertNotIn((8, 8), game.foods)
        self.assertTrue(game.foods.isdisjoint(game.snake))

    def test_green_dot_waits_thirty_seconds_and_never_stacks(self):
        game = preview.MovementPreview(rng=random.Random(8))
        self.assertTrue(hasattr(game, 'green_elapsed_ms'), 'Thirty-second scheduling is not implemented')
        game.foods = set()
        game.step(elapsed_ms=29999)
        self.assertIsNone(game.green_dot)
        game.step(elapsed_ms=1)
        self.assertIsNotNone(game.green_dot)
        first = game.green_dot
        game.step(elapsed_ms=60000)
        self.assertEqual(game.green_dot, first)
        game.snake = [(20 - index, 8) for index in range(10)]
        game.green_dot = (21, 8)
        game.step()
        self.assertEqual(len(game.snake), 8)
        self.assertIsNone(game.green_dot)
        self.assertEqual(game.green_elapsed_ms, 0)
        game.step(elapsed_ms=29999)
        self.assertIsNone(game.green_dot)
        game.step(elapsed_ms=1)
        self.assertIsNotNone(game.green_dot)

    def test_difficulty_changes_board_size_not_cell_size_and_resets_the_run(self):
        game = preview.MovementPreview(rng=random.Random(11))
        self.assertTrue(hasattr(game, 'grid_cells'), 'Difficulty board sizes are not implemented')
        for difficulty, cells, pixels in [('Easy', 64, 1024), ('Normal', 48, 768), ('Hard', 32, 512)]:
            with self.subTest(difficulty=difficulty):
                game.score = 99
                game.reset(difficulty)
                self.assertEqual((game.difficulty, game.grid_cells, game.board_pixels),
                                 (difficulty, cells, pixels))
                self.assertEqual(preview.CELL_PIXELS, 16)
                self.assertEqual((game.score, len(game.snake), len(game.foods)),
                                 (0, 6, 10 if difficulty == 'Hard' else 5))
                self.assertTrue(all(0 <= x < cells and 0 <= y < cells for x, y in game.foods))
                game.snake = [(cells - 1, 8), (cells - 2, 8), (cells - 3, 8)]
                game.foods = set()
                game.step()
                self.assertEqual(game.snake[0], (cells - 1, 8) if difficulty == 'Hard' else (0, 8))
                self.assertEqual(game.game_over, difficulty == 'Hard')
        with self.assertRaises(ValueError):
            game.reset('Unknown')
        self.assertEqual(game.difficulty, 'Hard')


if __name__ == '__main__':
    unittest.main()
