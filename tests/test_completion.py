"""Full-board victory, exhausted food/green spawning and finished-state behaviour."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import GREEN_INTERVAL_MS, MovementPreview  # noqa: E402

# 15-cell serpentine on a 4 x 4 board; the only free cell is (0, 3), left of the head.
SERPENTINE = [(1, 3), (2, 3), (3, 3), (3, 2), (2, 2), (1, 2), (0, 2), (0, 1),
              (1, 1), (2, 1), (3, 1), (3, 0), (2, 0), (1, 0), (0, 0)]


def tiny(difficulty='Hard', size=4):
    """Fixture: real rules on a small board so completion is reachable in tests."""
    game = MovementPreview(rng=random.Random(3), difficulty=difficulty)
    game.grid_cells = size
    game.foods = set()
    game.green_dot = None
    return game


class CompletionTests(unittest.TestCase):
    def test_filling_every_cell_wins_and_awards_the_final_point(self):
        for difficulty in ('Easy', 'Hard'):
            with self.subTest(difficulty=difficulty):
                game = tiny(difficulty)
                game.snake = list(SERPENTINE)
                game.direction = 'Left'
                game.foods = {(0, 3)}
                game.score = 9
                game.step()
                self.assertTrue(game.won)
                self.assertFalse(game.game_over)
                self.assertTrue(game.finished)
                self.assertEqual(game.state, 'won')
                self.assertEqual(game.score, 10)
                self.assertEqual(len(set(game.snake)), 16)
                self.assertEqual(game.foods, set())
                self.assertIsNone(game.green_dot)

    def test_no_moves_turns_or_cooldown_after_victory_and_reset_clears_it(self):
        game = tiny()
        game.snake = list(SERPENTINE)
        game.direction = 'Left'
        game.foods = {(0, 3)}
        game.step()
        frozen = (list(game.snake), game.ticks, game.score, game.green_elapsed_ms)
        self.assertFalse(game.request_turn('Up'))
        game.step(elapsed_ms=GREEN_INTERVAL_MS * 2)
        self.assertEqual((game.snake, game.ticks, game.score, game.green_elapsed_ms), frozen)
        game.reset('Hard')
        self.assertEqual((game.state, game.won, game.finished, game.score), ('playing', False, False, 0))

    def test_remaining_cells_all_being_food_is_not_a_win(self):
        game = tiny()
        game.snake = SERPENTINE[:-1]  # 14 cells; (0, 0) and (0, 3) free
        game.direction = 'Left'
        game.foods = {(0, 3), (0, 0)}
        game.step()
        self.assertFalse(game.won)
        self.assertFalse(game.finished)
        self.assertEqual(game.state, 'playing')
        self.assertEqual(game.foods, {(0, 0)})
        self.assertEqual(len(game.snake), 15)

    def test_refill_is_partial_when_space_runs_out_and_terminates(self):
        game = tiny()  # Hard wants ten oranges
        game.snake = SERPENTINE[:13]  # three free cells: (1,0), (0,0), (0,3)
        game.refill_foods()
        self.assertEqual(game.foods, {(1, 0), (0, 0), (0, 3)})
        game.refill_foods()  # repeated calls stay bounded and unchanged
        self.assertEqual(len(game.foods), 3)

    def test_due_green_waits_for_space_then_spawns_without_a_new_cooldown(self):
        game = tiny()
        loop = [(0, 1), (1, 1), (2, 1), (3, 1), (3, 0), (2, 0), (1, 0), (0, 0)]
        game.snake = list(loop)
        game.direction = 'Up'  # head enters the vacating tail cell
        game.foods = {(x, y) for y in (2, 3) for x in range(4)}
        game.green_elapsed_ms = GREEN_INTERVAL_MS
        game.step()
        self.assertFalse(game.finished)
        self.assertIsNone(game.green_dot)
        self.assertGreaterEqual(game.green_elapsed_ms, GREEN_INTERVAL_MS)
        game.foods.discard((3, 3))
        game.direction = 'Right'  # head (0, 0) enters the new vacating tail (1, 0)
        game.step()
        self.assertFalse(game.finished)
        self.assertEqual(game.green_dot, (3, 3))
        self.assertEqual(game.green_elapsed_ms, 0)

    def test_lost_state_is_distinct_from_won(self):
        game = tiny()
        game.snake = [(3, 1), (2, 1), (1, 1)]
        game.direction = 'Right'
        game.step()
        self.assertEqual((game.state, game.game_over, game.won, game.finished),
                         ('lost', True, False, True))


if __name__ == '__main__':
    unittest.main()
