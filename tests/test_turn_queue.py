"""Two-deep safe turn buffer: validated against the last queued direction."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MAX_QUEUED_TURNS, MovementPreview  # noqa: E402


def game():
    motion = MovementPreview(rng=random.Random(1), difficulty='Normal')
    motion.foods = set()
    return motion


class TurnQueueTests(unittest.TestCase):
    def test_two_quick_perpendicular_turns_apply_on_consecutive_ticks(self):
        self.assertEqual(MAX_QUEUED_TURNS, 2)
        motion = game()
        self.assertTrue(motion.request_turn('Up'))
        self.assertTrue(motion.request_turn('Left'))
        self.assertEqual(motion.queued_turns, ['Up', 'Left'])
        motion.step()
        self.assertEqual((motion.direction, motion.snake[0]), ('Up', (7, 7)))
        motion.step()
        self.assertEqual((motion.direction, motion.snake[0]), ('Left', (6, 7)))
        self.assertEqual(motion.queued_turns, [])

    def test_quick_u_turn_never_happens_in_a_single_tick(self):
        motion = game()
        motion.request_turn('Up')
        motion.request_turn('Left')
        before = motion.snake[0]
        motion.step()
        # One tick consumes only one turn, so the head can never move back on itself.
        self.assertNotEqual(motion.snake[0], (before[0] - 1, before[1]))
        self.assertEqual(motion.snake[0], (before[0], before[1] - 1))
        self.assertNotIn(motion.snake[0], motion.snake[1:])

    def test_turn_validated_against_last_queued_direction(self):
        motion = game()
        self.assertTrue(motion.request_turn('Down'))
        self.assertFalse(motion.request_turn('Up'))  # reverses the queued Down
        self.assertFalse(motion.request_turn('Down'))  # duplicate of queued Down
        self.assertTrue(motion.request_turn('Right'))  # back to original heading after a Down step
        self.assertFalse(motion.request_turn('Up'))  # queue is full
        self.assertEqual(motion.queued_turns, ['Down', 'Right'])

    def test_queue_cleared_by_reset_and_rejected_after_finish(self):
        motion = game()
        motion.request_turn('Up')
        motion.reset()
        self.assertEqual(motion.queued_turns, [])
        self.assertIsNone(motion.pending_direction)
        motion.game_over = True
        self.assertFalse(motion.request_turn('Up'))

    def test_pending_direction_compatibility_view(self):
        motion = game()
        motion.request_turn('Up')
        motion.request_turn('Left')
        self.assertEqual(motion.pending_direction, 'Up')
        motion.pending_direction = None
        self.assertEqual(motion.queued_turns, [])
        motion.pending_direction = 'Down'
        self.assertEqual(motion.queued_turns, ['Down'])


if __name__ == '__main__':
    unittest.main()
