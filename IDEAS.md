# Snake — ideas to revisit

## Game-over presentation — implemented

The user resumed work and explicitly approved implementing these changes.

Requested changes:
- On self-collision, turn the board border and grid lines red.
- Show a large, centred “Game Over” box.
- Put a “New Game” button beneath it, using the existing difficulty chooser when restarting.
- Reserve the red used for game over: prevent selecting that colour in Options.

Implemented warning red: #FF3333. That exact shade is rejected by both Options pickers, with a visible explanation and restoration of the previous colour. Other colours remain available. The warning overrides rendering temporarily and does not overwrite the player's ordinary colour choices.

The centered New Game button opens the existing difficulty chooser. Cancel returns to the Game Over view; choosing a difficulty resets the run and restores the selected colours.

## Difficulty through playing-area size

Historical proposal below; the later approved fixed 16-pixel cells and Easy/Normal/Hard presets in APPROVALS.md supersede its older preview dimensions. Do not treat the archived numbers as current requirements.

User's tentative idea, saved for later discussion, not approved for implementation:

- Offer different board sizes as a difficulty setting.
- Keep cells at the current 32 × 32 pixels rather than enlarging the same number of cells.
- Explore a board up to 2048 × 2048 pixels, which would contain 64 × 64 cells (4096 total).
- Current preview remains a 512 × 512 playing area with 16 × 16 cells.
- Discuss how board size affects difficulty rather than assuming larger means harder; extra space may make avoiding collisions easier while tokens can be farther away.
- Consider display fit before implementation: the previously inspected monitors are 2560 × 1440, so a 2048-pixel-tall board would not fit at full size. Decide later whether to use smaller presets, a viewport, or another explicitly approved presentation.

No game behavior, preview dimensions or desktop settings were changed to implement this idea.

## Joint-review polish — implemented 2026-10-31

Approved by the user and implemented (see APPROVALS.md and TEST_LOG.md):
- Explicit pause state with separate reasons, a Paused card, Escape hierarchy and focus-loss policy.
- Display fit and visual zoom (Auto fit, 50–200%), with a scroll fallback below 6 px cells.
- Balanced Hard with a 50 ms floor.
- Victory state on a fully covered board; partial or failed food refills; a due green dot waits for space.
- Readable overlay buttons in light themes; green diamond; brighter tail tip; Score · Length · Best; chooser explanations; modal keyboard focus trap.
- Two-deep safe turn queue.
- Persistent per-difficulty best scores and appearance/zoom (versioned XDG JSON).
- Module split behind the `grid_preview.py` façade; optional safe logging; second-launch refocus; isolated native checks.

Profiled and deliberately **not** done: an occupied-cell index for food spawning. The worst case is about 0.19 ms per refill against a 50–150 ms tick.

## Future ideas — not approved, not implemented

- A user setting to turn off pause-on-focus-loss (Hyprland focus-follows-mouse pauses the game whenever the pointer leaves the window).
- Resizable/tiled window mode. The window stays fixed-size so Hyprland floats it as before; Auto fit currently uses the monitor size, not a tiled allocation.
- Detecting the real Hyprland reserved areas and gaps instead of the fixed 40 × 72 logical-px allowance.
- Physical multi-monitor and HiDPI verification. HiDPI and 1080p are covered by geometry models and `--fit-limit` simulation only; the tested machine has two 2560 × 1440 @1 monitors.
- Best-run summary/history, or saving a run in progress.
- Alternative key bindings (WASD/HJKL).
- A short preview sound when moving the Volume slider. Options pauses the game and pause silences everything, so a volume change is only heard after returning to play.

## Sound — implemented 2026-11-04

Approved by the user and implemented (see APPROVALS.md, README.md and AUDIO_TEST_LOG.md). Listening quality awaits the user's evaluation.
