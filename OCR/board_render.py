import cv2
import json
import numpy as np


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def color_match(color1, color2, tolerance=30):
    return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))


def analyze_board_cv(image_path, target_color='#182442', tolerance=40):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    height, width = img.shape[:2]

    cell_width  = width  / 8
    cell_height = height / 8

    target_rgb = hex_to_rgb(target_color)

    OFFSETS = [0.30, 0.50, 0.70]
    grid = []

    for row in range(8):
        row_data = []
        for col in range(8):
            votes_bg    = 0
            votes_block = 0
            for oy in OFFSETS:
                for ox in OFFSETS:
                    px = int(col * cell_width  + ox * cell_width)
                    py = int(row * cell_height + oy * cell_height)
                    px = min(px, width  - 1)
                    py = min(py, height - 1)
                    pixel = tuple(img[py, px])
                    if color_match(pixel, target_rgb, tolerance):
                        votes_bg += 1
                    else:
                        votes_block += 1

            row_data.append(0 if votes_bg > votes_block else 1)
        grid.append(row_data)

    return {"grid": grid}
