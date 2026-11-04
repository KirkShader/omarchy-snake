"""Optional diagnostics: quiet by default, never able to stop gameplay."""
import io
import json
import os
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.log import GameLog  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402
from omarchy_snake.session import GameSession  # noqa: E402


class Broken(io.StringIO):
    def __init__(self, error):
        super().__init__()
        self.error, self.attempts = error, 0

    def write(self, _text):
        self.attempts += 1
        raise self.error


class LoggingTests(unittest.TestCase):
    def test_normal_play_is_quiet(self):
        stream = io.StringIO()
        log = GameLog('quiet', stream)
        log.event('step', head=(1, 2))
        log.debug('movement', segments=[(1, 2)] * 500)
        self.assertEqual(stream.getvalue(), '')

    def test_verbose_logs_events_without_snake_dumps_and_debug_adds_them(self):
        stream = io.StringIO()
        GameLog('verbose', stream).event('mechanics', score=3)
        GameLog('verbose', stream).debug('movement', segments=[(1, 2)])
        self.assertEqual([json.loads(line) for line in stream.getvalue().splitlines()],
                         [{'event': 'mechanics', 'score': 3}])
        stream = io.StringIO()
        GameLog('debug', stream).debug('movement', segments=[(1, 2)])
        self.assertEqual(json.loads(stream.getvalue())['segments'], [[1, 2]])
        with self.assertRaises(ValueError):
            GameLog('chatty', stream)

    def test_closed_or_failing_output_disables_logging_instead_of_raising(self):
        for error in (BrokenPipeError(), OSError(5, 'I/O error'), ValueError('closed file')):
            with self.subTest(error=type(error).__name__):
                stream = Broken(error)
                log = GameLog('debug', stream)
                self.assertFalse(log.event('one'))
                self.assertFalse(log.event('two'))
                self.assertEqual(stream.attempts, 1)
                self.assertFalse(log.enabled)

    def test_real_closed_pipe_does_not_stop_movement(self):
        read_end, write_end = os.pipe()
        os.close(read_end)
        stream = os.fdopen(write_end, 'w', buffering=1)
        log = GameLog('debug', stream)
        game = MovementPreview(rng=random.Random(1))
        game.foods = set()
        sources = {}

        class Scheduler:
            def add(self, _ms, callback):
                sources[1] = callback
                return 1

            def remove(self, source):
                sources.pop(source, None)

        session = GameSession(game, Scheduler(), now=lambda: 0.0,
                              listener=lambda event, s: log.debug(event, head=s.game.snake[0]))
        session.begin()
        for _ in range(5):
            self.assertTrue(sources[1]())
        self.assertEqual(game.ticks, 5)
        self.assertFalse(log.enabled)
        try:
            stream.close()
        except BrokenPipeError:
            pass


if __name__ == '__main__':
    unittest.main()
