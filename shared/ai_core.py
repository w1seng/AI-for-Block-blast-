import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple



FALLBACK_WEIGHTS: Dict[str, float] = {
    "holes":              -8.0,
    "max_height":         -3.0,
    "avg_height":         -1.0,
    "filled":             -0.3,
    "edge_penalty":       -2.0,
    "cluster_score":       4.0,
    "row_almost_full":    15.0,
    "col_almost_full":    15.0,
    "empty_rows":          5.0,
    "combo_preservation": 50.0,
    "piece_fit":           8.0,
    "diversity":           3.0,
    "cleared_lines":     100.0,
    "immediate_gain":      1.0,
}


def load_weights(path: str, fallback: Dict[str, float]) -> Dict[str, float]:
    """Loads weights from file. Falls back to defaults if file is missing or invalid."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key in fallback:
            if key not in data:
                raise ValueError(f"Missing weight key: '{key}'")

        return {k: float(v) for k, v in data.items()}

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Failed to load weights ({e}), using fallback")
        return fallback.copy()



@dataclass
class Piece:
    """A game piece defined by its cell offsets and hand slot index."""
    cells: List[Tuple[int, int]]
    slot:  int


@dataclass
class GameState:
    """Snapshot of the game read from state.json."""
    grid:         List[List[int]]
    hand:         List[Optional[Piece]]
    combo:        int
    combo_active: bool
    score:        int
    size:         int


@dataclass
class SimulatedState:
    """Result of simulating one placement on a GameState."""
    grid:          List[List[int]]
    cleared_lines: int
    score_gain:    int
    piece:         Piece
    gx:            int
    gy:            int



def load_state(path: str) -> Optional[GameState]:
    """Reads state.json and returns a GameState, or None if game is over / file missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    status = data.get("status", {})
    if status.get("game_over") or not status.get("any_move_available", True):
        return None

    board = data.get("board", {})
    grid  = board.get("grid", [])
    size  = board.get("size", 8)

    hand: List[Optional[Piece]] = [None, None, None]
    for entry in data.get("hand", []):
        idx = int(entry.get("slot", 0))
        if not entry.get("empty", True):
            piece_data = entry.get("piece")
            if piece_data:
                cells = [(int(x), int(y)) for x, y in piece_data.get("cells", [])]
                hand[idx] = Piece(cells=cells, slot=idx)

    combo_data   = data.get("combo", {})
    combo        = int(combo_data.get("combo", 0))
    combo_active = bool(combo_data.get("combo_active", False))
    score        = int(data.get("score", 0))

    return GameState(
        grid=grid,
        hand=hand,
        combo=combo,
        combo_active=combo_active,
        score=score,
        size=size,
    )


def can_place(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> bool:
    """Returns True if the piece fits at (gx, gy) without going out of bounds or overlapping."""
    size = len(grid)
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        if not (0 <= x < size and 0 <= y < size):
            return False
        if grid[y][x] == 1:
            return False
    return True


def _place_piece(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> None:
    """Mutates grid by stamping the piece at (gx, gy)."""
    for dx, dy in piece.cells:
        grid[gy + dy][gx + dx] = 1


def _clear_lines(grid: List[List[int]]) -> int:
    """Clears completed rows and columns in-place. Returns number of lines cleared."""
    size      = len(grid)
    full_rows = [r for r in range(size) if all(grid[r][c] for c in range(size))]
    full_cols = [c for c in range(size) if all(grid[r][c] for r in range(size))]

    for r in full_rows:
        for c in range(size):
            grid[r][c] = 0
    for c in full_cols:
        for r in range(size):
            grid[r][c] = 0

    return len(full_rows) + len(full_cols)


def _calculate_score_gain(cleared: int, combo: int) -> int:
    """Mirrors the scoring formula from game.py."""
    if cleared <= 0:
        return 0
    base  = 10 * cleared
    bonus = base * (combo + 1)
    if cleared > 2:
        bonus *= (cleared - 1)
    return bonus


def simulate_move(
    state: GameState, piece: Piece, gx: int, gy: int
) -> Optional[SimulatedState]:
    """Returns the board state after placing piece at (gx, gy), or None if illegal."""
    if not can_place(state.grid, piece, gx, gy):
        return None

    new_grid = [row[:] for row in state.grid]
    _place_piece(new_grid, piece, gx, gy)

    base_gain  = len(piece.cells)
    cleared    = _clear_lines(new_grid)
    clear_gain = _calculate_score_gain(cleared, state.combo)

    return SimulatedState(
        grid=new_grid,
        cleared_lines=cleared,
        score_gain=base_gain + clear_gain,
        piece=piece,
        gx=gx,
        gy=gy,
    )



def calc_holes(grid: List[List[int]]) -> float:
    """Empty cells with at least one filled cell above them (per column)."""
    size  = len(grid)
    holes = 0
    for x in range(size):
        seen = False
        for y in range(size):
            if grid[y][x]:
                seen = True
            elif seen:
                holes += 1
    return float(holes)


def calc_max_height(grid: List[List[int]]) -> float:
    """Height of the tallest column."""
    size  = len(grid)
    max_h = 0
    for x in range(size):
        for y in range(size):
            if grid[y][x]:
                max_h = max(max_h, size - y)
                break
    return float(max_h)


def calc_avg_height(grid: List[List[int]]) -> float:
    """Mean column height across all columns."""
    size    = len(grid)
    heights = []
    for x in range(size):
        for y in range(size):
            if grid[y][x]:
                heights.append(size - y)
                break
        else:
            heights.append(0)
    return sum(heights) / len(heights) if heights else 0.0


def calc_filled(grid: List[List[int]]) -> float:
    """Total number of filled cells on the board."""
    return float(sum(sum(row) for row in grid))


def calc_edge_penalty(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> float:
    """Number of piece cells that land on the board edge."""
    size       = len(grid)
    edge_cells = 0
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        if x == 0 or x == size - 1 or y == 0 or y == size - 1:
            edge_cells += 1
    return float(edge_cells)


def calc_cluster_score(grid: List[List[int]]) -> float:
    """Sum of filled neighbours for every filled cell (rewards compact shapes)."""
    size    = len(grid)
    cluster = 0
    for y in range(size):
        for x in range(size):
            if grid[y][x]:
                for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < size and 0 <= ny < size and grid[ny][nx]:
                        cluster += 1
    return float(cluster)


def calc_row_almost_full(grid: List[List[int]]) -> float:
    """Rows that are 1–2 cells away from being cleared."""
    size = len(grid)
    return float(sum(1 for y in range(size) if size - 2 <= sum(grid[y]) < size))


def calc_col_almost_full(grid: List[List[int]]) -> float:
    """Columns that are 1–2 cells away from being cleared."""
    size = len(grid)
    return float(
        sum(1 for x in range(size) if size - 2 <= sum(grid[y][x] for y in range(size)) < size)
    )


def calc_empty_rows(grid: List[List[int]]) -> float:
    """Completely empty rows (breathing room for future pieces)."""
    return float(sum(1 for row in grid if sum(row) == 0))


def calc_combo_preservation(combo: int, combo_active: bool, cleared: int) -> float:
    """Bonus for moves that keep or start a combo streak."""
    if cleared <= 0:
        return 0.0
    return 30.0 * cleared if combo_active else 10.0 * cleared


def calc_piece_fit(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> float:
    """How snugly the piece nestles against existing blocks and walls."""
    size      = len(grid)
    fit_score = 0
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        for ndx, ndy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nx, ny = x + ndx, y + ndy
            if not (0 <= nx < size and 0 <= ny < size):
                fit_score += 1          # wall counts as a neighbour
            elif grid[ny][nx]:
                fit_score += 1
    return float(fit_score)


def calc_height_variance(grid: List[List[int]]) -> float:
    """Standard deviation of column heights — lower means flatter board (better).
    
    Note: returns -std_dev so that a positive weight rewards flatness.
    """
    size    = len(grid)
    heights = []
    for x in range(size):
        for y in range(size):
            if grid[y][x]:
                heights.append(size - y)
                break
        else:
            heights.append(0)

    if not heights:
        return 0.0

    avg      = sum(heights) / len(heights)
    variance = sum((h - avg) ** 2 for h in heights) / len(heights)
    return -(variance ** 0.5)



def evaluate_move(
    sim: SimulatedState, state: GameState, weights: Dict[str, float]
) -> float:
    """Weighted linear combination of all heuristic features.

    S = w_holes·holes + w_max_height·max_height + ... + w_cleared·cleared_lines
    """
    holes      = calc_holes(sim.grid)
    max_height = calc_max_height(sim.grid)
    avg_height = calc_avg_height(sim.grid)
    filled     = calc_filled(sim.grid)
    edge       = calc_edge_penalty(sim.grid, sim.piece, sim.gx, sim.gy)
    cluster    = calc_cluster_score(sim.grid)
    rows_near  = calc_row_almost_full(sim.grid)
    cols_near  = calc_col_almost_full(sim.grid)
    empty_rows = calc_empty_rows(sim.grid)
    combo_val  = calc_combo_preservation(state.combo, state.combo_active, sim.cleared_lines)
    fit        = calc_piece_fit(sim.grid, sim.piece, sim.gx, sim.gy)
    variance   = calc_height_variance(sim.grid)
    cleared    = float(sim.cleared_lines)
    gain       = float(sim.score_gain)

    return (
        weights["holes"]              * holes      +
        weights["max_height"]         * max_height +
        weights["avg_height"]         * avg_height +
        weights["filled"]             * filled     +
        weights["edge_penalty"]       * edge       +
        weights["cluster_score"]      * cluster    +
        weights["row_almost_full"]    * rows_near  +
        weights["col_almost_full"]    * cols_near  +
        weights["empty_rows"]         * empty_rows +
        weights["combo_preservation"] * combo_val  +
        weights["piece_fit"]          * fit        +
        weights["diversity"]          * variance   +
        weights["cleared_lines"]      * cleared    +
        weights["immediate_gain"]     * gain
    )


def find_all_legal_moves(state: GameState) -> List[Tuple[Piece, int, int]]:
    """Returns every (piece, gx, gy) triple that is legal in the current state."""
    moves = []
    for piece in state.hand:
        if piece is None:
            continue
        for gy in range(state.size):
            for gx in range(state.size):
                if can_place(state.grid, piece, gx, gy):
                    moves.append((piece, gx, gy))
    return moves


def choose_best_move(
    state: GameState, weights: Dict[str, float]
) -> Optional[Tuple[int, int, int]]:
    """Greedy one-ply search. Returns (slot, gx, gy) for the highest-scoring move."""
    best_move  = None
    best_value = -1e18

    for piece, gx, gy in find_all_legal_moves(state):
        sim = simulate_move(state, piece, gx, gy)
        if sim is None:
            continue
        value = evaluate_move(sim, state, weights)
        if value > best_value:
            best_value = value
            best_move  = (piece.slot, gx, gy)

    return best_move