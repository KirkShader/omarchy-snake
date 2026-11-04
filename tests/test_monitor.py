"""MonitorWatch: monitor enter/leave, geometry/scale and hotplug changes become one
coalesced refit request; everything is disconnected on close."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.monitor import MonitorWatch  # noqa: E402


class Emitter:
    """Stands in for a GObject: connect/disconnect/emit by signal name."""

    def __init__(self):
        self.handlers, self.next_id = {}, 1

    def connect(self, signal, callback):
        handler = self.next_id
        self.next_id += 1
        self.handlers[handler] = (signal, callback)
        return handler

    def disconnect(self, handler):
        del self.handlers[handler]

    def emit(self, signal, *args):
        for name, callback in list(self.handlers.values()):
            if name == signal:
                callback(self, *args)

    def signals(self):
        return sorted(name for name, _ in self.handlers.values())


class Idle:
    def __init__(self):
        self.sources, self.next_id = {}, 1

    def add(self, callback):
        source = self.next_id
        self.next_id += 1
        self.sources[source] = callback
        return source

    def remove(self, source):
        del self.sources[source]

    def run(self):
        for source, callback in list(self.sources.items()):
            if not callback():
                self.sources.pop(source, None)


class MonitorWatchTests(unittest.TestCase):
    def setUp(self):
        self.idle, self.refits = Idle(), []
        self.watch = MonitorWatch(lambda: self.refits.append(1), self.idle.add, self.idle.remove)
        self.surface, self.monitors, self.monitor = Emitter(), Emitter(), Emitter()
        self.watch.watch(self.surface, self.monitors)
        self.watch.track(self.monitor)

    def test_watches_enter_leave_hotplug_and_monitor_properties(self):
        self.assertEqual(self.surface.signals(), ['enter-monitor', 'leave-monitor'])
        self.assertEqual(self.monitors.signals(), ['items-changed'])
        self.assertEqual(self.monitor.signals(), ['invalidate', 'notify'])

    def test_bursts_of_changes_coalesce_into_one_refit(self):
        self.surface.emit('enter-monitor', self.monitor)
        self.monitor.emit('notify', 'geometry')
        self.monitor.emit('notify', 'scale')
        self.monitors.emit('items-changed', 0, 0, 1)
        self.assertEqual(len(self.idle.sources), 1)
        self.idle.run()
        self.assertEqual((self.refits, self.idle.sources), ([1], {}))
        self.surface.emit('leave-monitor', self.monitor)
        self.idle.run()
        self.assertEqual(self.refits, [1, 1])

    def test_tracking_another_monitor_moves_the_property_handlers(self):
        other = Emitter()
        self.watch.track(other)
        self.assertEqual((self.monitor.signals(), other.signals()), ([], ['invalidate', 'notify']))
        self.watch.track(other)  # same monitor: no duplicate handlers
        self.assertEqual(other.signals(), ['invalidate', 'notify'])
        self.watch.track(None)
        self.assertEqual(other.signals(), [])

    def test_close_disconnects_everything_and_drops_a_pending_refit(self):
        self.monitor.emit('notify', 'geometry')
        self.watch.close()
        self.assertEqual(self.idle.sources, {})
        self.assertEqual(self.surface.signals() + self.monitors.signals() + self.monitor.signals(), [])
        self.watch.changed()
        self.watch.track(Emitter())
        self.idle.run()
        self.assertEqual(self.refits, [])


if __name__ == '__main__':
    unittest.main()
