import json
import os
import time
import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

STATE_PATH = "state.json"
ACTION_PATH = "action.json"
RESTART_PATH = "restart.json"
WEIGHTS_PATH = "weights.json"
GENERIC_PATH = "stats.json"

POLL_DELAY_SEC = 0.05
MOVE_COOLDOWN_SEC = 0.02

FALLBACK_WEIGHTS = {
    'holes': -8.0,
    'max_height': -3.0,
    'avg_height': -1.0,
    'filled': -0.3,
    'edge_penalty': -2.0,
    'cluster_score': 4.0,
    'row_almost_full': 15.0,
    'col_almost_full': 15.0,
    'empty_rows': 5.0,
    'combo_preservation': 50.0,
    'piece_fit': 8.0,
    'diversity': 3.0,
    'cleared_lines': 100.0,
    'immediate_gain': 1.0,
}


def load_weights(path: str, fallback: dict) -> dict:
    """Loads weights from file or uses fallback."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key in fallback:
            if key not in data:
                raise ValueError(f"Missing weight: {key}")

        return {k: float(v) for k, v in data.items()}

    except Exception as e:
        print(f"⚠️ Failed to load weights ({e}), using fallback")
        return fallback.copy()


@dataclass
class Piece:
    """Piece with cells."""
    cells: List[Tuple[int, int]]
    slot: int


@dataclass
class GameState:
    """Game state."""
    grid: List[List[int]]
    hand: List[Optional[Piece]]
    combo: int
    combo_active: bool
    score: int
    size: int


@dataclass
class SimulatedState:
    """Simulated state after a move."""
    grid: List[List[int]]
    cleared_lines: int
    score_gain: int
    piece: Piece
    gx: int
    gy: int


def load_state(path: str) -> Optional[GameState]:
    """Loads and parses state.json."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
    status = data.get("status", {})
    if status.get("game_over") or not status.get("any_move_available", True):
        return None
    
    board = data.get("board", {})
    grid = board.get("grid", [])
    size = board.get("size", 8)
    
    hand_data = data.get("hand", [])
    hand: List[Optional[Piece]] = [None, None, None]
    
    for entry in hand_data:
        slot_idx = int(entry.get("slot", 0))
        if entry.get("empty", True):
            hand[slot_idx] = None
        else:
            piece_data = entry.get("piece")
            if piece_data:
                cells = [(int(x), int(y)) for x, y in piece_data.get("cells", [])]
                hand[slot_idx] = Piece(cells=cells, slot=slot_idx)
    
    combo_data = data.get("combo", {})
    combo = int(combo_data.get("combo", 0))
    combo_active = bool(combo_data.get("combo_active", False))
    
    score = int(data.get("score", 0))
    
    return GameState(
        grid=grid,
        hand=hand,
        combo=combo,
        combo_active=combo_active,
        score=score,
        size=size
    )


def can_place(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> bool:
    """Checks whether the piece can be placed."""
    size = len(grid)
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        if x < 0 or y < 0 or x >= size or y >= size:
            return False
        if grid[y][x] == 1:
            return False
    return True


def place_piece(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> None:
    """Places the piece on the grid (mutates grid!)."""
    for dx, dy in piece.cells:
        grid[gy + dy][gx + dx] = 1


def clear_lines(grid: List[List[int]]) -> int:
    """Clears full lines, returns the count of cleared lines."""
    size = len(grid)
    
    full_rows = [r for r in range(size) if all(grid[r][c] == 1 for c in range(size))]
    full_cols = [c for c in range(size) if all(grid[r][c] == 1 for r in range(size))]
    
    for r in full_rows:
        for c in range(size):
            grid[r][c] = 0
    
    for c in full_cols:
        for r in range(size):
            grid[r][c] = 0
    
    return len(full_rows) + len(full_cols)


def calculate_score_gain(cleared: int, combo: int) -> int:
    """Calculates score gain using the scoring formula."""
    if cleared <= 0:
        return 0
    
    base = 10 * cleared
    bonus = base * (combo + 1)
    
    if cleared > 2:
        bonus *= (cleared - 1)
    
    return bonus


def simulate_move(state: GameState, piece: Piece, gx: int, gy: int) -> Optional[SimulatedState]:
    """Simulates a move, returns the new state."""
    if not can_place(state.grid, piece, gx, gy):
        return None
    
    new_grid = [row[:] for row in state.grid]
    
    place_piece(new_grid, piece, gx, gy)
    
    base_gain = len(piece.cells)
    
    cleared = clear_lines(new_grid)
    
    clear_gain = calculate_score_gain(cleared, state.combo)
    total_gain = base_gain + clear_gain
    
    return SimulatedState(
        grid=new_grid,
        cleared_lines=cleared,
        score_gain=total_gain,
        piece=piece,
        gx=gx,
        gy=gy
    )


def calc_holes(grid: List[List[int]]) -> float:
    """Number of holes (empty cells below filled ones)."""
    size = len(grid)
    holes = 0
    
    for x in range(size):
        seen_block = False
        for y in range(size):
            if grid[y][x] == 1:
                seen_block = True
            elif seen_block and grid[y][x] == 0:
                holes += 1
    
    return float(holes)


def calc_max_height(grid: List[List[int]]) -> float:
    """Maximum column height."""
    size = len(grid)
    max_h = 0
    
    for x in range(size):
        for y in range(size):
            if grid[y][x] == 1:
                h = size - y
                max_h = max(max_h, h)
                break
    
    return float(max_h)


def calc_avg_height(grid: List[List[int]]) -> float:
    """Average column height."""
    size = len(grid)
    heights = []
    
    for x in range(size):
        for y in range(size):
            if grid[y][x] == 1:
                heights.append(size - y)
                break
        else:
            heights.append(0)
    
    return sum(heights) / len(heights) if heights else 0.0


def calc_filled(grid: List[List[int]]) -> float:
    """Total board fill count."""
    total = sum(sum(row) for row in grid)
    return float(total)


def calc_edge_penalty(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> float:
    """Penalty for placing near edges (risky)."""
    size = len(grid)
    edge_cells = 0
    
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        if x == 0 or x == size - 1 or y == 0 or y == size - 1:
            edge_cells += 1
    
    return float(edge_cells)


def calc_cluster_score(grid: List[List[int]]) -> float:
    """Block clustering score (good for future clears)."""
    size = len(grid)
    cluster = 0
    
    for y in range(size):
        for x in range(size):
            if grid[y][x] == 1:
                neighbors = 0
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < size and 0 <= ny < size and grid[ny][nx] == 1:
                        neighbors += 1
                cluster += neighbors
    
    return float(cluster)


def calc_row_almost_full(grid: List[List[int]]) -> float:
    """Number of nearly full rows (6-7 out of 8 cells)."""
    size = len(grid)
    almost_full = 0
    
    for y in range(size):
        filled = sum(grid[y])
        if size - 2 <= filled < size:
            almost_full += 1
    
    return float(almost_full)


def calc_col_almost_full(grid: List[List[int]]) -> float:
    """Number of nearly full columns."""
    size = len(grid)
    almost_full = 0
    
    for x in range(size):
        filled = sum(grid[y][x] for y in range(size))
        if size - 2 <= filled < size:
            almost_full += 1
    
    return float(almost_full)


def calc_empty_rows(grid: List[List[int]]) -> float:
    """Number of completely empty rows (room to maneuver)."""
    size = len(grid)
    empty = 0
    
    for y in range(size):
        if sum(grid[y]) == 0:
            empty += 1
    
    return float(empty)


def calc_combo_preservation(combo: int, combo_active: bool, cleared: int) -> float:
    """Value of preserving the combo."""
    if combo_active and cleared > 0:
        return 30.0 * cleared

    if not combo_active and cleared > 0:
        return 10.0 * cleared

    return 0.0


def calc_piece_fit(grid: List[List[int]], piece: Piece, gx: int, gy: int) -> float:
    """How well the piece fills available space."""
    size = len(grid)
    fit_score = 0
    
    for dx, dy in piece.cells:
        x, y = gx + dx, gy + dy
        
        neighbors = 0
        for ndx, ndy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + ndx, y + ndy
            if nx < 0 or ny < 0 or nx >= size or ny >= size:
                neighbors += 1
            elif grid[ny][nx] == 1:
                neighbors += 1
        
        fit_score += neighbors
    
    return float(fit_score)


def calc_diversity(grid: List[List[int]]) -> float:
    """Height variance (flat board is better than uneven)."""
    size = len(grid)
    heights = []
    
    for x in range(size):
        for y in range(size):
            if grid[y][x] == 1:
                heights.append(size - y)
                break
        else:
            heights.append(0)
    
    if not heights:
        return 0.0
    
    avg = sum(heights) / len(heights)
    variance = sum((h - avg) ** 2 for h in heights) / len(heights)
    std_dev = variance ** 0.5
    
    return -std_dev


def evaluate_move(sim: SimulatedState, state: GameState, weights: Dict[str, float]) -> float:
    """Main move evaluation formula: S = k1*b1 + k2*b2 + ... + kn*bn."""
    
    b1 = calc_holes(sim.grid)
    b2 = calc_max_height(sim.grid)
    b3 = calc_avg_height(sim.grid)
    b4 = calc_filled(sim.grid)
    b5 = calc_edge_penalty(sim.grid, sim.piece, sim.gx, sim.gy)
    b6 = calc_cluster_score(sim.grid)
    b7 = calc_row_almost_full(sim.grid)
    b8 = calc_col_almost_full(sim.grid)
    b9 = calc_empty_rows(sim.grid)
    b10 = calc_combo_preservation(state.combo, state.combo_active, sim.cleared_lines)
    b11 = calc_piece_fit(sim.grid, sim.piece, sim.gx, sim.gy)
    b12 = calc_diversity(sim.grid)
    b13 = float(sim.cleared_lines)
    b14 = float(sim.score_gain)
    
    value = (
        weights['holes'] * b1 +
        weights['max_height'] * b2 +
        weights['avg_height'] * b3 +
        weights['filled'] * b4 +
        weights['edge_penalty'] * b5 +
        weights['cluster_score'] * b6 +
        weights['row_almost_full'] * b7 +
        weights['col_almost_full'] * b8 +
        weights['empty_rows'] * b9 +
        weights['combo_preservation'] * b10 +
        weights['piece_fit'] * b11 +
        weights['diversity'] * b12 +
        weights['cleared_lines'] * b13 +
        weights['immediate_gain'] * b14
    )
    
    return value


def find_all_legal_moves(state: GameState) -> List[Tuple[Piece, int, int]]:
    """Finds all legal moves (piece, gx, gy)."""
    moves = []
    
    for piece in state.hand:
        if piece is None:
            continue
        
        for gy in range(state.size):
            for gx in range(state.size):
                if can_place(state.grid, piece, gx, gy):
                    moves.append((piece, gx, gy))
    
    return moves


def choose_best_move(state: GameState, weights: Dict[str, float]) -> Optional[Tuple[int, int, int]]:
    """Finds the best move using the evaluation formula. Returns: (slot, gx, gy) or None."""
    legal_moves = find_all_legal_moves(state)
    
    if not legal_moves:
        return None
    
    best_move = None
    best_value = -1e18
    
    for piece, gx, gy in legal_moves:
        sim = simulate_move(state, piece, gx, gy)
        if sim is None:
            continue
        
        value = evaluate_move(sim, state, weights)
        
        if value > best_value:
            best_value = value
            best_move = (piece.slot, gx, gy)
    
    return best_move


def write_action(slot: int, gx: int, gy: int, move_id: int) -> None:
    """Writes a move to action.json atomically with retry."""
    action = {
        "move_id": move_id,
        "slot": slot,
        "gx": gx,
        "gy": gy
    }
    
    tmp_path = ACTION_PATH + ".tmp"
    
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(action, f, ensure_ascii=False, indent=2)
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            if os.path.exists(ACTION_PATH):
                os.remove(ACTION_PATH)
            
            os.rename(tmp_path, ACTION_PATH)
            return
            
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.05)
            else:
                print(f"⚠️ Failed to write action.json after {max_retries} attempts")
                try:
                    os.remove(tmp_path)
                except:
                    pass
                raise


class Toggle:
    """Thread-safe toggle for AI."""
    
    def __init__(self):
        self.enabled = False
        self._lock = threading.Lock()
    
    def set(self, v: bool):
        with self._lock:
            self.enabled = v
    
    def get(self) -> bool:
        with self._lock:
            return self.enabled


def console_thread(toggle: Toggle):
    """Console interface for controlling the AI."""
    print("🤖 AI Control:")
    print("  on   - enable AI")
    print("  off  - disable AI")
    print("  quit - exit")
    
    while True:
        cmd = input("> ").strip().lower()
        
        if cmd == "on":
            toggle.set(True)
            print("✅ AI enabled")
        elif cmd == "off":
            toggle.set(False)
            print("⸱️ AI paused")
        elif cmd in ("quit", "exit", "q"):
            toggle.set(False)
            print("👋 Exiting...")
            os._exit(0)
        else:
            print("❌ Commands: on / off / quit")


def main():
    """Main AI loop."""
    toggle = Toggle()
    
    try:
        with open(GENERIC_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except:
        stats = {}
    
    t = threading.Thread(target=console_thread, args=(toggle,), daemon=True)
    t.start()
    
    move_id = 0
    game = 1
    generic = 1
    max_combo = 0
    max_score = 0

    weights = load_weights(WEIGHTS_PATH, FALLBACK_WEIGHTS)
    print("🎮 AI started! Waiting for a game...")
    
    while True:
        if not toggle.get():
            time.sleep(0.1)
            continue
        
        
        time.sleep(POLL_DELAY_SEC)

        state = load_state(STATE_PATH)
        if state is None:
            stats[game] = {
                "Moves": move_id,
                "Score": max_score,
                "Max_Combo": max_combo
            }
            
            with open(GENERIC_PATH, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            game += 1
            move_id = 0
            max_combo = 0
            max_score = 0

            if game > 10:
                weights = load_weights(WEIGHTS_PATH, FALLBACK_WEIGHTS)
                
                generic += 1
                game = 1
                stats = {}
    
            with open(RESTART_PATH, "w", encoding="utf-8") as f:
                json.dump({"restart": True}, f, ensure_ascii=False, indent=2)

            continue
        
        if state.combo > max_combo:
            max_combo = state.combo
        if state.score > max_score:
            max_score = state.score

        best = choose_best_move(state, weights)
        
        if best is None:
            continue
        
        slot, gx, gy = best
        
        move_id += 1
        write_action(slot, gx, gy, move_id)
        print(f"Generation {generic} Game {game} Move #{move_id}, Score {state.score}, combo={state.combo}")
        
        time.sleep(MOVE_COOLDOWN_SEC)


if __name__ == "__main__":
    main()