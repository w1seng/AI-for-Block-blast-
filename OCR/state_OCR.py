import json
import time
from screen import take_screenshots
from board_render import analyze_board_cv
from hand_render import read_hand


def capture_game_state(board_image="board.png", hand_image="hand.png"):
    take_screenshots()

    board_data = analyze_board_cv(board_image)
    hand_data = read_hand(hand_image)

    state = {
        "board": {
            "size": 8,
            "grid": board_data["grid"]
        },
        "hand": hand_data
    }

    return state


def save_game_state(filename="game_state.json"):
    state = capture_game_state()

    if state is None:
        return False

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return True


if __name__ == "__main__":
    save_game_state("state.json")
