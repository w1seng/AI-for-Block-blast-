import cv2
import numpy as np

CELL_SIZE = 24


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return np.array([int(hex_color[i:i+2], 16) for i in (0, 2, 4)])


def find_shape_bounds(mask):
    ys, xs = np.where(mask > 127)
    if len(xs) == 0:
        return None
    return xs.min(), xs.max(), ys.min(), ys.max()


def mask_to_piece(mask):
    bounds = find_shape_bounds(mask)
    if bounds is None:
        return None

    min_x, max_x, min_y, max_y = bounds
    shape = mask[min_y:max_y + 1, min_x:max_x + 1]

    h, w = shape.shape
    cols = w // CELL_SIZE
    rows = h // CELL_SIZE

    cells = []

    for row in range(rows):
        for col in range(cols):
            cell = shape[
                row * CELL_SIZE:(row + 1) * CELL_SIZE,
                col * CELL_SIZE:(col + 1) * CELL_SIZE
            ]

            if cell.size != CELL_SIZE * CELL_SIZE:
                continue

            white_ratio = np.sum(cell > 127) / cell.size
            if white_ratio > 0.6:
                cells.append([col, row])

    if not cells:
        return None


    return {
        "cells": cells,
    }


def read_hand(image_path):
    bg = hex_to_rgb("#395194")
    shadow = hex_to_rgb("#294184")
    tolerance = 20

    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    h, w = img.shape[:2]
    part_w = w // 3

    hand = []

    for slot in range(3):
        x0 = slot * part_w
        x1 = (slot + 1) * part_w if slot < 2 else w
        part = img[:, x0:x1]

        diff_bg = np.abs(part - bg)
        diff_sh = np.abs(part - shadow)

        mask = (
            np.any(diff_bg > tolerance, axis=2) &
            np.any(diff_sh > tolerance, axis=2)
        ).astype(np.uint8) * 255

        piece = mask_to_piece(mask)

        if piece is None:
            hand.append({
                "slot": slot,
                "empty": True
            })
        else:
            hand.append({
                "slot": slot,
                "empty": False,
                "piece": piece
            })

    return hand
