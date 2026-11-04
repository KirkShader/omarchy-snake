"""The rules report what the last step collected, so sound never has to guess from a diff."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402


def game(difficulty='Easy'):
    run = MovementPreview(rng=random.Random(5), difficulty=difficulty)
    run.foods, run.green_dot = set(), None
    return run


class LastRewardTests(unittest.TestCase):
    def test_orange_is_reported_for_exactly_the_step_that_collects_it(self):
        run = game()
        run.foods = {(8, 8)}
        run.step()
        self.assertEqual(run.last_reward, 'orange')
        run.foods = set()
        run.step()
        self.assertIsNone(run.last_reward)

    def test_green_is_reported(self):
        run = game()
        run.green_dot = (8, 8)
        run.step()
        self.assertEqual(run.last_reward, 'green')

    def test_a_green_dot_on_a_short_snake_is_no_reward(self):
        run = game()
        run.snake = run.snake[:5]
        run.green_dot = (8, 8)
        run.step()
        self.assertIsNone(run.last_reward)

    def test_collision_gives_no_reward_even_onto_food(self):
        run = game('Hard')
        run.snake = [(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8)]
        run.direction = 'Left'
        run.foods = {(1, 7)}
        run.step()
        self.assertTrue(run.game_over)
        self.assertIsNone(run.last_reward)
        run = game()
        run.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                     (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
        run.direction, run.foods = 'Right', {(11, 10)}
        run.step()
        self.assertTrue(run.game_over)
        self.assertIsNone(run.last_reward)

    def test_the_last_orange_is_reported_together_with_victory(self):
        run = game('Hard')
        path = [(x if y % 2 == 0 else 31 - x, y) for y in range(32) for x in range(32)]
        run.snake = list(reversed(path[:-1]))
        run.direction, run.foods = 'Left', {path[-1]}
        run.step()
        self.assertTrue(run.won)
        self.assertEqual(run.last_reward, 'orange')

    def test_reset_clears_the_reward(self):
        run = game()
        run.foods = {(8, 8)}
        run.step()
        run.reset()
        self.assertIsNone(run.last_reward)


if __name__ == '__main__':
    unittest.main()
