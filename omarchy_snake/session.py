"""Display-independent run controller: pause reasons, movement timer and step clock.

Pause policy (documented in README):
- Each reason is tracked separately: manual (Escape/Resume), menu (popover open),
  color (native colour chooser open), focus (window inactive), difficulty (chooser open).
  Movement and the green cooldown run only when no reason remains.
- Closing the menu, colour chooser or difficulty chooser removes only its own reason,
  so it can never resume a manual pause.
- Losing window focus freezes the run at once (focus reason). If focus is still gone after
  FOCUS_LOSS_CONFIRM_MS, the manual pause is engaged too, unless focus moved to the game's
  own colour chooser. Regaining focus never resumes a manual pause. The delay ignores the
  brief inactive blip GTK reports on Wayland while a popover opens.
- A finished (lost or won) run cannot be paused; only New Game restarts it.
"""
from time import monotonic

PAUSE_REASONS = ('manual', 'menu', 'color', 'focus', 'difficulty')
# A late callback is credited its real delay up to this many step intervals; longer
# stalls (suspend, a blocked event loop) are not added to the green cooldown.
STALL_CREDIT_FACTOR = 2
FOCUS_LOSS_CONFIRM_MS = 300


def escape_action(chooser_open, menu_open, finished, chooser_details=False):
    """Escape closes the innermost surface first, then toggles the manual pause.
    The chooser's details page steps back to its choices page before the chooser closes."""
    if chooser_open:
        return 'chooser-back' if chooser_details else 'close-chooser'
    if menu_open:
        return 'close-menu'
    return 'none' if finished else 'toggle-pause'


class StepClock:
    """Measures active time between movement callbacks; resumes never count paused time."""

    def __init__(self, now=monotonic):
        self.now = now
        self.last = now()

    def restart(self):
        self.last = self.now()

    def credit(self, interval_ms):
        current = self.now()
        actual = max(0.0, (current - self.last) * 1000)
        self.last = current
        return min(actual, interval_ms * STALL_CREDIT_FACTOR)


class GameSession:
    """Owns at most one movement timer; exactly one step per timer callback, no catch-up."""

    def __init__(self, game, scheduler, now=monotonic, listener=None):
        self.game = game
        self.scheduler = scheduler
        self.clock = StepClock(now)
        self.listener = listener or (lambda _event, _session: None)
        self.reasons = set()
        self.timer = None
        self.started = False

    @property
    def paused(self):
        return bool(self.reasons)

    @property
    def manually_paused(self):
        return 'manual' in self.reasons

    def begin(self):
        """Start the timer unless a reason (such as the launch chooser) is already set."""
        self.started = True
        self.listener('begin', self)
        self._sync()

    def stop(self):
        """Remove the movement timer for good (window closing)."""
        self.started = False
        self._stop_timer()

    def start(self, difficulty=None):
        self.started = True
        self._stop_timer()
        self.game.reset(difficulty)
        self.reasons -= {'manual', 'difficulty'}
        self.listener('new_game', self)
        self._sync()

    def pause(self, reason):
        if reason not in PAUSE_REASONS:
            raise ValueError(f'Unknown pause reason: {reason}')
        if reason == 'manual' and self.game.finished:
            return
        if reason not in self.reasons:
            self.reasons.add(reason)
            self.listener('pause_changed', self)
        self._sync()

    def resume(self, reason):
        if reason in self.reasons:
            self.reasons.discard(reason)
            self.listener('pause_changed', self)
        self._sync()

    def toggle_manual(self):
        """Return the new manual-pause state, or None when the run has finished."""
        if self.game.finished:
            return None
        if self.manually_paused:
            self.resume('manual')
        else:
            self.pause('manual')
        return self.manually_paused

    def focus_changed(self, active):
        if active:
            self.resume('focus')
        else:
            self.pause('focus')

    def confirm_focus_loss(self, own_dialog=False):
        """Called FOCUS_LOSS_CONFIRM_MS after a focus loss; a sustained loss pauses manually."""
        if 'focus' in self.reasons and not own_dialog and not self.game.finished:
            self.pause('manual')

    def steer(self, key):
        if self.paused:
            return False
        return self.game.request_turn(key)

    def _stop_timer(self):
        if self.timer is not None:
            self.scheduler.remove(self.timer)
            self.timer = None

    @property
    def running(self):
        return self.started and not self.paused and not self.game.finished

    def _sync(self):
        if self.running and self.timer is None:
            self.clock.restart()
            self._schedule()
        elif not self.running:
            self._stop_timer()

    def _schedule(self):
        # Each callback knows its own source, so a replaced or removed timer can never step.
        source = self.timer = self.scheduler.add(round(self.game.step_interval_ms),
                                                 lambda: self._tick(source))

    def _tick(self, source):
        if source != self.timer or not self.running:
            return False
        previous_interval = self.game.step_interval_ms
        self.game.step(elapsed_ms=self.clock.credit(previous_interval))
        self.listener('step', self)
        if self.game.finished:
            if self.timer == source:
                self.timer = None
            self.listener('finished', self)
            return False
        if self.timer != source:  # the listener paused, stopped or restarted the run
            return False
        if self.game.step_interval_ms != previous_interval:
            self._schedule()
            return False
        return True
