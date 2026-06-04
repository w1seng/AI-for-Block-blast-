import threading
from ai import main as ai_main
from ui import run

if __name__ == "__main__":
    t = threading.Thread(target=ai_main, daemon=True)
    t.start()
    run()
