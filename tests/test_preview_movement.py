"""Checks for the speed-only preview, not full Snake gameplay."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('movement_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def moving_snake():
    game = preview.MovementPreview()
    game.foods = set()  # Movement tests must not collect random orange dots.
    return game


class MovementPreviewTests(unittest.TestCase):
    def test_one_tick_moves_the_whole_snake_one_cell_right(self):
        self.assertTrue(hasattr(preview, 'MovementPreview'), 'Movement is not implemented')
        motion = moving_snake()
        self.assertEqual(motion.snake, [(7, 8), (6, 8), (5, 8), (4, 8), (3, 8), (2, 8)])
        motion.step()
        self.assertEqual(motion.snake, [(8, 8), (7, 8), (6, 8), (5, 8), (4, 8), (3, 8)])
        self.assertEqual(motion.ticks, 1)
        self.assertEqual(preview.STEP_INTERVAL_MS, 150)

    def test_right_edge_wrap_preserves_row_and_body_order(self):
        self.assertTrue(hasattr(preview, 'MovementPreview'), 'Movement is not implemented')
        motion = moving_snake()
        edge = preview.GRID_CELLS - 1
        motion.snake = [(edge, 8), (edge - 1, 8), (edge - 2, 8)]
        motion.step()
        self.assertEqual(motion.snake, [(0, 8), (edge, 8), (edge - 1, 8)])
        for _ in range(preview.GRID_CELLS):
            motion.step()
        self.assertEqual(motion.snake, [(0, 8), (edge, 8), (edge - 1, 8)])

    def test_each_arrow_direction_steers_on_the_next_tick(self):
        motion = moving_snake()
        self.assertTrue(hasattr(motion, 'request_turn'), 'Steering is not implemented')
        for key, head in [('Up', (7, 7)), ('Left', (6, 7)),
                          ('Down', (6, 8)), ('Right', (7, 8))]:
            with self.subTest(key=key):
                self.assertTrue(motion.request_turn(key))
                motion.step()
                self.assertEqual(motion.snake[0], head)
                self.assertEqual(len(motion.snake), 6)

    def test_reversal_and_multiple_turns_in_one_tick_are_ignored(self):
        motion = moving_snake()
        self.assertFalse(motion.request_turn('Left'))
        self.assertTrue(motion.request_turn('Up'))
        self.assertFalse(motion.request_turn('Left'))
        self.assertFalse(motion.request_turn('Up'))
        motion.step()
        self.assertEqual(motion.direction, 'Up')
        self.assertFalse(motion.request_turn('Down'))
        self.assertFalse(motion.request_turn('space'))
        self.assertTrue(motion.request_turn('Left'))
        motion.step()
        self.assertEqual(motion.direction, 'Left')

    def test_wrapping_works_on_all_four_edges(self):
        edge = preview.GRID_CELLS - 1
        for direction, start, expected in [
                ('Right', (edge, 8), (0, 8)), ('Left', (0, 8), (edge, 8)),
                ('Up', (7, 0), (7, edge)), ('Down', (7, edge), (7, 0))]:
            with self.subTest(direction=direction):
                motion = moving_snake()
                motion.snake = [start, (3, 3), (2, 3)]
                motion.direction = direction
                motion.step()
                self.assertEqual(motion.snake[0], expected)

    def test_new_game_resets_position_length_direction_and_pending_input(self):
        motion = moving_snake()
        self.assertTrue(hasattr(motion, 'reset'), 'New Game reset is not implemented')
        motion.request_turn('Up')
        motion.step()
        motion.request_turn('Left')
        motion.snake.append((0, 0))
        motion.reset()
        self.assertEqual(motion.snake, [(7, 8), (6, 8), (5, 8), (4, 8), (3, 8), (2, 8)])
        self.assertEqual(motion.direction, 'Right')
        self.assertIsNone(motion.pending_direction)
        self.assertEqual(motion.ticks, 0)


if __name__ == '__main__':
    unittest.main()
