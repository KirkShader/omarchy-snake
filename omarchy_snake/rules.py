"""Display-independent Snake rules: board presets, movement, rewards and scoring."""
import random

GRID_CELLS = 64
CELL_PIXELS = 16
BOARD_PIXELS = GRID_CELLS * CELL_PIXELS
DIFFICULTIES = {'Easy': 64, 'Normal': 48, 'Hard': 32}
STEP_INTERVAL_MS = 150
HARD_SPEEDUP_MS = 2.3
HARD_MIN_STEP_INTERVAL_MS = 50  # User-approved Hard floor (2026-10-31), supersedes the 1 ms floor.
MIN_STEP_INTERVAL_MS = HARD_MIN_STEP_INTERVAL_MS  # Backwards-compatible name.
GREEN_INTERVAL_MS = 30000
MAX_QUEUED_TURNS = 2  # Approved two-deep safe turn buffer.


class MovementPreview:
    """Display-independent Snake rules with an injectable random generator."""

    DIRECTIONS = {'Up': (0, -1), 'Down': (0, 1),
                  'Left': (-1, 0), 'Right': (1, 0)}

    def __init__(self, rng=None, difficulty='Easy'):
        self.rng = rng if rng is not None else random.Random()
        self.reset(difficulty)

    @property
    def board_pixels(self):
        return self.grid_cells * CELL_PIXELS

    def reset(self, difficulty=None):
        if difficulty is not None:
            if difficulty not in DIFFICULTIES:
                raise ValueError('Unknown difficulty')
            self.difficulty = difficulty
        self.grid_cells = DIFFICULTIES[self.difficulty]
        self.snake = [(7, 8), (6, 8), (5, 8), (4, 8), (3, 8), (2, 8)]
        self.ticks = 0
        self.direction = 'Right'
        self.queued_turns = []
        self.score = 0
        self.game_over = False
        self.game_over_reason = None
        self.won = False
        self.last_reward = None  # 'orange' or 'green' when the latest step collected one
        self.foods = set()
        self.green_dot = None
        self.green_elapsed_ms = 0
        self.refill_foods()

    @property
    def finished(self):
        """A lost or won run accepts no further moves, turns or cooldown time."""
        return self.game_over or self.won

    @property
    def state(self):
        return 'lost' if self.game_over else 'won' if self.won else 'playing'

    @property
    def orange_dot_count(self):
        return 10 if self.difficulty == 'Hard' else 5

    @property
    def step_interval_ms(self):
        if self.difficulty != 'Hard':
            return STEP_INTERVAL_MS
        return max(HARD_MIN_STEP_INTERVAL_MS, round(STEP_INTERVAL_MS - self.score * HARD_SPEEDUP_MS, 1))

    def refill_foods(self):
        while len(self.foods) < self.orange_dot_count:
            excluded = self.foods | ({self.green_dot} if self.green_dot else set())
            cell = self.empty_cell(excluded)
            if cell is None:
                break
            self.foods.add(cell)

    def empty_cell(self, excluded=()):
        occupied = set(self.snake) | set(excluded)
        free = [(x, y) for y in range(self.grid_cells) for x in range(self.grid_cells)
                if (x, y) not in occupied]
        return self.rng.choice(free) if free else None

    @property
    def pending_direction(self):
        """Next turn to apply; kept for tools written before the two-deep queue."""
        return self.queued_turns[0] if self.queued_turns else None

    @pending_direction.setter
    def pending_direction(self, key):
        self.queued_turns = [] if key is None else [key]

    def request_turn(self, key):
        """Queue a perpendicular turn relative to the last queued (or current) heading."""
        if (self.finished or key not in self.DIRECTIONS
                or len(self.queued_turns) >= MAX_QUEUED_TURNS):
            return False
        dx, dy = self.DIRECTIONS[self.queued_turns[-1] if self.queued_turns else self.direction]
        requested = self.DIRECTIONS[key]
        if requested == (dx, dy) or requested == (-dx, -dy):
            return False
        self.queued_turns.append(key)
        return True

    def step(self, elapsed_ms=None):
        self.last_reward = None
        if self.finished:
            return
        if elapsed_ms is None:
            elapsed_ms = self.step_interval_ms
        if self.queued_turns:
            self.direction = self.queued_turns.pop(0)
        x, y = self.snake[0]
        dx, dy = self.DIRECTIONS[self.direction]
        head = (x + dx, y + dy)
        if self.difficulty == 'Hard' and not all(0 <= cell < self.grid_cells for cell in head):
            self.game_over = True
            self.game_over_reason = 'wall collision'
            return
        head = (head[0] % self.grid_cells, head[1] % self.grid_cells)
        growing = head in self.foods
        shrinking = head == self.green_dot and len(self.snake) >= 6
        remaining_body = self.snake if growing else self.snake[:-1]
        if (self.difficulty == 'Hard' or len(self.snake) >= 10) and head in remaining_body:
            self.game_over = True
            self.game_over_reason = 'self collision'
            return
        self.snake = [head] + (self.snake if growing else self.snake[:-1])
        if growing:
            self.score += 1
            self.last_reward = 'orange'
            self.foods.remove(head)
            # Victory needs every cell under the snake; free cells holding food do not count.
            if len(set(self.snake)) == self.grid_cells * self.grid_cells:
                self.won = True
                self.green_dot = None
                self.ticks += 1
                return
            self.refill_foods()
        if shrinking:
            self.snake = self.snake[:-2]
            self.last_reward = 'green'
            self.green_dot = None
            self.green_elapsed_ms = 0
        self.ticks += 1
        if len(self.snake) < 6:
            self.green_dot = None
            self.green_elapsed_ms = 0
        elif self.green_dot is None:
            if not shrinking:
                self.green_elapsed_ms += max(0, elapsed_ms)
            if self.green_elapsed_ms >= GREEN_INTERVAL_MS:
                self.green_dot = self.empty_cell(self.foods)
                # With no free cell the due dot waits, spawning once space opens.
                self.green_elapsed_ms = 0 if self.green_dot else GREEN_INTERVAL_MS
