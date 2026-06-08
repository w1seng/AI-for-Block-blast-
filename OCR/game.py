import json
import os
import sys
import time
import threading
from typing import List, Tuple, Optional
from dataclasses import dataclass
import screen
import pygame


_HERE       = os.path.dirname(os.path.abspath(__file__))
_ROOT       = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

try:
    from state_OCR import save_game_state as _capture_state
except ImportError:
    _capture_state = None


from shared.config import (
        BOARD_SIZE, CELL, CELL_HAND, GAP_BOARD, GAP_HAND,
        PADDING, TOP_BAR, HAND_HEIGHT, EXTRA_W, EXTRA_H,
        BG, GRID_BG, LINE, BLOCK, GHOST_OK, GHOST_BAD, TEXT, SUBTEXT,
)
BOARD_W = BOARD_SIZE * CELL
BOARD_H = BOARD_SIZE * CELL
WIN_W   = PADDING * 2 + BOARD_W + EXTRA_W
WIN_H   = TOP_BAR + PADDING + BOARD_H + 20 + HAND_HEIGHT + EXTRA_H
BOARD_X = (WIN_W - BOARD_W) // 2
BOARD_Y = TOP_BAR
HAND_Y  = BOARD_Y + BOARD_H + 20
HAND_X  = PADDING
HAND_W  = WIN_W - 2 * PADDING

STATE_PATH   = "state.json"

_SHARED_DIR  = os.path.join(_ROOT, "shared")
WEIGHTS_PATH = os.path.join(_SHARED_DIR, "weights.json")

HINT_BORDER  = (*GHOST_OK, 220)
CLEAR_LINE   = (*GHOST_OK, 55)

from shared.ai_core import Piece as _Piece, GameState as _GameState

@dataclass
class AIPiece:
    cells: List[Tuple[int, int]]
    slot: int
    w: int
    h: int


@dataclass
class AIState:
    grid: List[List[int]]
    hand: List[Optional[AIPiece]]
    combo: int
    combo_active: bool
    score: int
    size: int


try:
    import ai as _ai
    _AI_AVAILABLE = True
except ImportError:
    _ai = None
    _AI_AVAILABLE = False


def _load_weights(path: str) -> dict:
    if _AI_AVAILABLE:
        return _ai.load_weights(path, _ai.FALLBACK_WEIGHTS)
    fallback = {
        'holes': -8.0, 'max_height': -3.0, 'avg_height': -1.0,
        'filled': -0.3, 'edge_penalty': -2.0, 'cluster_score': 4.0,
        'row_almost_full': 15.0, 'col_almost_full': 15.0, 'empty_rows': 5.0,
        'combo_preservation': 50.0, 'piece_fit': 8.0, 'diversity': 3.0,
        'cleared_lines': 100.0, 'immediate_gain': 1.0,
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = fallback.copy()
        for k, v in data.items():
            if k in merged:
                merged[k] = float(v)
        return merged
    except Exception:
        return fallback.copy()


def choose_best(state: AIState, weights: dict):
    """Returns (slot, gx, gy, clear_rows, clear_cols) or None."""
    if _AI_AVAILABLE:
        ai_hand = []
        for p in state.hand:
            if p is None:
                ai_hand.append(None)
            else:
                ai_hand.append(_ai.Piece(cells=p.cells, slot=p.slot))
        ai_state = _ai.GameState(
            grid=state.grid, hand=ai_hand,
            combo=state.combo, combo_active=state.combo_active,
            score=state.score, size=state.size,
        )
        result = _ai.choose_best_move(ai_state, weights)
        if result is None:
            return None
        slot, gx, gy = result
        piece = state.hand[slot]
        if piece is None:
            return None
        tmp = [r[:] for r in state.grid]
        for dx, dy in piece.cells:
            tmp[gy + dy][gx + dx] = 1
        size = state.size
        cr = [r for r in range(size) if all(tmp[r][c] for c in range(size))]
        cc = [c for c in range(size) if all(tmp[r][c] for r in range(size))]
        return (slot, gx, gy, cr, cc)

    best_val = -1e18
    best     = None
    for piece in state.hand:
        if piece is None:
            continue
        for gy in range(state.size):
            for gx in range(state.size):
                if not all(
                    0 <= gx+dx < state.size and 0 <= gy+dy < state.size
                    and not state.grid[gy+dy][gx+dx]
                    for dx, dy in piece.cells
                ):
                    continue
                tmp = [r[:] for r in state.grid]
                for dx, dy in piece.cells:
                    tmp[gy+dy][gx+dx] = 1
                cr = [r for r in range(state.size) if all(tmp[r][c] for c in range(state.size))]
                cc = [c for c in range(state.size) if all(tmp[r][c] for r in range(state.size))]
                val = len(cr) + len(cc)
                if val > best_val:
                    best_val = val
                    best = (piece.slot, gx, gy, cr, cc)
    return best


def parse_state(path: str) -> Optional[AIState]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    board = data.get("board", {})
    grid  = board.get("grid", [])
    size  = board.get("size", 8)

    hand: List[Optional[AIPiece]] = [None, None, None]
    for entry in data.get("hand", []):
        idx = int(entry.get("slot", 0))
        if entry.get("empty", True):
            continue
        pd    = entry.get("piece", {})
        cells = [tuple(xy) for xy in pd.get("cells", [])]
        hand[idx] = AIPiece(cells=cells, slot=idx,
                            w=pd.get("w", 1), h=pd.get("h", 1))

    combo_d = data.get("combo", {})
    return AIState(
        grid=grid, hand=hand, size=size,
        combo=int(combo_d.get("combo", 0)),
        combo_active=bool(combo_d.get("combo_active", False)),
        score=int(data.get("score", 0)),
    )


def cell_rect(gx: int, gy: int) -> pygame.Rect:
    return pygame.Rect(BOARD_X + gx * CELL, BOARD_Y + gy * CELL,
                       CELL - GAP_BOARD, CELL - GAP_BOARD)


def draw_piece_cells(surface, cells, px, py, color, cell_size, gap, radius):
    for dx, dy in cells:
        r = pygame.Rect(px + dx*cell_size, py + dy*cell_size,
                        cell_size - gap, cell_size - gap)
        pygame.draw.rect(surface, color, r, border_radius=radius)


def draw_hint_ghost(surface, cells, gx, gy, clear_rows, clear_cols, flash: bool):
    """Green ghost + highlight of rows/columns to be cleared."""
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

    for row in clear_rows:
        for col in range(BOARD_SIZE):
            pygame.draw.rect(overlay, CLEAR_LINE,
                             cell_rect(col, row), border_radius=8)
    for col in clear_cols:
        for row in range(BOARD_SIZE):
            pygame.draw.rect(overlay, CLEAR_LINE,
                             cell_rect(col, row), border_radius=8)

    alpha = 175 if flash else 105
    for dx, dy in cells:
        x, y = gx + dx, gy + dy
        if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
            r = cell_rect(x, y)
            pygame.draw.rect(overlay, (*GHOST_OK, alpha), r, border_radius=8)
            pygame.draw.rect(overlay, HINT_BORDER,        r, width=2, border_radius=8)

    surface.blit(overlay, (0, 0))


def hand_slot_xs() -> List[int]:
    slot_w, margin = 180, 24
    cx = HAND_X + HAND_W // 2
    return [HAND_X + margin, cx - slot_w // 2, HAND_X + HAND_W - slot_w - margin]


def draw_hand(surface, hand, best_slot, font_small, flash: bool):
    """Draws the three hand slots; best_slot is highlighted with a green border."""
    slot_w, slot_h = 180, 160
    slot_y = HAND_Y + 16
    xs = hand_slot_xs()

    for i in range(3):
        sx    = xs[i]
        piece = hand[i]
        is_best = (i == best_slot)

        if piece is None:
            lbl = font_small.render("—", True, SUBTEXT)
            surface.blit(lbl, (sx + slot_w//2 - lbl.get_width()//2,
                                slot_y + slot_h//2 - lbl.get_height()//2))
            continue

        pw = piece.w * CELL_HAND
        ph = piece.h * CELL_HAND
        px = sx + (slot_w - pw) // 2
        py = slot_y + (slot_h - ph) // 2

        color = GHOST_OK if is_best else BLOCK
        draw_piece_cells(surface, piece.cells, px, py,
                         color, CELL_HAND, GAP_HAND, 6)

        if is_best:
            lbl = font_small.render("▶  PLAY", True, GHOST_OK)
            surface.blit(lbl, (sx + slot_w//2 - lbl.get_width()//2,
                                slot_y + slot_h - 22))


class StateWatcher:
    def __init__(self, path: str):
        self.path   = path
        self._state = None
        self._mtime = 0
        self._lock  = threading.Lock()

    def _capture_loop(self, interval: float):
        while True:
            if _capture_state is not None:
                try:
                    _capture_state(self.path)
                except Exception as e:
                    print(f"[StateWatcher] Capture error: {e}")
            time.sleep(interval)

    def _parse_loop(self, interval: float):
        while True:
            try:
                mt = os.path.getmtime(self.path)
            except OSError:
                time.sleep(interval)
                continue
            if mt != self._mtime:
                self._mtime = mt
                st = parse_state(self.path)
                with self._lock:
                    self._state = st
            time.sleep(interval)

    def get(self) -> Optional[AIState]:
        with self._lock:
            return self._state

    def start_background(self, capture_interval: float = 0.2, parse_interval: float = 0.1):
        threading.Thread(target=self._capture_loop, args=(capture_interval,), daemon=True).start()
        threading.Thread(target=self._parse_loop,   args=(parse_interval,),   daemon=True).start()


def run(state_path: str = STATE_PATH):
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Block Blast — AI Hint")
    clock  = pygame.time.Clock()

    font       = pygame.font.SysFont("Segoe UI", 22)
    font_small = pygame.font.SysFont("Segoe UI", 15)

    weights = _load_weights(WEIGHTS_PATH)

    watcher = StateWatcher(state_path)
    watcher.start_background(capture_interval=2, parse_interval=0.1)

    current_state : Optional[AIState] = None
    current_best  : Optional[tuple]   = None
    last_state_id : int                = -1
    flash         : bool               = True
    flash_timer   : int                = 0
    FLASH_MS      : int                = 650
    status_text   : str                = "Waiting for state.json…"

    while True:
        dt = clock.tick(60)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                pygame.quit()
                return

        new_state = watcher.get()
        if new_state is not None and id(new_state) != last_state_id:
            current_state = new_state
            last_state_id = id(new_state)
            current_best  = choose_best(current_state, weights)
            if current_best:
                slot, gx, gy, cr, cc = current_best
                clears = len(cr) + len(cc)
                status_text = (
                    f"Slot {slot+1}  →  R{gy+1} C{gx+1}"
                    + (f"   ✚ {clears} {'line' if clears == 1 else 'lines'}" if clears else "")
                )
            else:
                status_text = "No moves available"

        flash_timer += dt
        if flash_timer >= FLASH_MS:
            flash_timer = 0
            flash = not flash

        screen.fill(BG)

        pygame.draw.rect(screen, GRID_BG,
                         pygame.Rect(BOARD_X, BOARD_Y, BOARD_W, BOARD_H),
                         border_radius=14)

        grid = (current_state.grid if current_state
                else [[0]*BOARD_SIZE for _ in range(BOARD_SIZE)])
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                r = cell_rect(x, y)
                pygame.draw.rect(screen, LINE,  r, width=1, border_radius=8)
                if grid[y][x]:
                    pygame.draw.rect(screen, BLOCK, r, border_radius=8)

        if current_best and current_state:
            slot, gx, gy, cr, cc = current_best
            piece = current_state.hand[slot]
            if piece:
                draw_hint_ghost(screen, piece.cells, gx, gy, cr, cc, flash)

        hint_color = GHOST_OK if current_best else SUBTEXT
        lbl = font_small.render(f"▶  {status_text}", True, hint_color)
        screen.blit(lbl, (WIN_W//2 - lbl.get_width()//2, BOARD_Y + BOARD_H + 4))

        best_slot = current_best[0] if current_best else None
        if current_state:
            draw_hand(screen, current_state.hand, best_slot, font_small, flash)

        pygame.display.flip()


if __name__ == "__main__":
    screen.select_and_save_regions(2)
    path = sys.argv[1] if len(sys.argv) > 1 else STATE_PATH
    if not os.path.exists(path) and _capture_state is None:
        print(f"[hint_viewer] File not found: {path}")
        sys.exit(1)
    run(path)
