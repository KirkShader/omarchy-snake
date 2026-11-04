"""Two-page New Game chooser: choosing previews only, Back/Escape step out, held keys never cascade."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.chooser import NewGameChooser  # noqa: E402


class PageTests(unittest.TestCase):
    def test_opens_on_the_choices_page_with_nothing_selected(self):
        chooser = NewGameChooser()
        self.assertEqual((chooser.page, chooser.selected), (None, None))
        chooser.open()
        self.assertEqual((chooser.page, chooser.selected), ('choices', None))

    def test_choosing_only_previews_the_difficulty(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.choose('Hard')
        self.assertEqual((chooser.page, chooser.selected), ('details', 'Hard'))

    def test_back_returns_to_choices_and_remembers_the_selection(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.choose('Normal')
        chooser.back()
        self.assertEqual((chooser.page, chooser.selected), ('choices', 'Normal'))

    def test_escape_goes_back_from_details_then_closes_from_choices(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.choose('Easy')
        self.assertEqual(chooser.escape(), 'back')
        self.assertEqual(chooser.page, 'choices')
        self.assertEqual(chooser.escape(), 'close')
        self.assertEqual((chooser.page, chooser.selected), (None, None))

    def test_start_commits_only_from_the_details_page(self):
        chooser = NewGameChooser()
        self.assertIsNone(chooser.start())
        chooser.open()
        self.assertIsNone(chooser.start())
        chooser.choose('Hard')
        self.assertEqual(chooser.start(), 'Hard')
        self.assertEqual((chooser.page, chooser.selected), (None, None))
        self.assertIsNone(chooser.start())  # a second Start cannot reset again

    def test_reopening_starts_fresh_on_the_choices_page(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.choose('Hard')
        chooser.close()
        chooser.open()
        self.assertEqual((chooser.page, chooser.selected), ('choices', None))


class HeldKeyTests(unittest.TestCase):
    """An Enter/Space that changed the page (or opened the chooser) must be released before the
    new page's buttons respond, so auto-repeat cannot run on from a choice into Start."""

    def test_repeat_of_the_key_that_chose_is_swallowed_until_released(self):
        chooser = NewGameChooser()
        chooser.open()
        self.assertFalse(chooser.key_pressed('Return'))  # activates the focused choice
        chooser.choose('Hard')
        self.assertTrue(chooser.key_pressed('Return'))  # auto-repeat on the details page
        self.assertTrue(chooser.key_pressed('Return'))
        chooser.key_released('Return')
        self.assertFalse(chooser.key_pressed('Return'))  # a fresh press may Start

    def test_key_held_when_the_chooser_opens_cannot_choose(self):
        chooser = NewGameChooser()
        chooser.key_pressed('space')  # e.g. Space on the Game Over card's New Game button
        chooser.open()
        self.assertTrue(chooser.key_pressed('space'))
        chooser.key_released('space')
        self.assertFalse(chooser.key_pressed('space'))

    def test_every_activation_key_must_be_released(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.key_pressed('Return')
        chooser.key_pressed('KP_Enter')
        chooser.choose('Easy')
        chooser.key_released('Return')
        self.assertTrue(chooser.key_pressed('KP_Enter'))
        chooser.key_released('KP_Enter')
        self.assertFalse(chooser.key_pressed('space'))

    def test_pointer_choice_with_no_key_held_leaves_start_usable(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.choose('Normal')
        self.assertFalse(chooser.key_pressed('Return'))

    def test_other_keys_and_a_closed_chooser_are_never_swallowed(self):
        chooser = NewGameChooser()
        chooser.key_pressed('Return')
        self.assertFalse(chooser.key_pressed('Return'))  # closed: ordinary widgets get it
        chooser.open()
        self.assertFalse(chooser.key_pressed('Tab'))
        self.assertFalse(chooser.key_pressed('Escape'))

    def test_focus_loss_forgets_held_keys(self):
        chooser = NewGameChooser()
        chooser.open()
        chooser.key_pressed('Return')
        chooser.choose('Hard')
        chooser.release_all()  # the release went to another window
        self.assertFalse(chooser.key_pressed('Return'))


if __name__ == '__main__':
    unittest.main()
