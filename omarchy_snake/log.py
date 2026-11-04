"""Optional JSON-lines diagnostics (--verbose / --debug); quiet in normal play.

Output failures (closed pipe, full disk, closed stream) disable logging rather than raising,
so a diagnostic write can never stop the movement timer.
"""
import json
import sys

LEVELS = ('quiet', 'verbose', 'debug')


class GameLog:
    def __init__(self, level='quiet', stream=None):
        if level not in LEVELS:
            raise ValueError(f'Unknown log level: {level}')
        self.level = level
        self.stream = stream if stream is not None else sys.stdout
        self.enabled = level != 'quiet'

    def event(self, name, **data):
        """Record a notable event at verbose or debug level."""
        return self._write(name, data)

    def debug(self, name, **data):
        """Record detail (such as full snake segments) only at debug level."""
        if self.level != 'debug':
            return False
        return self._write(name, data)

    def __call__(self, name, **data):
        return self.event(name, **data)

    def _write(self, name, data):
        if not self.enabled:
            return False
        try:
            self.stream.write(json.dumps({'event': name, **data}, default=list) + '\n')
            self.stream.flush()
        except (OSError, ValueError):
            self.enabled = False
            return False
        return True
