# Omarchy Snake

A native, offline Snake game built for Linux with Python, GTK4, PyGObject and Cairo. It opens in its own desktop window: no browser, web server, game account, AI service or remote assets are needed to play.

The application is currently in **`grid_preview.py`**. Its filename is historical; it contains the playable game.

## Restore after reinstalling Linux

Keep access to the GitHub account that owns this private repository. With Git and GitHub CLI (`gh`) installed, sign in and clone your backup:

```bash
gh auth login --hostname github.com --git-protocol https --web
mkdir -p ~/projects
gh repo clone omarchy-snake ~/projects/omarchy-snake
cd ~/projects/omarchy-snake
```

The repository shorthand above uses the signed-in GitHub account. If using another account, include the owner's name before `/omarchy-snake`.

On Omarchy/Arch Linux, the game uses these packages. If they are missing, this command installs them; review it before running:

```bash
sudo pacman -S --needed python python-gobject python-cairo gtk4
```

Use the **system Python**, which has access to the distribution's GTK bindings:

```bash
/usr/bin/python grid_preview.py --show-difficulty
```

Choose a difficulty, then use the **arrow keys** to steer. Menu provides **New Game**, **Options** and **Quit**. New Game opens a difficulty chooser; Cancel returns to the existing run. The chooser pauses movement and the green-dot cooldown.

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
| Speed change per orange | None | None | Reduce time per cell by 0.0023 seconds |

- An orange dot gives **one point and one extra body square**, then respawns in a free cell.
- At a current length of at least six, one green dot can appear after a **30-second eligible-play cooldown**. Collecting it removes **two squares** without changing score or undoing Hard-mode acceleration. A fresh cooldown then starts.
- Immediate reverse turns are ignored. Entering a tail cell that vacates on the same non-growing step is safe.
- Hard speed resets with each new run. A **1 ms technical minimum** prevents zero/negative timer delays; the proposed 0.050-second gameplay cap was not adopted. GTK schedules rounded whole-millisecond delays; the footer shows the nominal configured interval.
- On game over, the board frame and grid become **#FF3333**, with a centred **Game Over** box and **New Game** button. Cancel in the restart chooser restores that view.
- Options changes the normal frame/grid colours. The exact game-over red is rejected with an explanation; ordinary choices return on a new run.
- The surrounding UI follows the active Omarchy palette when available, with fallback colours elsewhere.

## Tests

Run the automated suite without opening the GUI:

```bash
/usr/bin/python -m unittest discover -s tests -v
```

Additional native checks are separate launchers:

```bash
/usr/bin/python tests/native_ui_check.py
/usr/bin/python tests/native_game_over_check.py
/usr/bin/python tests/native_hard_check.py
```

Run native checks **one at a time, with the ordinary game closed**. They open actual GTK windows and use controlled game fixtures, real actions and GLib timers. Some require a running Hyprland session and `grim` for screenshots. Generated captures go to the scratch directory, not into this backup.

## What this backup includes

- Game source and tests.
- This restore/run guide.
- `APPROVALS.md`: the current approved behaviour and working agreement.
- `IDEAS.md`: completed notes and explicitly unimplemented ideas.
- `PLAN.md`: the archived original proposal, **not** the current implementation or permission to start specialist bots.

This is a source backup, not a packaged installer. It does **not** install a launcher/icon, restore Hyprland configuration (including any app-specific opacity rule), or include dependencies, recordings, credentials, AI accounts or the rest of the Linux installation. Colour selections are session-only; scores are not saved between runs.

Do not wipe either drive until the remote backup has been verified and any other important files have a separate backup.
