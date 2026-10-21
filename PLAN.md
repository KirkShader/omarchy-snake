# Omarchy Snake — original planning archive

> Historical proposal only. The current GTK implementation, rules and permissions are described in README.md and APPROVALS.md. The old stack, authentication notes and proposed bot workflow below are not current instructions or permission to start specialist bots.

## Status and permission boundary

**Current state: setup and planning complete; first pass NOT approved.**

The user approved creating the bots and writing this plan. No game code, tests, game dependency installation, launcher, or desktop configuration changes are authorized yet. This plan is a proposal, not permission to execute it. See APPROVALS.md. Existing default-profile Hermes is the coordinator; there are three additional persistent specialist profiles, not four new profiles.

## 1. Confirmed requirements

- A genuine desktop application in its own window, not a browser game, webview, Electron wrapper, or localhost website.
- Completely offline gameplay: no account, authentication, server, telemetry, online assets, runtime downloads, or network calls.
- A snake moves around a board.
- Arrow keys turn it up, down, left, and right.
- Collectible tokens make the snake grow.
- Integration into the user's Omarchy desktop after a separate installation approval.
- Run proposed phases through the user before proceeding.

“Integrated” means a user-local installed application reachable through the app launcher. It does not mean modifying the upstream Omarchy distribution or its packaged files. Development bots may need an online model connection; the finished game must not.

## 2. Team and ownership

| Bot/profile | Responsibility | Assigned skills |
| --- | --- | --- |
| Existing Hermes / default | Coordinator: maintain agreed scope, present checkpoints, review evidence, resolve handoffs | hermes-agent, omarchy, requesting-code-review |
| snake-builder / Snake Builder | Native window, game rules, developer-authored tests | test-driven-development, systematic-debugging; hermes-agent also available |
| snake-tester / Snake Tester | Independent acceptance tests, native GUI checks, code review and defect report | test-driven-development, systematic-debugging, requesting-code-review, computer-use; hermes-agent also available |
| snake-integrator / Snake Integrator | User-local packaging, launcher/icon, installation and uninstall verification | omarchy, test-driven-development, systematic-debugging; hermes-agent also available |

All specialist SOUL.md files explicitly prohibit implementation or autonomous handoffs until user approval. Skills are installed in each profile. Browser-only p5js/dogfood skills are not assigned because this is a native application.

### Authentication blocker

The specialist profiles are pinned to the same model/provider as the coordinator: gpt-6.1-sol / openai-codex. They have no profile-local OAuth login yet. Hermes documentation requires separate OAuth sign-in for each profile; existing OAuth credentials were not copied. Complete supported per-profile sign-in before dispatching work. No LLM task or authentication smoke test has been run for the new bots. Profile existence is not proof of inference readiness.

## 3. Proposed first-pass implementation

Use **Python 3 + Tkinter Canvas**. Tkinter was found on both available Python interpreters during setup; that was only an import-availability check, not a successful graphical window test. Use the verified system interpreter for the final launcher if the native GUI probe succeeds.

Reasons: a real desktop window, a small dependency surface, no browser/server, no external image/font requirements, and game logic can use Python's built-in unittest. The integrator must validate actual window creation on this Omarchy session, including any XWayland dependency. Native Wayland support is not claimed. If Tk fails or is unsuitable, stop and present an alternative (such as pygame-ce) and its dependency/install implications before proceeding. Do not silently change the stack or install packages.

Separate concerns:
- `model.py`: grid positions, movement, token placement, collision detection, score and game state; no GUI, filesystem or networking imports.
- `app.py`: Tk window/Canvas, keyboard mapping, one scheduled movement callback, display of model state, pause/restart/close behavior.
- `storage.py`: small local high-score file, defensive parsing and nonfatal I/O failure handling.
- Integration assets are generated as project-local templates before any actual installation.

### Proposed gameplay defaults (subject to approval)

- A 30-column by 20-row rectangular grid and an initial snake length of three cells.
- A clear dark board, contrasting snake, and visibly distinct token; text explains controls.
- Start/ready screen; Enter starts a run. Initial movement is rightward.
- Up/Down/Left/Right set the requested direction. Immediate 180-degree reversal is ignored once the snake is moving.
- A small bounded turn queue accepts at most two pending legal turns, evaluated against the last queued direction; consume at most one turn per movement step. Ignore key-repeat duplicates so rapid input cannot reverse the snake within one step.
- Fixed movement speed for the first pass. No difficulty selector, acceleration, sound, skins, effects, controller support, or multiplayer.
- Exactly one token exists while free cells remain. Collecting it adds one body segment and one point, and spawns the next token only on an unoccupied cell.
- Walls and the snake's body cause game over; no edge wrapping.
- Moving into the current tail cell is legal if the tail is vacating that cell on the same non-growing step.
- A full board is a win, not an infinite token-placement loop.
- Space or P pauses/resumes. Pausing freezes the model and ignores movement input; losing window focus automatically pauses.
- R or Enter restarts from game-over/win with a clean model and fresh timing; one movement loop only.
- Escape and the standard window close button exit cleanly.
- Score and best score are displayed; best score is saved locally. If saving fails, keep playing and report the persistence issue without crashing.
- Resizing retains square grid cells and correct input mapping; rendering must not affect rule timing.

## 4. File boundaries

Approved now (documentation and bot setup only):
- `/home/bignutta/projects/omarchy-snake/PLAN.md`
- `/home/bignutta/projects/omarchy-snake/APPROVALS.md`
- The three explicitly requested new profiles under `/home/bignutta/.hermes/profiles/`.

Proposed after first-pass approval:

```text
/home/bignutta/projects/omarchy-snake/
  PLAN.md
  APPROVALS.md
  README.md
  src/omarchy_snake/
    __init__.py
    __main__.py
    model.py
    app.py
    storage.py
  tests/
    unit/
    acceptance/
  packaging/
    omarchy-snake
    omarchy-snake.desktop
    omarchy-snake.svg
    install-user.sh
    uninstall-user.sh
  reports/
    implementation.md
    test-results.md
    integration-review.md
```

No project source/test/packaging files exist yet. Do not initialize a repository, commit, publish or push without permission.

Proposed installation targets, separately gated:
- App files: `~/.local/share/omarchy-snake/`
- Command: `~/.local/bin/omarchy-snake`
- Desktop entry: `~/.local/share/applications/omarchy-snake.desktop`
- Icon: `~/.local/share/icons/hicolor/scalable/apps/omarchy-snake.svg`
- Best score: `${XDG_STATE_HOME:-~/.local/state}/omarchy-snake/highscore.json`

The launcher must resolve paths independently of the current working directory. Existing targets must be checked and conflicts reported before overwriting anything. Installation must have an explicit manifest and a matching uninstall path; keep the best score by default when uninstalling unless the user asks to remove it.

Do not write to `/usr/share/omarchy/`, `/usr/bin/`, system package databases, global configs, keybindings, Hyprland configs or shell/bar settings. Do not add autostart entries or background services.

## 5. Execution phases and gates

### Phase A — setup and planning (authorized)

Create three persistent profiles, install selected skills, write role/approval instructions, pin the model, create this plan, and verify profile/skill configuration. Do not start agent work. Report the per-profile authentication blocker.

### Gate 1 — user approval of the first pass

Ask the user to approve the stack and gameplay defaults. Resolve profile sign-ins through supported interactive authentication. Only then dispatch the approved first-pass tasks.

### Phase B — first-pass build and independent testing (not yet authorized)

1. Integrator performs a minimal native-window feasibility check without installing anything or modifying desktop settings. If it fails, stop for a stack decision.
2. Builder develops one behavior at a time using RED-GREEN-REFACTOR. Capture actual failed-then-passed test evidence. Do not implement all tests as one speculative horizontal batch.
3. Tester can prepare the approved acceptance criteria in parallel, but must not edit builder-owned code. Test the actual resulting implementation when available.
4. Integrator prepares project-local packaging templates and an installation manifest only; do not run installation scripts.
5. Tester performs independent logic/persistence checks, code review and a real native-window smoke test. Coordinate GUI access; never have several bots controlling windows simultaneously.
6. If a defect is found, report its reproduction and proposed correction to the coordinator/user before a fix pass. No automatic fix or endless agent-to-agent loop.
7. Coordinator reports delivered files, real test output, observed UI behavior, untested items and blockers. Show a screenshot if the native GUI test can capture one.

Phase B may run the game from the project directory for testing. It may not install launcher entries, add packages, or make unrelated changes. Any extra dependency or privileged operation is a fresh approval checkpoint.

### Gate 2 — user review and installation approval

Let the user try the first-pass game from its project path. Present exact install targets and any conflicts. Obtain explicit approval before applying desktop integration.

### Phase C — user-local integration (not yet authorized)

Install only the approved files. Validate the desktop entry if the validator is available; otherwise report the missing validation. Launch through the actual application-menu/desktop entry, verify the correct native window and icon, and verify a launch from another working directory. Do not use a browser to display the game. Test the offline requirement without disabling the user's networking; use application-specific isolation when safely available, otherwise report the validation limitation. Review uninstall behavior without deleting user data unless removal is approved.

### Gate 3 — user verdict

Collect feedback. New polish/features/packaging changes become a separately approved pass.

## 6. Acceptance test matrix

| Area | Required evidence |
| --- | --- |
| Movement | Each arrow direction affects the next legal step correctly; continuous movement uses fixed steps. |
| Input safety | Opposite turns ignored; queued turns preserve order; key repeats and rapid presses cannot trigger illegal reversal. |
| Growth | Token collision adds exactly one segment and one point, once per token. |
| Token placement | No spawn on snake; seeded tests reproduce placement; a full board terminates as a win. |
| Collisions | Each board edge and self-collision tested; moving into a vacating tail is handled correctly. |
| Lifecycle | Ready, running, paused, game-over and win states have valid transitions; restart clears stale timers/input. |
| Persistence | Best score survives a new process; missing/corrupt/unwritable files do not prevent play. |
| Native GUI | Actual window opens; arrows reach it; resizing, focus-pause, restart and close work. Headless tests are not substitutes. |
| Offline | No network or browser/server code; no remote assets. Verify a real launch in application-scoped network isolation if feasible. |
| Integration | Approved launcher/desktop entry starts the game independently of working directory, with correct title/icon and no terminal requirement. |
| Safety | No packaged Omarchy edits, autostart, global configs, unapproved package installs or unrelated writes. |

Acceptance is evidence-based: do not call an item passed merely because the code looks correct. Any missing GUI/offline/launcher evidence must be explicitly marked unverified.

## 7. First-pass deliverable

A playable offline native-window Snake prototype in the project directory, unit and independent acceptance results, a concise defects/limitations report, and proposed integration templates awaiting installation approval. The result is not described as an installed Omarchy game until Phase C is approved and verified.
