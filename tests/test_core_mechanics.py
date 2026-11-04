"""Core collection, tail appearance, green-dot and collision rules."""
import importlib.util
from pathlib import Path
import random
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('mechanics_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class CoreMechanicsTests(unittest.TestCase):
    def test_normal_dot_adds_one_point_one_segment_and_respawns_off_the_body(self):
        motion = preview.MovementPreview()
        self.assertTrue(hasattr(motion, 'score'), 'Collection and scoring are not implemented')
        motion.rng = random.Random(12)
        motion.foods = {(8, 8)}
        motion.step()
        self.assertEqual(motion.score, 1)
        self.assertEqual(len(motion.snake), 7)
        self.assertEqual(motion.snake[0], (8, 8))
        self.assertEqual(len(motion.foods), 5)
        self.assertTrue(motion.foods.isdisjoint(motion.snake))
        self.assertNotIn((8, 8), motion.foods)
        motion.step()
        self.assertEqual(motion.score, 1)
        self.assertEqual(len(motion.snake), 7)

    def test_green_dot_only_spawns_at_six_or_more_in_an_empty_cell(self):
        for length in (4, 5, 6, 7):
            with self.subTest(length=length):
                motion = preview.MovementPreview(rng=random.Random(22))
                self.assertTrue(hasattr(motion, 'green_dot'), 'Green-dot spawning is not implemented')
                motion.snake = [(7 - index, 8) for index in range(length)]
                motion.green_elapsed_ms = 30000
                motion.step()
                if length < 6:
                    self.assertIsNone(motion.green_dot)
                else:
                    self.assertIsNotNone(motion.green_dot)
                    self.assertNotIn(motion.green_dot, motion.snake)
                    self.assertNotIn(motion.green_dot, motion.foods)

    def test_collecting_green_removes_two_tail_squares_without_changing_score(self):
        for length in (6, 7, 10):
            with self.subTest(length=length):
                motion = preview.MovementPreview(rng=random.Random(4))
                motion.snake = [(20 - index, 8) for index in range(length)]
                motion.green_dot = (21, 8)
                motion.score = 7
                motion.step()
                self.assertEqual(len(motion.snake), length - 2)
                self.assertEqual(motion.snake[0], (21, 8))
                self.assertEqual(motion.snake[-1], (20 - (length - 4), 8))
                self.assertEqual(motion.score, 7)
                self.assertIsNone(motion.green_dot)

    def test_self_collision_is_fatal_only_from_length_ten(self):
        body = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                (12, 11), (13, 11), (13, 10), (14, 10), (14, 11), (15, 11)]
        for length in (9, 10, 11):
            with self.subTest(length=length):
                motion = preview.MovementPreview(rng=random.Random(5))
                self.assertTrue(hasattr(motion, 'game_over'), 'Self-collision is not implemented')
                motion.snake = body[:length]
                motion.foods = set()
                motion.step()
                self.assertEqual(motion.game_over, length >= 10)
                if motion.game_over:
                    stopped = list(motion.snake)
                    motion.step()
                    self.assertEqual(motion.snake, stopped)
                    self.assertFalse(motion.request_turn('Up'))
                    motion.reset()
                    self.assertFalse(motion.game_over)
                    self.assertEqual(motion.score, 0)
                    self.assertEqual(len(motion.snake), 6)

    def test_moving_into_the_vacating_tail_is_safe_even_at_length_ten(self):
        motion = preview.MovementPreview()
        motion.snake = [(10, 10), (10, 11), (9, 11), (8, 11), (8, 10),
                        (8, 9), (9, 9), (10, 9), (11, 9), (11, 10)]
        motion.foods = set()
        self.assertTrue(hasattr(motion, 'game_over'), 'Self-collision is not implemented')
        motion.step()
        self.assertFalse(motion.game_over)
        self.assertEqual(motion.snake[0], (11, 10))
        self.assertEqual(len(set(motion.snake)), 10)

    def test_last_three_segments_fade_from_body_green_to_almost_black(self):
        self.assertTrue(hasattr(preview, 'segment_color'), 'Tail shading is not implemented')
        for length in (4, 6, 12):
            with self.subTest(length=length):
                start, middle, tip = [preview.segment_color(i, length)
                                      for i in range(length - 3, length)]
                self.assertEqual(start, (0.36, 0.68, 0.37))
                self.assertTrue(all(a > b > c for a, b, c in zip(start, middle, tip)))
                # Approved polish: the tip stays darkest but is no longer near-invisible.
                self.assertLess(max(tip), max(middle))
                self.assertGreater(max(tip), 0.2)
                self.assertEqual(preview.segment_color(0, length), (0.65, 0.91, 0.50))


if __name__ == '__main__':
    unittest.main()
