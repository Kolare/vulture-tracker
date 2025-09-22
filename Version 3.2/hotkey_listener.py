import threading
import keyboard
import cv2
import numpy as np
from PIL import ImageGrab
from analyzer import HealthAnalyzer

CROP_BOX_SIZE = 50

def hotkey_worker(capture_queue, error_logger):
    """The function that runs in a separate thread to listen for hotkeys."""
    def on_hotkey():
        try:
            screenshot_pil = ImageGrab.grab()
            if screenshot_pil is None or screenshot_pil.size == (0, 0):
                raise ValueError("Failed to capture screen (ImageGrab returned None).")

            screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            h, w = screenshot_cv.shape[:2]
            
            if h < CROP_BOX_SIZE or w < CROP_BOX_SIZE:
                raise ValueError(f"Screenshot is too small ({w}x{h}) to crop a {CROP_BOX_SIZE}px box.")

            x1 = (w - CROP_BOX_SIZE) // 2
            y1 = (h - CROP_BOX_SIZE) // 2
            roi = screenshot_cv[y1:y1+CROP_BOX_SIZE, x1:x1+CROP_BOX_SIZE]
            
            # --- NEW: Final validation check on the cropped ROI ---
            if roi is None or roi.size == 0:
                raise ValueError("Cropped ROI is empty. Check screen capture integrity.")

            analysis = HealthAnalyzer.analyze(roi)
            
            import datetime
            timestamp = datetime.datetime.now()
            
            capture_queue.put({
                "health": analysis["health_percent"],
                "timestamp": timestamp,
                "roi_image": roi
            })
        except Exception:
            import traceback
            error_details = traceback.format_exc()
            capture_queue.put({"error": error_details})

    keyboard.add_hotkey('ctrl+shift+h', on_hotkey)
    print("Hotkey listener ready. Press Ctrl+Shift+Q in this terminal to exit.")
    keyboard.wait('ctrl+shift+q')

def start_hotkey_listener(capture_queue, error_logger):
    """Creates and starts the hotkey listener thread."""
    hotkey_thread = threading.Thread(target=hotkey_worker, args=(capture_queue, error_logger), daemon=True)
    hotkey_thread.start()
    print("Hotkey listener thread started.")