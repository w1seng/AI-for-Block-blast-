import mss
import numpy as np
import cv2
import json
import os
from datetime import datetime

CONFIG_FILE = "screenshot_regions.json"


def select_and_save_regions(num_regions=2):
    regions = []
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        screenshot = np.array(sct.grab(monitor))
        img = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    scale = 0.7
    display_img = cv2.resize(img, None, fx=scale, fy=scale)

    for i in range(num_regions):
        print(f"\n=== Select region {i+1} of {num_regions} ===")
        print("- Click and drag with the mouse")
        print("- Press 'Enter' or 'Space' to confirm")
        print("- Press 'Esc' to cancel")

        preview = display_img.copy()
        for j, prev_region in enumerate(regions):
            x = int(prev_region["x"] * scale)
            y = int(prev_region["y"] * scale)
            w = int(prev_region["w"] * scale)
            h = int(prev_region["h"] * scale)
            cv2.rectangle(preview, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(preview, f"Region {j+1}", (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        roi = cv2.selectROI(f"Select region {i+1}", preview, fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()

        if roi[2] == 0 or roi[3] == 0:
            print("Selection cancelled")
            return None

        rect = {
            "x": int(roi[0] / scale),
            "y": int(roi[1] / scale),
            "w": int(roi[2] / scale),
            "h": int(roi[3] / scale)
        }

        regions.append(rect)
        print(f"✓ Region {i+1} saved: x={rect['x']}, y={rect['y']}, w={rect['w']}, h={rect['h']}")

    with open(CONFIG_FILE, 'w') as f:
        json.dump(regions, f, indent=2)

    print(f"\n✓ All {num_regions} regions saved to {CONFIG_FILE}")

    for i, rect in enumerate(regions):
        preview = grab_region(rect)
        cv2.imshow(f"Region {i+1} - press any key", preview)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return regions


def load_regions():
    """Loads saved region coordinates."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: File {CONFIG_FILE} not found!")
        print("Please run select_and_save_regions() first to select regions")
        return None

    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def grab_region(rect):
    """Takes a screenshot of the specified screen region."""
    with mss.mss() as sct:
        monitor = {
            "left": rect["x"],
            "top": rect["y"],
            "width": rect["w"],
            "height": rect["h"]
        }
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def take_screenshots(prefix=None):
    """Takes screenshots of all saved regions and saves them."""
    regions = load_regions()
    if regions is None:
        return None

    screenshots = []

    for i, rect in enumerate(regions):
        screenshot = grab_region(rect)

        filename = "board.png" if i == 0 else "hand.png"

        cv2.imwrite(filename, screenshot)
        screenshots.append(screenshot)

    return screenshots


def take_screenshot_region(region_num, filename=None):
    """Takes a screenshot of a specific region (1, 2, 3...)."""
    regions = load_regions()
    if regions is None:
        return None

    if region_num < 1 or region_num > len(regions):
        print(f"Error: region {region_num} does not exist (available 1-{len(regions)})")
        return None

    rect = regions[region_num - 1]
    screenshot = grab_region(rect)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_region{region_num}_{timestamp}.png"
    elif not filename.endswith('.png'):
        filename += '.png'

    cv2.imwrite(filename, screenshot)
    return screenshot


if __name__ == "__main__":
    print("=== Screenshot region setup ===")
    select_and_save_regions(2)
