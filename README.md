# block_blast

A self-contained Block Blast puzzle game built with Pygame, bundled with a genetic-algorithm AI agent that learns to play it autonomously. The project ships in two variants that share the same AI core but differ in how they read the game state: **block_bast** (pure Python simulation) and **OCR** (computer-vision overlay for an external game window).

---

## Project structure

```
block_blast/
├── block_bast/          # Pygame simulation + AI agent (self-contained)
│   ├── main.py          # Entry point — launches the Pygame window
│   ├── config.py        # Visual constants: board size, cell size, colours
│   ├── pieces.py        # Piece definitions and piece pool
│   ├── game.py          # Core game logic (placement, line clearing, scoring, combo)
│   ├── state_io.py      # Serialises game state to state.json for the AI
│   ├── ui.py            # Pygame rendering, drag-and-drop, action.json consumer
│   ├── ai.py            # AI agent: evaluates positions and writes action.json
│   └── ai_trainer.py    # Genetic algorithm that evolves the AI's weights
│
└── OCR/                 # AI hint overlay for an external Block Blast window
    ├── config.py        # Same visual constants as block_bast
    ├── screen.py        # Screen-region selector and screenshot capture (mss)
    ├── board_render.py  # OpenCV colour-matching: screenshot → 8×8 grid
    ├── hand_render.py   # OpenCV mask analysis: screenshot → piece list
    ├── state_OCR.py     # Orchestrates capture → board + hand → state.json
    ├── game.py          # Pygame hint overlay (draws ghost + best-move label)
    └── ai.py            # Same AI agent, reads state.json produced by OCR
```

---

## How it works

### Game engine (`block_bast/`)

The game logic is a clean Python simulation of Block Blast rules:

- The board is an 8×8 grid of integers (0 = empty, 1 = filled).
- Each turn the player receives a hand of three pieces drawn from a pool of 26 distinct shapes.
- A piece is placed by dragging it from the hand onto the board with the mouse.
- Any row or column that becomes fully filled is immediately cleared.
- Scoring rewards multi-line clears and a combo system: clearing lines on consecutive hands multiplies points.
- If no piece in the current hand can legally be placed anywhere, the game ends.

The Pygame UI (`ui.py`) renders the board, draws ghost previews while dragging (green = valid, red = invalid), and doubles as a bridge between the human player and the AI agent via two JSON files:

- `state.json` — written after every move; describes the full board, hand, score, and combo state.
- `action.json` — written by the AI agent; consumed by the UI to execute the next move automatically.

This file-based protocol means the AI runs as a completely separate process and can be started or stopped at any time without touching the game window.

### AI agent (`ai.py`)

The agent is a **greedy one-ply search**: for every legal (piece, column, row) combination it simulates the placement, clears lines, and scores the resulting position with a weighted linear formula:

```
S = w_holes·holes + w_max_height·max_height + w_avg_height·avg_height
  + w_filled·filled + w_edge·edge_penalty + w_cluster·cluster_score
  + w_row·row_almost_full + w_col·col_almost_full + w_empty·empty_rows
  + w_combo·combo_preservation + w_fit·piece_fit + w_div·diversity
  + w_lines·cleared_lines + w_gain·immediate_gain
```

Each feature captures a different aspect of board quality:

| Feature | What it measures |
|---|---|
| `holes` | Empty cells trapped below filled ones (penalty) |
| `max_height` / `avg_height` | Stack height (penalty) |
| `filled` | Total occupied cells |
| `edge_penalty` | Cells placed on the board edge (risky) |
| `cluster_score` | Neighbouring filled cells (encourages compact placement) |
| `row_almost_full` / `col_almost_full` | Lines that are one or two cells away from clearing |
| `empty_rows` | Fully empty rows (breathing room) |
| `combo_preservation` | Bonus for keeping the combo multiplier alive |
| `piece_fit` | How snugly the piece fits into existing gaps |
| `diversity` | Penalises large height variance (prefers a flat surface) |
| `cleared_lines` | Immediate lines cleared by this move |
| `immediate_gain` | Raw score awarded by this move |

The agent polls `state.json` every 50 ms, picks the best move, writes `action.json`, then waits for the UI to acknowledge the move before proceeding.

A console interface (run alongside the main window) lets you type `on`, `off`, or `quit` to toggle the agent without restarting either process.

### Genetic trainer (`ai_trainer.py`)

The weights above are not hand-tuned — they are evolved automatically by a **steady-state genetic algorithm**:

1. A population of 10 weight sets is maintained in `population.json`.
2. Each set is evaluated over 10 games; fitness is computed as a weighted combination of average moves, score, and max combo.
3. After all candidates are scored the top 2 are kept as elite; the rest are replaced by offspring produced through **uniform crossover** and **Gaussian mutation**.
4. The best-ever weights are checkpointed to `best_weights.json`.
5. The trainer runs automatically between generation cycles: when the AI agent finishes game 10 it calls `ai_trainer.train()`, loads the new weights, and starts a fresh generation.

Weight search bounds are defined per-feature in `BOUNDS` inside `ai_trainer.py` so the algorithm never produces physically nonsensical values (e.g. a positive weight for holes).

### OCR variant (`OCR/`)

The OCR folder contains an alternative front-end for players who want AI hints while playing an actual mobile or desktop Block Blast app via an emulator or mirroring tool:

1. **`screen.py`** — on first run, lets the user drag two selection rectangles over the live game window: one covering the board, one covering the hand. Coordinates are saved to `screenshot_regions.json`.
2. **`board_render.py`** — takes a screenshot of the board region, samples nine points inside each of the 64 cells, and classifies each cell as empty or filled by comparing the sampled colour against the known background colour (`#182442`) with a configurable tolerance.
3. **`hand_render.py`** — takes a screenshot of the hand region, subtracts the background colour (`#395194`) to isolate block pixels, divides the strip into three equal slots, and reconstructs the cell coordinates of each piece.
4. **`state_OCR.py`** — orchestrates the two steps above and writes a `state.json` in the same format the AI agent expects.
5. **`game.py`** — a lightweight Pygame overlay that displays the best move (green ghost on the board + slot label) in a separate window on top of the game, updated at ~10 fps.

---

## Communication protocol

All components communicate through plain JSON files on disk. This keeps every module independently restartable and makes it trivial to swap any component.

```
ui.py / state_OCR.py  →  state.json  →  ai.py
ai.py                 →  action.json →  ui.py
ai.py                 →  restart.json → ui.py   (triggers new game)
ai_trainer.py         →  weights.json → ai.py   (updated weights)
ai_trainer.py         →  population.json         (evolution state)
ai_trainer.py         →  best_weights.json       (all-time best)
```

---

## Requirements

- Python 3.9+
- `pygame` — game window and rendering
- `opencv-python` (`cv2`) — OCR colour analysis (OCR variant only)
- `mss` — cross-platform screen capture (OCR variant only)
- `numpy` — pixel arithmetic (OCR variant only)

Install all at once:

```bash
pip install pygame opencv-python mss numpy
```

---

## Running

### Simulation (block_bast)

```bash
cd block_bast
python main.py          # opens the game window
python ai.py            # in a second terminal — starts the AI agent
```

Type `on` in the AI terminal to let the agent play. Type `off` to pause it and take over manually. Press `R` in the game window to restart at any time.

### OCR hint overlay

```bash
cd OCR
python screen.py        # first run only — select board and hand regions
python game.py          # starts the hint overlay window
python ai.py            # in a second terminal — starts the AI agent
```

---

## Configuration

All layout and colour constants are in `config.py`. Key values:

| Constant | Default | Description |
|---|---|---|
| `BOARD_SIZE` | `8` | Board dimensions (N×N) |
| `CELL` | `48` | Board cell size in pixels |
| `CELL_HAND` | `30` | Hand piece cell size in pixels |
| `BG` | `(20, 22, 28)` | Window background colour |
| `BLOCK` | `(220, 220, 235)` | Filled cell colour |
| `GHOST_OK` | `(140, 255, 170)` | Valid placement preview colour |
| `GHOST_BAD` | `(255, 120, 120)` | Invalid placement preview colour |

AI timing constants are at the top of `ai.py`:

| Constant | Default | Description |
|---|---|---|
| `POLL_DELAY_SEC` | `0.05` | How often the agent checks state.json |
| `MOVE_COOLDOWN_SEC` | `0.02` | Minimum delay between consecutive moves |

---

## File reference

| File | Responsibility |
|---|---|
| `main.py` | Launches `ui.run()` |
| `config.py` | Shared visual constants |
| `pieces.py` | 26 piece shapes + `Piece` dataclass + pool factory |
| `game.py` | `Game` class — all game rules, no rendering |
| `state_io.py` | `build_state_dict` / `write_state_json` |
| `ui.py` | Pygame loop, drag-and-drop, action.json polling |
| `ai.py` | `main()` loop, feature functions, `choose_best_move` |
| `ai_trainer.py` | `train()` — genetic algorithm, population management |
