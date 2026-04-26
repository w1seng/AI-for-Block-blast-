from dataclasses import dataclass
from typing import List, Tuple

PIECES = [
    [(0, 0)],
    [(0, 0), (1, 0)],
    [(0, 0), (1, 0), (2, 0)],
    [(0, 0), (1, 0), (2, 0), (3, 0)],
    [(0, 0), (0, 1)],
    [(0, 0), (0, 1), (0, 2)],
    [(0, 0), (0, 1), (0, 2), (0, 3)],
    [(0, 0), (1, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (2, 0),(0, 1), (1, 1), (2, 1),(0, 2), (1, 2), (2, 2)],
    [(0, 0), (0, 1), (0, 2), (1, 2)],
    [(1, 0), (1, 1), (1, 2), (0, 2)],
    [(0, 0), (1, 0), (2, 0), (0, 1)],
    [(0, 0), (1, 0), (2, 0), (2, 1)],
    [(0, 0), (1, 0), (2, 0), (1, 1)],
    [(1, 0), (0, 1), (1, 1), (1, 2)],
    [(1, 0), (0, 1), (1, 1), (2, 1)],
    [(0, 0), (0, 1), (0, 2), (1, 1)],
    [(0, 0), (1, 0), (1, 1), (2, 1)],
    [(1, 0), (1, 1), (0, 1), (0, 2)],
    [(0, 0), (0, 1), (1, 1), (0, 2)],
    [(0, 0), (0, 1), (1, 1)],
    [(0, 1), (1, 1), (1, 0)],
    [(0, 0), (1, 0), (0, 1)],
    [(0, 0), (1, 0), (1, 1)],
    [(0,0), (1,0), (2,0), (0,1), (1,1), (2,1)],
    [(0,0), (1,0), (0,1), (1,1), (0,2), (1,2)],
]


@dataclass(frozen=True)
class Piece:
    """Description of a piece as a set of cells relative to (0,0) and its name."""
    cells: Tuple[Tuple[int, int], ...]
    name: str

    @property
    def w(self) -> int:
        """Width of the piece in cells."""
        return 1 + max(x for x, _ in self.cells)

    @property
    def h(self) -> int:
        """Height of the piece in cells."""
        return 1 + max(y for _, y in self.cells)


def normalize(cells: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Normalizes cells so that the minimum x,y becomes (0,0)."""
    minx = min(x for x, _ in cells)
    miny = min(y for _, y in cells)
    return sorted([(x - minx, y - miny) for x, y in cells])


def make_piece_pool() -> List[Piece]:
    """Creates a piece pool from base templates (no rotations)."""
    return [Piece(tuple(normalize(base)), name=f"P{i}") for i, base in enumerate(PIECES)]


PIECE_POOL = make_piece_pool()
