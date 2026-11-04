# Omarchy Snake

**Version 0.0001 — Initial Public offering**

First public source release. See [CHANGELOG.md](CHANGELOG.md) for release notes. This is a source checkout, not an Omarchy Hub package or one-click installer.

A native, offline Snake game built for Linux with Python, GTK4, PyGObject and Cairo. It opens in its own desktop window: no browser, web server, game account, AI service or remote assets are needed to play.

Launch it with **`grid_preview.py`** (historical name, kept as the stable launcher). The game itself lives in the `omarchy_snake/` package:

| Module | Responsibility |
| --- | --- |
| `rules.py` | Board presets, movement, two-deep turn queue, rewards, scoring, loss and victory |
| `session.py` | Pause reasons, the single movement timer, step clock, Escape hierarchy |
| `geometry.py` | Display fit and visual zoom (rendered cell size only) |
| `preferences.py` | Versioned JSON settings and best scores |
| `theme.py` / `drawing.py` / `text.py` | Omarchy palette and contrast, Cairo rendering, player-facing text |
| `log.py` | Optional `--verbose` / `--debug` diagnostics |
| `synth.py` | Original arcade sounds and melody, computed from note tables |
| `audio.py` | What should sound and when, from game events and settings; needs no audio libraries |
| `gst_audio.py` | Optional GStreamer playback, loaded only if available |
| `app.py` | GTK4 window and controller |

`grid_preview.py` still re-exports the older public names (`MovementPreview`, `draw_board_border`, constants) for existing tools and tests.

## Download and run

Clone the public repository with Git:

```bash
git clone https://github.com/KirkShader/omarchy-snake.git
cd omarchy-snake
git checkout v0.0001
```

The tag selects this exact release. Omit the checkout command to use the latest default-branch source. Cloning this public repository does not require a GitHub account.

On Omarchy/Arch Linux, the game uses these packages. If they are missing, this command installs them; review it before running:

```bash
sudo pacman -S --needed python python-gobject python-cairo gtk4
```

Use the **system Python**, which has access to the distribution's GTK bindings:

```bash
/usr/bin/python grid_preview.py --show-difficulty
```

The New Game chooser opens before the snake makes its first move. It has two pages:

1. **Easy / Normal / Hard** only. Choosing one just shows its details; nothing is reset.
2. That difficulty's rules, with **Back** and **Start**. Only **Start** resets the run and begins the chosen difficulty.

**Esc** on the details page goes back to the choices; Esc on the choices page cancels and returns to the current run, which at launch is a fresh Easy run. The run stays paused on both pages. Enter or Space that opened the chooser or changed its page must be released before the new page's buttons respond, so holding a key cannot run on into Start. Menu → New Game, the Paused, Game Over and Victory cards' New Game buttons, and `--show-difficulty` all use this flow.

Then use the **arrow keys** to steer. Two quick turns can be queued, for example Up then Left. **Esc** pauses and resumes. Menu provides **New Game**, **Pause**, **Options** and **Quit**.

Running the launcher again while the game is open brings the existing window to the front instead of opening a second game.

You can also run without opening the chooser first:

```bash
/usr/bin/python grid_preview.py
```

## Current rules

| Setting | Easy | Normal | Hard |
| --- | --- | --- | --- |
| Board | 64 × 64 cells | 48 × 48 cells | 32 × 32 cells |
| Playing area | 1024 × 1024 pixels | 768 × 768 pixels | 512 × 512 pixels |
| Cell size | 16 pixels | 16 pixels | 16 pixels |
| Initial snake length | 6 | 6 | 6 |
| Orange dots available | 5 | 5 | 10 |
| Outer edges | Wrap around | Wrap around | Solid walls: game over |
| Self-collision | Fatal from length 10 | Fatal from length 10 | Fatal from the start |
| Initial time per cell | 0.150 seconds | 0.150 seconds | 0.150 seconds |
| Speed change per orange | None | None | Reduce time per cell by 0.0023 seconds, to a 0.050-second minimum |

- An orange dot (round ●) gives **one point and one extra body square**, then respawns in a free cell. When the board is nearly full, only as many oranges as there are free cells are shown.
- At a current length of at least six, one green dot (diamond ◆) can appear after a **30-second eligible-play cooldown**. Collecting it removes **two squares** without changing score or undoing Hard-mode acceleration. A fresh cooldown then starts. If the cooldown completes while no cell is free, the dot appears as soon as one opens.
- Turns are checked against the last queued direction. A reversal, a repeat, or a third queued turn is ignored, and each step applies only one turn, so the snake never makes a one-step U-turn. Entering a tail cell that vacates on the same non-growing step is safe.
- **Hard pace (approved 2026-10-31):** the same linear curve, 150 ms − 2.3 ms per orange, with a **50 ms floor**, reached at 44 points. The change is gradual, with no sudden jump. Green dots never undo speed, and New Game resets it to 150 ms. GTK schedules rounded whole-millisecond delays; the footer shows the nominal interval.
- **Victory:** when the snake covers every cell (unique cells), the last orange scores its point, a gold **★ Victory!** card appears, and movement stops. Free cells that hold food do not count as covered.
- **Game over:** the board frame and grid become **#FF3333**, with a centred **Game Over** card showing the reason, Score, Length and Best. Cancelling the restart chooser (Esc) restores that card.
- Paused, game over and victory are each named in text, not shown by colour alone.
- The header shows **Score · Length · Best** (best for the current difficulty).
- Options changes frame/grid colours and **board zoom**. The exact game-over red is rejected with an explanation.
- The surrounding UI follows the active Omarchy palette when available, with readable fallbacks for light themes.

## Pausing

| Situation | Result |
| --- | --- |
| **Esc** or Menu → Pause | Manual pause: **Paused** card with Resume / New Game. Board and green cooldown freeze. |
| Menu open, colour chooser open, difficulty chooser open | Paused only while open. Closing it never resumes a manual pause. The colour chooser keeps the game paused even if the menu closes. |
| Window loses focus | Freezes at once. If focus is still gone after 0.3 s, the manual pause engages. Regaining focus does **not** resume, so press Esc or Resume. The short delay ignores the brief blip GTK reports while the menu opens. |
| After game over or victory | Pause is unavailable; use New Game. |

Esc closes the innermost surface first: the chooser's details page (back to the choices), the chooser, then the menu, then it toggles the manual pause. When resuming, the paused time is never counted, and there is no catch-up movement. If the event loop stalls, the green cooldown is credited at most two step intervals for that callback, and the snake still moves only one cell per callback.

While a card or chooser is open, it is modal. The header Menu and board are disabled. Tab, Shift+Tab and the arrow keys move only between the card's buttons (on each chooser page, only that page's buttons). When the card closes, focus returns to where it was. Arrow keys never steer while paused.

## Sound

| Event | Sound |
| --- | --- |
| Orange collected | Short bright beep |
| Green collected | Two descending notes |
| New game actually starts (Start, or launching straight into a run) | Quick three rising notes; never on previewing, Back or cancelling |
| Game over | Low descending buzz |
| Victory | Short jingle (the last orange plays only this, not its beep as well) |
| Active play | A quiet looping melody, one note at a time |

Movement itself makes no sound. The melody plays only while the run is actually moving: not behind the launch chooser, during any pause, or after game over or victory. A pause keeps its place in the melody, and a new run starts it from the top. Any pause reason also cuts a sound that is still playing.

Menu → Options has **Music** and **Sound Effects** switches and a **Volume** slider (default 30%, with music mixed quieter than effects). They work from the keyboard (Tab to reach them; Space or Enter for the switches; arrow keys for the slider), apply at once and are saved. Volume 0 silences both, and a channel you turned off stays off through pause, resume and New Game. Options already pauses the game, so you hear a change when you return to play.

**Where the sounds come from:** every sound is original and generated by the small program in `omarchy_snake/synth.py` when the game starts: square, triangle and saw waves from note tables written for this project, the same every time. There are no samples, recordings, downloads, bundled codecs or network use.

**What audio needs:** GStreamer 1.x and its Python (GObject) bindings, the `appsrc`, `volume`, `audioconvert` and `audioresample` elements, and one of `pipewiresink`, `pulsesink`, `autoaudiosink` or `alsasink`, tried in that order. On Arch/Omarchy these normally come from `gstreamer`, `gst-plugins-base` and `gst-plugin-pipewire` (package names are not checked by any test); this project does not install them. If any of it is missing, or no sink can connect, the game plays silently and normally. Run with `--verbose` to see why (`audio_unavailable`), or to see runtime errors (`audio_error`, at most three per channel, then `audio_channel_disabled`).

## Display fit and zoom

Cell **counts** never change (64/48/32). Only the rendered cell size changes, always in whole pixels so grid lines stay sharp. The default is **100% (16 logical px)**. If a board would not fit the monitor's usable logical area (GDK geometry minus a 40 × 72 px allowance for bars and gaps), the cells shrink to the largest size that fits. Options → Board zoom offers **Auto fit** (largest whole cell that fits), 50%, 75%, 100%, 125%, 150% and 200%; requests that are too large are limited to fit. Below 6 px per cell, the board stays at 6 px and scrolls, keeping the snake's head in view. The header and footer are measured from the real window, again after every refit (a reduced board can wrap the info line). Your monitor settings are never changed.

## Saved data

| File | Contents |
| --- | --- |
| `$XDG_CONFIG_HOME/omarchy-snake/settings.json` (default `~/.config/…`) | Version, border and grid colours, zoom, music and effects switches, master volume |
| `$XDG_STATE_HOME/omarchy-snake/scores.json` (default `~/.local/state/…`) | Version, best score per difficulty |

Files are written atomically with ordinary `0644` permissions. Missing, corrupted, unknown-version or out-of-range values fall back to defaults field by field, and the reserved red is never loaded or saved. If a write fails, it is logged (with `--verbose`) and play continues. The current run itself is not saved. `--config-dir` and `--state-dir` override the locations.

## Command-line options

`--show-difficulty`, `--show-menu`, `--show-options`, `--geometry-report PATH` (JSON layout and state), `--verbose` (event log as JSON lines), `--debug` (also every move, with full segments), `--application-id` (tests use their own), `--config-dir`, `--state-dir`, and `--fit-limit WxH` (fit into a pretend usable area, for testing). Normal play prints nothing. If the log output closes, logging stops without affecting the game.

## Tests

Run the automated suite without opening the GUI:

```bash
/usr/bin/python -m unittest discover -s tests -v
```

Additional native checks are separate launchers:

```bash
/usr/bin/python tests/native_chooser_check.py   # two-page New Game: preview, Back/Esc, Start once, held keys
/usr/bin/python tests/native_pause_check.py     # pause reasons, launch chooser, colour dialog, focus
/usr/bin/python tests/native_fit_check.py       # real allocation on this monitor + simulated 1080p / 2x
/usr/bin/python tests/native_ui_check.py        # modal keyboard, presets, HUD, Options, persistence
/usr/bin/python tests/native_game_over_check.py # loss vs victory, light-theme contrast
/usr/bin/python tests/native_hard_check.py      # acceleration, measured 50 ms floor cadence, walls
/usr/bin/python tests/native_relaunch_check.py  # second launch refocuses the running window
/usr/bin/python tests/native_audio_check.py     # real PipeWire audio: PLAYS SOUND, records its own streams
```

The app's sounds are on during every native check, so expect to hear them. Run native checks **one at a time**. Each one uses its own application ID and temporary settings/state, so it never attaches to your game or touches your saved data, and it closes its window when done. Screenshots need Hyprland and `grim`. They are written to `$OMARCHY_SNAKE_SCRATCH`, or else `$XDG_RUNTIME_DIR/omarchy-snake-checks`, or else the system temp directory. Keyboard input is sent through the window's real key handler; GTK4 cannot inject OS-level key presses. With Hyprland's focus-follows-mouse, the real-focus sections report "skipped" if the desktop keeps focus. `TEST_LOG.md` records the test-first history and results.

## What this backup includes

- Game source and tests.
- This restore/run guide.
- `APPROVALS.md`: the current approved behaviour and working agreement.
- `IDEAS.md`: completed notes and explicitly unimplemented ideas.
- `TEST_LOG.md`: test-first (red → green) history and test results for the 2026-10-31 polish.
- `AUDIO_TEST_LOG.md`: the same for the sound slice, including what real PipeWire measurements found.
- `PLAN.md`: the archived original proposal, **not** the current implementation or permission to start specialist bots.

This is a source backup, not a packaged installer. It does **not** install a launcher/icon, restore Hyprland configuration (including any app-specific opacity rule, which matches the unchanged application ID `local.omarchy.snake.preview`), or include dependencies, recordings, credentials, AI accounts or the rest of the Linux installation. Saved colours, zoom and best scores live in your XDG directories, not in this repository.

Do not wipe either drive until the remote backup has been verified and any other important files have a separate backup.
