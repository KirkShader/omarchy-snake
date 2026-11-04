"""SnakeWindow controller paths that need no mapped window: best-score saving on finish,
New Game and close, using the real PreferenceStore in temporary directories."""
import json
import random
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.audio import AudioDirector, NullBackend  # noqa: E402
from omarchy_snake.chooser import NewGameChooser  # noqa: E402
from omarchy_snake.geometry import SCREEN_ALLOWANCE  # noqa: E402
from omarchy_snake.log import GameLog  # noqa: E402
from omarchy_snake.preferences import BestScores, PreferenceStore  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402

try:
    from omarchy_snake import app
except (ImportError, ValueError) as error:  # GTK 4 bindings missing
    app = None
    IMPORT_ERROR = error


def controller(store, game):
    """A SnakeWindow without widgets: real methods, inert presentation."""
    window = app.SnakeWindow.__new__(app.SnakeWindow)
    window.store, window.game, window.log = store, game, GameLog('quiet')
    window.best_scores = BestScores(store)
    window.widgets = defaultdict(mock.MagicMock)
    window.session = mock.MagicMock(game=game)
    window.fit = mock.MagicMock(cells=game.grid_cells)
    window.focus_check = window.theme_timer = window.chrome_measure = None
    window.window = mock.MagicMock()
    window.monitor_watch = mock.MagicMock()
    for name in ('update_overlays', 'refresh_labels', 'apply_fit'):
        setattr(window, name, mock.MagicMock())
    window.chooser = NewGameChooser()
    window.audio = AudioDirector(NullBackend())
    return window


@unittest.skipIf(app is None, 'GTK 4 bindings unavailable')
class BestScoreRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blocker = Path(self.tmp.name) / 'state'
        self.blocker.write_text('')  # a file where the state directory should be: writes fail
        self.store = PreferenceStore(Path(self.tmp.name) / 'config', self.blocker / 'omarchy-snake')
        self.game = MovementPreview(rng=random.Random(3), difficulty='Hard')
        self.game.score = 7
        self.game.game_over = True

    def tearDown(self):
        self.tmp.cleanup()

    def unblock(self):
        self.blocker.unlink()

    def saved(self):
        return json.loads(self.store.scores_path.read_text())['high_scores']['Hard']

    def finish(self, window):
        window.on_session('finished', window.session)

    def test_failed_save_on_finish_is_retried_on_close(self):
        window = controller(self.store, self.game)
        self.finish(window)
        self.assertFalse(self.store.scores_path.exists())
        self.assertEqual(window.best, 7)
        self.unblock()
        window.on_close(None)
        self.assertEqual(self.saved(), 7)

    def test_failed_save_on_finish_is_retried_on_new_game(self):
        window = controller(self.store, self.game)
        self.finish(window)
        self.unblock()
        self.game.reset('Hard')  # the next run has score 0 when New Game is chosen
        window.start_game('Hard')
        self.assertEqual(self.saved(), 7)

    def test_failed_save_retried_on_next_finish_and_memory_best_never_lowers(self):
        window = controller(self.store, self.game)
        self.finish(window)
        self.game.reset('Hard')
        self.game.score, self.game.game_over = 3, True
        self.finish(window)  # still blocked
        self.assertEqual(window.best, 7)
        self.unblock()
        self.finish(window)  # lower score, but the unsaved 7 is written
        self.assertEqual((window.best, self.saved()), (7, 7))


@unittest.skipIf(app is None, 'GTK 4 bindings unavailable')
class MonitorRefitTests(unittest.TestCase):
    """Refit follows the window's current monitor; a controlled provider stands in for GDK."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.window = controller(PreferenceStore(Path(self.tmp.name) / 'c', Path(self.tmp.name) / 's'),
                                 MovementPreview(rng=random.Random(3), difficulty='Hard'))
        self.window.args = SimpleNamespace(fit_limit=None)
        self.window.chrome, self.window.zoom = (32, 139), '100'
        self.monitor = mock.MagicMock()
        self.logical(2560, 1440)
        self.window.monitor_provider = lambda: self.monitor
        # apply_fit queues a real menu-alignment timer; test_gst_audio runs the default main
        # context, which must not fire it long after this widget-less window is gone.
        patcher = mock.patch.object(app.GLib, 'timeout_add')
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def logical(self, width, height):
        self.monitor.get_geometry.return_value = SimpleNamespace(width=width, height=height)

    def test_apply_fit_records_the_usable_area_it_fitted(self):
        app.SnakeWindow.apply_fit(self.window)
        self.assertEqual(self.window.fit_usable, (2560 - SCREEN_ALLOWANCE[0], 1440 - SCREEN_ALLOWANCE[1]))
        self.assertEqual(self.window.fit.cell_pixels, 16)

    def test_refits_only_when_the_usable_area_changes(self):
        self.window.fit_usable = (2560 - SCREEN_ALLOWANCE[0], 1440 - SCREEN_ALLOWANCE[1])
        self.window.refit_for_monitor()  # e.g. enter-monitor after our own resize: no-op
        self.window.apply_fit.assert_not_called()
        self.window.monitor_watch.track.assert_called_with(self.monitor)
        self.logical(1280, 720)  # 1920x1080 at 1.5
        self.window.refit_for_monitor()
        self.window.apply_fit.assert_called_once_with()

    def test_fit_limit_still_overrides_the_monitor(self):
        self.window.args.fit_limit = (1000, 800)
        self.window.fit_usable = (1000, 800)
        self.logical(960, 540)
        self.window.refit_for_monitor()
        self.window.apply_fit.assert_not_called()

    def test_close_disconnects_the_monitor_watch(self):
        self.window.on_close(None)
        self.window.monitor_watch.close.assert_called_once_with()


@unittest.skipIf(app is None, 'GTK 4 bindings unavailable')
class ChromeMeasureTests(unittest.TestCase):
    """Chrome is the header/footer space the board needs, measured from real allocations.

    Allocations below are the ones native_fit_check recorded for Hard at 1240x648.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.window = controller(PreferenceStore(Path(self.tmp.name) / 'c', Path(self.tmp.name) / 's'),
                                 MovementPreview(rng=random.Random(3), difficulty='Hard'))
        self.window.window = mock.MagicMock()
        self.window.widgets['content'].get_spacing.return_value = 12
        self.window.chrome_measure = None

    def tearDown(self):
        self.tmp.cleanup()

    def allocate(self, window, content, board, footer):
        self.window.window.get_width.return_value, self.window.window.get_height.return_value = window
        content_widget = self.window.widgets['content']
        content_widget.get_width.return_value, content_widget.get_height.return_value = content
        scroller = self.window.widgets['board-scroller']
        scroller.get_width.return_value = scroller.get_height.return_value = board
        for name, height in zip(('board-info', 'movement-status'), footer):
            self.window.widgets[name].get_height.return_value = height

    def test_header_wider_than_board_is_not_horizontal_chrome(self):
        self.window.chrome = app.CHROME_ESTIMATE
        self.allocate(window=(661, 663), content=(629, 584), board=524, footer=(18, 18))
        self.window.measure_chrome()
        self.assertEqual(self.window.chrome, (32, 139))
        self.window.apply_fit.assert_called_once_with()

    def test_footer_rewrapped_by_refit_is_measured_and_refitted(self):
        self.window.chrome = (32, 139)  # measured before 'reduced to fit screen' wrapped the info line
        self.allocate(window=(661, 649), content=(629, 570), board=492, footer=(36, 18))
        self.window.measure_chrome()
        self.assertEqual(self.window.chrome, (32, 157))
        self.window.apply_fit.assert_called_once_with()

    def test_leftover_height_below_the_footer_is_not_chrome(self):
        self.window.chrome = (32, 157)  # window still at its previous, taller size
        self.allocate(window=(661, 663), content=(629, 584), board=460, footer=(36, 18))
        self.window.measure_chrome()
        self.assertEqual(self.window.chrome, (32, 157))
        self.window.apply_fit.assert_not_called()

    def test_apply_fit_measures_chrome_again_after_the_next_layout(self):
        self.window.args = SimpleNamespace(fit_limit=(1240, 648))
        self.window.chrome, self.window.zoom = (32, 139), '100'
        self.window.measure_chrome = mock.MagicMock()
        clock = self.window.window.get_frame_clock.return_value
        clock.connect.return_value = 41
        with mock.patch.object(app.GLib, 'timeout_add'):
            app.SnakeWindow.apply_fit(self.window)
            app.SnakeWindow.apply_fit(self.window)  # a burst of refits waits for one layout
        clock.connect.assert_called_once()
        signal, after_paint = clock.connect.call_args.args
        self.assertEqual(signal, 'after-paint')
        self.window.measure_chrome.assert_not_called()
        after_paint(clock)
        clock.disconnect.assert_called_once_with(41)
        self.window.measure_chrome.assert_called_once_with()
        self.assertIsNone(self.window.chrome_measure)

    def test_close_cancels_a_pending_chrome_measurement(self):
        clock = self.window.window.get_frame_clock.return_value
        self.window.chrome_measure = (clock, 41)
        self.window.on_close(None)
        clock.disconnect.assert_called_once_with(41)
        self.assertIsNone(self.window.chrome_measure)


@unittest.skipIf(app is None, 'GTK 4 bindings unavailable')
class NewGameFlowTests(unittest.TestCase):
    """Choosing previews only; Start alone saves the abandoned run and resets, exactly once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PreferenceStore(Path(self.tmp.name) / 'c', Path(self.tmp.name) / 's')
        self.game = MovementPreview(rng=random.Random(3), difficulty='Easy')
        self.game.score = 9
        self.window = controller(self.store, self.game)

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, name, released=False):
        keyval = app.Gdk.keyval_from_name(name)
        handler = self.window.on_key_released if released else self.window.on_key
        return handler(None, keyval, 0, 0)

    def test_opening_pauses_for_the_chooser_on_its_choices_page(self):
        self.window.open_new_game()
        self.window.session.pause.assert_called_once_with('difficulty')
        self.assertEqual(self.window.chooser.page, 'choices')

    def test_choosing_and_back_never_reset_or_save(self):
        self.window.open_new_game()
        self.window.choose_difficulty('Hard')
        self.assertEqual((self.window.chooser.page, self.window.chooser.selected), ('details', 'Hard'))
        self.window.show_difficulty_choices()
        self.assertEqual(self.window.chooser.page, 'choices')
        self.window.session.start.assert_not_called()
        self.window.session.resume.assert_not_called()
        self.assertEqual((self.game.difficulty, self.game.score), ('Easy', 9))
        self.assertFalse(self.store.scores_path.exists())

    def test_start_commits_the_selected_difficulty_exactly_once(self):
        self.window.open_new_game()
        self.window.choose_difficulty('Normal')
        self.window.start_selected()
        self.window.start_selected()  # a second activation finds no details page
        self.window.session.start.assert_called_once_with('Normal')
        self.assertEqual(self.window.chooser.page, None)
        self.assertEqual(json.loads(self.store.scores_path.read_text())['high_scores']['Easy'], 9)

    def test_escape_goes_back_from_details_then_cancels_from_choices(self):
        self.window.open_new_game()
        self.window.choose_difficulty('Hard')
        self.assertTrue(self.key('Escape'))
        self.assertEqual(self.window.chooser.page, 'choices')
        self.window.session.resume.assert_not_called()
        self.assertTrue(self.key('Escape'))
        self.assertEqual(self.window.chooser.page, None)
        self.window.session.resume.assert_called_once_with('difficulty')
        self.window.session.start.assert_not_called()
        self.window.session.toggle_manual.assert_not_called()

    def test_held_enter_that_chose_cannot_reach_start_until_released(self):
        self.window.open_new_game()
        self.assertFalse(self.key('Return'))  # passes on to the focused choice button
        self.window.choose_difficulty('Hard')
        self.assertTrue(self.key('Return'))  # auto-repeat swallowed on the details page
        self.key('Return', released=True)
        self.assertFalse(self.key('Return'))

    def test_focus_loss_forgets_a_held_key(self):
        self.window.session.reasons = set()
        self.window.open_new_game()
        self.key('space')
        self.window.choose_difficulty('Easy')
        self.window.window.is_active.return_value = False
        with mock.patch.object(app.GLib, 'timeout_add'):
            self.window.on_active_changed(self.window.window, None)
        self.assertFalse(self.key('space'))


if __name__ == '__main__':
    unittest.main()
