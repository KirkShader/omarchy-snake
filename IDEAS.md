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
