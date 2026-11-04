"""Display-independent New Game chooser: a choices page, then a details page with Start/Back.

Choosing a difficulty only previews it; Start is the single commit. Enter/Space that opened
the chooser or changed its page must be released before the new page's buttons respond, so a
held key's auto-repeat cannot run on from a choice into Start.
"""
ACTIVATION_KEYS = frozenset({'Return', 'KP_Enter', 'ISO_Enter', 'space', 'KP_Space'})


class NewGameChooser:
    def __init__(self):
        self.page = None  # None (closed), 'choices' or 'details'
        self.selected = None
        self.held = set()
        self.armed = True

    def _show(self, page):
        self.page = page
        self.armed = not self.held

    def open(self):
        self.selected = None
        self._show('choices')

    def choose(self, difficulty):
        self.selected = difficulty
        self._show('details')

    def back(self):
        self._show('choices')

    def close(self):
        self.page = self.selected = None

    def escape(self):
        """Details goes back to choices; choices closes the chooser."""
        if self.page == 'details':
            self.back()
            return 'back'
        self.close()
        return 'close'

    def start(self):
        """Return the difficulty to start (and close), or None when Start is not on screen."""
        if self.page != 'details':
            return None
        difficulty = self.selected
        self.close()
        return difficulty

    def key_pressed(self, key):
        """Return True when the press must be swallowed (a held key on a fresh page)."""
        if key not in ACTIVATION_KEYS:
            return False
        self.held.add(key)
        return self.page is not None and not self.armed

    def key_released(self, key):
        self.held.discard(key)
        if not self.held:
            self.armed = True

    def release_all(self):
        self.held.clear()
        self.armed = True
