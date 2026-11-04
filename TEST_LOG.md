# Test log — approved polish (2026-10-31)

Genuine command output, trimmed with `tail`/`grep` where noted. Command: `/usr/bin/python -m unittest ...` from repo root.

## Marketplace launcher prerequisite (2026-11-04, MARKETPLACE_BRIEF.md)

RED, before any plugin file existed (trimmed to the summary):
```
$ /usr/bin/python -m unittest tests.test_marketplace_plugin -q
Ran 17 tests in 0.005s
FAILED (failures=7, errors=13)
```

GREEN for the runtime and packaging classes, before the docs slice and the later `press-right` test:
```
$ /usr/bin/python -m unittest tests.test_marketplace_plugin.LauncherRuntimeTests tests.test_marketplace_plugin.PackagingTests -q
Ran 13 tests in 8.267s
OK
```

Runtime tests load the unmodified `BarWidget.qml` in Quickshell 0.3.2 (offscreen, environment built from nothing), and the real `execDetached` runs `/usr/bin/python` on a stub `grid_preview.py` in a relocated hostile path. Fault injection on scratch copies: 11 of 13 faults caught at first. The other two were each masked by the other button check, so a `triggerPress(right)` test was added; both were then caught. The real bar and a real click on the desktop were not exercised, and `qmllint` was not run.

Final results, trimmed to the summary:
```
$ /usr/bin/python -m unittest tests.test_marketplace_plugin -q
Ran 18 tests in 9.284s
OK
$ /usr/bin/python -m unittest discover -s tests -q
Ran 236 tests in 13.852s
OK
```

## Independent pre-publication launcher verification — 2026-11-04

After the historical implementation run above, the coordinator independently ran `/usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml BarWidget.qml` successfully (exit 0), `omarchy plugin validate .` successfully (exit 0), all 18 marketplace tests successfully, and the full 236-test suite successfully. A separate read-only reviewer also verified the validator, linter and all 236 tests and found no correctness, security or packaging blockers. The QML launch tests remain isolated offscreen tests with a mock bar and a scratch game stub, not an installation or click in the user's live bar. No game code or live desktop configuration was changed.

## Slice 0 — refactor into package + façade (behaviour-preserving)

Baseline before any change and after moving code into `omarchy_snake/` (both runs, observed in session):
```
Ran 30 tests in 0.041s

OK
```

## Slice 1 — Hard 50 ms floor

RED:
```
ERROR: test_balanced_hard_keeps_linear_curve_until_the_50ms_floor (tests.test_hard_rules.HardRulesTests.test_balanced_hard_keeps_linear_curve_until_the_50ms_floor)
AttributeError: module 'hard_preview' has no attribute 'HARD_MIN_STEP_INTERVAL_MS'. Did you mean: 'MIN_STEP_INTERVAL_MS'?
FAIL: test_green_does_not_undo_speed_at_the_floor (tests.test_hard_rules.HardRulesTests.test_green_does_not_undo_speed_at_the_floor)
AssertionError: Tuples differ: (70, 4, 1) != (70, 4, 50)
Ran 11 tests in 0.013s
FAILED (failures=1, errors=1)
```

GREEN:
```
Ran 32 tests in 0.045s

OK
```

## Slice 2 — two-deep safe turn queue

RED:
```
ERROR: test_turn_queue (unittest.loader._FailedTest.test_turn_queue)
ImportError: Failed to import test module: test_turn_queue
ImportError: cannot import name 'MAX_QUEUED_TURNS' from 'omarchy_snake.rules' (/home/bignutta/Work/omarchy-snake/omarchy_snake/rules.py)
FAIL: test_reversal_and_queue_overflow_are_ignored (tests.test_preview_movement.MovementPreviewTests.test_reversal_and_queue_overflow_are_ignored)
AssertionError: False is not true
Ran 7 tests in 0.011s
FAILED (failures=1, errors=1)
```

GREEN:
```
Ran 37 tests in 0.046s

OK
```

## Slice 3 — completion / victory and exhausted spawns

RED:
```
ERROR: test_due_green_waits_for_space_then_spawns_without_a_new_cooldown (tests.test_completion.CompletionTests.test_due_green_waits_for_space_then_spawns_without_a_new_cooldown)
AttributeError: 'MovementPreview' object has no attribute 'finished'
ERROR: test_filling_every_cell_wins_and_awards_the_final_point (tests.test_completion.CompletionTests.test_filling_every_cell_wins_and_awards_the_final_point) (difficulty='Easy')
AttributeError: 'MovementPreview' object has no attribute 'won'
ERROR: test_filling_every_cell_wins_and_awards_the_final_point (tests.test_completion.CompletionTests.test_filling_every_cell_wins_and_awards_the_final_point) (difficulty='Hard')
AttributeError: 'MovementPreview' object has no attribute 'won'
ERROR: test_lost_state_is_distinct_from_won (tests.test_completion.CompletionTests.test_lost_state_is_distinct_from_won)
AttributeError: 'MovementPreview' object has no attribute 'state'. Did you mean: 'snake'?
ERROR: test_remaining_cells_all_being_food_is_not_a_win (tests.test_completion.CompletionTests.test_remaining_cells_all_being_food_is_not_a_win)
AttributeError: 'MovementPreview' object has no attribute 'won'
FAIL: test_no_moves_turns_or_cooldown_after_victory_and_reset_clears_it (tests.test_completion.CompletionTests.test_no_moves_turns_or_cooldown_after_victory_and_reset_clears_it)
AssertionError: True is not false
Ran 6 tests in 0.006s
FAILED (failures=1, errors=5)
```

GREEN:
```
Ran 43 tests in 0.050s

FAILED (failures=1)
```

First GREEN attempt failed: fixture bug (second step left a Hard wall). Corrected fixture direction; rules unchanged.
```
Ran 43 tests in 0.050s

OK
```

Profile (decides on optimisation):
```
Easy: empty_cell with 2048-cell snake: 0.186 ms per call
Normal: empty_cell with 1152-cell snake: 0.083 ms per call
Hard: empty_cell with 512-cell snake: 0.039 ms per call
```
Worst case ~0.19 ms per refill vs a 50–150 ms tick: no occupied-cell index added (not justified).

## Slice 4 — explicit pause reasons, timer ownership, step clock

RED:
```
ERROR: test_session (unittest.loader._FailedTest.test_session)
ImportError: Failed to import test module: test_session
ModuleNotFoundError: No module named 'omarchy_snake.session'
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN:
```
Ran 61 tests in 0.060s

FAILED (failures=1)
```

First run: 1 failure, float artefact `150.00000000009095 != 150` from the fake clock; assertion changed to assertAlmostEqual.
```
Ran 61 tests in 0.060s

OK
```

## Slice 5 — display fit / visual zoom model

RED:
```
ERROR: test_geometry (unittest.loader._FailedTest.test_geometry)
ImportError: Failed to import test module: test_geometry
ModuleNotFoundError: No module named 'omarchy_snake.geometry'
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN:
```
Ran 69 tests in 0.062s

OK
```

## Slice 6 — persistence

RED:
```
ERROR: test_preferences (unittest.loader._FailedTest.test_preferences)
ImportError: Failed to import test module: test_preferences
ImportError: cannot import name 'preferences' from 'omarchy_snake' (/home/bignutta/Work/omarchy-snake/omarchy_snake/__init__.py)
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN:
```
Ran 77 tests in 0.075s

OK
```

## Slice 7 — theme contrast, palette ordering and invalid hex

RED:
```
ERROR: test_contrast_ratio_matches_wcag (tests.test_omarchy_theme.ContrastTests.test_contrast_ratio_matches_wcag)
AttributeError: module 'omarchy_snake.theme' has no attribute 'contrast_ratio'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback) (theme='default-dark')
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback) (theme='catppuccin-latte')
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback) (theme='flexoki-light')
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback) (theme='rose-pine-dawn')
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback) (theme='low-contrast-dark')
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_general_ui_text_gets_a_readable_fallback (tests.test_omarchy_theme.ContrastTests.test_general_ui_text_gets_a_readable_fallback)
AttributeError: module 'omarchy_snake.theme' has no attribute 'readable_on'
ERROR: test_overlay_buttons_are_readable_under_light_and_dark_palettes (tests.test_omarchy_theme.ContrastTests.test_overlay_buttons_are_readable_under_light_and_dark_palettes) (theme='default-dark')
AttributeError: module 'omarchy_snake.theme' has no attribute 'overlay_button_colors'
ERROR: test_overlay_buttons_are_readable_under_light_and_dark_palettes (tests.test_omarchy_theme.ContrastTests.test_overlay_buttons_are_readable_under_light_and_dark_palettes) (theme='catppuccin-latte')
AttributeError: module 'omarchy_snake.theme' has no attribute 'overlay_button_colors'
ERROR: test_overlay_buttons_are_readable_under_light_and_dark_palettes (tests.test_omarchy_theme.ContrastTests.test_overlay_buttons_are_readable_under_light_and_dark_palettes) (theme='flexoki-light')
AttributeError: module 'omarchy_snake.theme' has no attribute 'overlay_button_colors'
ERROR: test_overlay_buttons_are_readable_under_light_and_dark_palettes (tests.test_omarchy_theme.ContrastTests.test_overlay_buttons_are_readable_under_light_and_dark_palettes) (theme='rose-pine-dawn')
AttributeError: module 'omarchy_snake.theme' has no attribute 'overlay_button_colors'
ERROR: test_overlay_buttons_are_readable_under_light_and_dark_palettes (tests.test_omarchy_theme.ContrastTests.test_overlay_buttons_are_readable_under_light_and_dark_palettes) (theme='low-contrast-dark')
AttributeError: module 'omarchy_snake.theme' has no attribute 'overlay_button_colors'
Ran 5 tests in 0.004s
FAILED (errors=12)
```

GREEN:
```
Ran 81 tests in 0.078s

OK
```

## Slice 8 — rendering shapes, tail visibility, HUD and explanatory text

RED:
```
ERROR: test_presentation (unittest.loader._FailedTest.test_presentation)
ImportError: Failed to import test module: test_presentation
ImportError: cannot import name 'text' from 'omarchy_snake' (/home/bignutta/Work/omarchy-snake/omarchy_snake/__init__.py)
FAIL: test_last_three_segments_fade_from_body_green_to_almost_black (tests.test_core_mechanics.CoreMechanicsTests.test_last_three_segments_fade_from_body_green_to_almost_black) (length=4)
AssertionError: 0.08600000000000001 not greater than 0.2
FAIL: test_last_three_segments_fade_from_body_green_to_almost_black (tests.test_core_mechanics.CoreMechanicsTests.test_last_three_segments_fade_from_body_green_to_almost_black) (length=6)
AssertionError: 0.08600000000000001 not greater than 0.2
FAIL: test_last_three_segments_fade_from_body_green_to_almost_black (tests.test_core_mechanics.CoreMechanicsTests.test_last_three_segments_fade_from_body_green_to_almost_black) (length=12)
AssertionError: 0.08600000000000001 not greater than 0.2
Ran 7 tests in 0.016s
FAILED (failures=3, errors=1)
```

GREEN:
```
Ran 88 tests in 0.081s

OK
```

## Slice 9 — safe optional logging

RED:
```
ERROR: test_logging (unittest.loader._FailedTest.test_logging)
ImportError: Failed to import test module: test_logging
ModuleNotFoundError: No module named 'omarchy_snake.log'
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN:
```
Ran 92 tests in 0.083s

OK
```

## Slice 10 — session shutdown for window close

RED:
```
ERROR: test_stop_removes_timer_and_blocks_restart_until_new_game (tests.test_session.PauseReasonTests.test_stop_removes_timer_and_blocks_restart_until_new_game)
AttributeError: 'GameSession' object has no attribute 'stop'
Ran 19 tests in 0.012s
FAILED (errors=1)
```

GREEN:
```
Ran 93 tests in 0.083s

OK
```

## Slice 11 — status wording distinguishes manual pause from menu/dialog pause

RED:
```
ERROR: test_states_are_named_not_only_coloured (tests.test_presentation.TextTests.test_states_are_named_not_only_coloured)
TypeError: status_text() got an unexpected keyword argument 'manual'
Ran 7 tests in 0.006s
FAILED (errors=1)
```

GREEN:
```
Ran 93 tests in 0.084s

OK
```

## Slice 12 — debounce focus loss (native finding: popover opening blips is-active False→True)

Native diagnostic samples (scratch script, two runs): `[before True] [notify False, popover open] [notify True, popover open] ...` — every Menu click would have become a sticky manual pause.

RED:
```
ERROR: test_session (unittest.loader._FailedTest.test_session)
ImportError: Failed to import test module: test_session
ImportError: cannot import name 'FOCUS_LOSS_CONFIRM_MS' from 'omarchy_snake.session' (/home/bignutta/Work/omarchy-snake/omarchy_snake/session.py)
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN:
```
Ran 94 tests in 0.086s

OK
```

## Slice 13 — chrome re-measured after each refit (native finding: fit_monitor_change)

Final-review fixes already in place before this slice (best-score retry on finish/New Game/close, timer re-entrancy from the step listener, MonitorWatch enter/leave/hotplug/property refit): covered by `test_app_controller.BestScoreRetryTests`, `test_preferences` retry tests, `test_session` listener re-entrancy tests and `test_monitor`; all pass in the suite below.

Native failure (`/usr/bin/python tests/native_fit_check.py`, before this slice):
```
  "native_check": "fit_monitor_change",
  "failures": [
    "timed out after 3000 ms waiting for: refit to 15px within (1240, 648)"
  ],
```
Diagnosis from a throwaway probe outside the repo (Hard, controlled 1280×720 logical monitor):
```
before refit: fit 16px frame 524, chrome (137, 139), window (661, 663), content (629, 584), board-info 18 px
after refit:  fit 15px frame 492, chrome (137, 139), window (661, 649), content (629, 570), board-info 36 px
```
The model fit 15 px using the chrome measured at map time: 492 + 139 = 631 ≤ 648. Then the reduced board added "· reduced to fit screen" to the board-info line, which wrapped it from 18 to 36 px. The real chrome became 157 and the window 649 > 648. Chrome was only measured once, on map. Horizontal chrome was also wrong: it counted the header-driven centring slack (137 here, 265 at 2×1080p) as chrome, so continual re-measuring could have ratcheted cells down on narrow screens.

RED (`/usr/bin/python -m unittest tests.test_app_controller -v`):
```
test_apply_fit_measures_chrome_again_after_the_next_layout ... FAIL
test_close_cancels_a_pending_chrome_measurement ... FAIL
test_footer_rewrapped_by_refit_is_measured_and_refitted ... FAIL
test_header_wider_than_board_is_not_horizontal_chrome ... FAIL
test_leftover_height_below_the_footer_is_not_chrome ... FAIL
AssertionError: Expected 'connect' to have been called once. Called 0 times.
AssertionError: Expected 'disconnect' to be called once. Called 0 times.
AssertionError: Tuples differ: (169, 157) != (32, 157)
AssertionError: Tuples differ: (137, 139) != (32, 139)
AssertionError: Tuples differ: (201, 203) != (32, 157)
Ran 12 tests in 0.026s
FAILED (failures=5)
```
Fix (`omarchy_snake/app.py`): `measured_chrome()` returns width = window − content (margins only) and height = header + margins + footer rows (excluding leftover below them). `apply_fit` schedules one `after-paint` re-measure (`measure_chrome_after_layout`); `measure_chrome` refits only when the chrome changed. `on_close` cancels a pending re-measure. The native check now waits for a settled fit instead of a 15 px value derived from the stale chrome: chrome equal to a fresh measurement of the real allocation, cell size equal to `fit_board` for that chrome, the window inside the usable area, the cell still below 16 px, and close leaving no pending re-measure. The simulated phases also assert chrome = fresh measurement.

GREEN:
```
Ran 12 tests in 0.024s
OK
```
`native_fit_check.py`, fit_monitor_change artifacts:
```
"enter_monitor_1280x720": {"cell_pixels": 14, "chrome": [32, 157], "window": [661, 617], "usable": [1240, 648]}
"geometry_960x540": {"cell_pixels": 9, "chrome": [32, 139], "window": [661, 439], "usable": [920, 468]}
"apply_fit_usable_areas": [[1240, 648], [1240, 648], [920, 468], [920, 468], [2520, 1368], [920, 468]]
```
(One extra refit per monitor change from the chrome re-measure, then stable; no loop.)

## Native GTK checks (sequential, isolated app IDs and temp config/state; Hyprland 2× 2560×1440 @1)

During development each native check first failed on test-fixture expectations, which were corrected (see the session notes in the final report). The real app bugs found natively were the popover focus blip (Slice 12) and stale screenshot timing.

Final sequential sweep:
```
native_pause_check.py: exit 0, 12 checks passed, 0 failures
native_fit_check.py: exit 0, 7 checks passed, 0 failures
native_ui_check.py: exit 0, 14 checks passed, 0 failures
native_game_over_check.py: exit 0, 5 checks passed, 0 failures
native_hard_check.py: exit 0, 6 checks passed, 0 failures
native_relaunch_check.py: exit 0, 1 checks passed, 0 failures
native_pause_check.py focus sections in that sweep: skipped (desktop held focus: Hyprland follow_mouse, pointer outside window)
native_pause_check.py immediate rerun: exit 0, 16 checks passed, 0 failures
```

Sweep after Slice 13 (same order, one at a time; every run 0 visible windows after exit, app exit 0):
```
native_pause_check.py: exit 0, 16 checks passed, 0 failures (focus sections ran, none skipped)
native_fit_check.py: exit 0, 12 checks passed, 0 failures (fit_real 4, fit_1080p 1, fit_2x1080p 2, fit_monitor_change 5)
native_ui_check.py: exit 0, 14 checks passed, 0 failures (ui 13, ui_relaunch 1)
native_game_over_check.py: exit 0, 5 checks passed, 0 failures
native_hard_check.py: exit 0, 6 checks passed, 0 failures
native_relaunch_check.py: exit 0, 1 checks passed, 0 failures
```
Allocated chrome is now [32, 139] in fit_1080p and fit_2x1080p (previously [265, 139] at 2×1080p from header slack); cell sizes are unchanged (13 px, 6 px with scroll).

Measured artifacts:
```
    "floor_cadence_ms": {
      "mean": 50.1,
      "min": 50.0,
      "max": 50.2,
      "samples": 20
    },
    "light_theme_button": {
      "foreground": "#f2f2f2",
      "background": "#050505",
      "contrast": 18.21
    },
    "real_monitor": {
      "name": "DP-1",
      "mode": [
        2560,
        1440
      ],
      "scale": 1,
      "window_at": [
        746,
        146
      ],
      "window_size": [
        1068,
        1175
      ],
      "chrome": [
        32,
        139
      ]
    },
    "hard_auto_cell_pixels": 38,
```

## Final headless suite

`/usr/bin/python -m unittest discover -s tests -v`
```
----------------------------------------------------------------------
Ran 94 tests in 0.089s

OK
```

After Slice 13 (includes the final-review retry, re-entrancy and monitor tests):
```
----------------------------------------------------------------------
Ran 120 tests in 0.125s

OK
```

---

# Test log — two-stage New Game (2026-11-01, NEW_GAME_FLOW_BRIEF.md)

Baseline before any change: `/usr/bin/python -m unittest discover -s tests`
```
Ran 120 tests in 0.122s

OK
```

## Slice A — chooser page model and Escape hierarchy (`omarchy_snake/chooser.py`, `escape_action`)

RED: `/usr/bin/python -m unittest tests.test_new_game_chooser tests.test_session` (grep of ERROR/FAIL/summary lines)
```
ERROR: test_new_game_chooser (unittest.loader._FailedTest.test_new_game_chooser)
ImportError: Failed to import test module: test_new_game_chooser
ModuleNotFoundError: No module named 'omarchy_snake.chooser'
ERROR: test_escape_on_the_details_page_goes_back_before_closing (tests.test_session.EscapeHierarchyTests.test_escape_on_the_details_page_goes_back_before_closing)
TypeError: escape_action() got an unexpected keyword argument 'chooser_details'
Ran 29 tests in 0.019s
FAILED (errors=2)
```

GREEN:
```
Ran 40 tests in 0.019s

OK
```

## Slice B — controller wiring (choose previews, Back, Start once, Escape, held keys, focus loss)

First RED run failed for all 18 tests at the fixture (`app.NewGameChooser` missing), which hid the
behaviour under test; the fixture was changed to import the model from `omarchy_snake.chooser`.
RED after that: `/usr/bin/python -m unittest tests.test_app_controller`
```
ERROR: test_choosing_and_back_never_reset_or_save (tests.test_app_controller.NewGameFlowTests.test_choosing_and_back_never_reset_or_save)
AttributeError: 'SnakeWindow' object has no attribute 'choose_difficulty'. Did you mean: 'cancel_difficulty'?
ERROR: test_escape_goes_back_from_details_then_cancels_from_choices (tests.test_app_controller.NewGameFlowTests.test_escape_goes_back_from_details_then_cancels_from_choices)
AttributeError: 'SnakeWindow' object has no attribute 'choose_difficulty'. Did you mean: 'cancel_difficulty'?
ERROR: test_focus_loss_forgets_a_held_key (tests.test_app_controller.NewGameFlowTests.test_focus_loss_forgets_a_held_key)
AttributeError: 'SnakeWindow' object has no attribute 'choose_difficulty'. Did you mean: 'cancel_difficulty'?
ERROR: test_held_enter_that_chose_cannot_reach_start_until_released (tests.test_app_controller.NewGameFlowTests.test_held_enter_that_chose_cannot_reach_start_until_released)
AttributeError: 'SnakeWindow' object has no attribute 'choose_difficulty'. Did you mean: 'cancel_difficulty'?
ERROR: test_start_commits_the_selected_difficulty_exactly_once (tests.test_app_controller.NewGameFlowTests.test_start_commits_the_selected_difficulty_exactly_once)
AttributeError: 'SnakeWindow' object has no attribute 'choose_difficulty'. Did you mean: 'cancel_difficulty'?
FAIL: test_opening_pauses_for_the_chooser_on_its_choices_page (tests.test_app_controller.NewGameFlowTests.test_opening_pauses_for_the_chooser_on_its_choices_page)
AssertionError: None != 'choices'
Ran 18 tests in 0.037s
FAILED (failures=1, errors=5)
```

GREEN:
```
Ran 18 tests in 0.037s
OK
```

Full suite after slice B:
```
Ran 139 tests in 0.137s

OK
```

## Native — new `tests/native_chooser_check.py`

Two failing runs were harness errors, not app defects, fixed in the check:
1. `assert w['difficulty-details-page'].get_visible() ...` failed right after `Gtk.Button.activate()`:
   a GTK 4 button emits `clicked` about 250 ms after keyboard activation. The check now waits for the page.
2. `assert c.window.get_focus().activate()` failed for an Enter after Start: focus had correctly
   returned to the board, which has nothing to activate. The check now asserts exactly that.

## Native GTK checks (sequential, isolated app IDs and temp config/state; Hyprland 2× 2560×1440 @1)

Headless first: `Ran 139 tests in 0.141s` / `OK`. Then each script in turn (summary lines extracted from each JSON report):
```
=== native_chooser_check exit=0
chooser checks=9 failures=0 visible_windows_after_exit=0 app_exit=0
   {"choices_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-chooser-choices.png", "details_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-chooser-details.png"}
=== native_pause_check exit=0
pause checks=16 failures=0 visible_windows_after_exit=0 app_exit=0
   {"paused_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-paused.png"}
=== native_ui_check exit=0
ui checks=13 failures=0 visible_windows_after_exit=0 app_exit=0
   {"options_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-options.png"}
ui_relaunch checks=1 failures=0 visible_windows_after_exit=0 app_exit=0
=== native_game_over_check exit=0
game_over checks=5 failures=0 visible_windows_after_exit=0 app_exit=0
   {"game_over_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-game-over-light-theme.png", "victory_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-victory.png"}
=== native_hard_check exit=0
hard checks=6 failures=0 visible_windows_after_exit=0 app_exit=0
   {"hard_screenshot": "/run/user/1000/omarchy-snake-checks/omarchy-snake-hard-game-over.png"}
=== native_fit_check exit=0
fit_real checks=4 failures=0 visible_windows_after_exit=0 app_exit=0
fit_1080p checks=1 failures=0 visible_windows_after_exit=0 app_exit=0
fit_2x1080p checks=2 failures=0 visible_windows_after_exit=0 app_exit=0
fit_monitor_change checks=5 failures=0 visible_windows_after_exit=0 app_exit=0
=== native_relaunch_check exit=0
relaunch checks=1 failures=0 visible_windows_after_exit=0 app_exit=0
```
Chooser check names: launch_opens_choices_page_with_only_three_difficulties, choices_page_focus_trap,
enter_previews_details_and_repeat_cannot_start, details_page_focus_trap,
escape_steps_back_then_cancels_without_reset, mid_run_preview_back_escape_keep_run,
start_resets_exactly_once_into_chosen_mode, paused_new_game_preview_keeps_manual_pause_start_clears_it,
game_over_preview_and_held_space_keep_loss.

Limitation: key presses in the native checks go through the window's real capture handler and then
`Gtk.Widget.activate()` on the focused button; they are not compositor-level key events, so real
key auto-repeat timing is not exercised.
