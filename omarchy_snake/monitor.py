"""Follows the monitor under the game window so the board refits when it changes.

Watches the surface's enter/leave-monitor, monitor hotplug (items-changed) and every
property of the current monitor (geometry, scale, scale-factor, ...). Any burst of those
becomes one idle refit request; the controller refits only if the usable area changed,
so its own window resize cannot start a loop. Toolkit-free: tests drive it with fakes.
"""


class MonitorWatch:
    def __init__(self, on_change, idle_add, source_remove):
        self.on_change = on_change
        self.idle_add, self.source_remove = idle_add, source_remove
        self.handlers, self.monitor_handlers = [], []
        self.monitor = None
        self.pending = None
        self.closed = False

    def watch(self, surface, monitors):
        if self.closed:
            return
        for emitter, signal in ((surface, 'enter-monitor'), (surface, 'leave-monitor'),
                                (monitors, 'items-changed')):
            self.handlers.append((emitter, emitter.connect(signal, self.changed)))

    def track(self, monitor):
        """Move the property handlers to the monitor the window is now on."""
        if self.closed or monitor is self.monitor:
            return
        self._disconnect(self.monitor_handlers)
        self.monitor = monitor
        if monitor is not None:
            self.monitor_handlers = [(monitor, monitor.connect(signal, self.changed))
                                     for signal in ('notify', 'invalidate')]

    def changed(self, *_args):
        if self.pending is None and not self.closed:
            self.pending = self.idle_add(self._fire)

    def _fire(self):
        self.pending = None
        if not self.closed:
            self.on_change()
        return False

    def close(self):
        self.closed = True
        if self.pending is not None:
            self.source_remove(self.pending)
            self.pending = None
        self._disconnect(self.handlers)
        self._disconnect(self.monitor_handlers)
        self.monitor = None

    @staticmethod
    def _disconnect(handlers):
        for emitter, handler in handlers:
            emitter.disconnect(handler)
        handlers.clear()
