import threading
import keyboard
import cv2
import numpy as np
from PIL import ImageGrab
import os

# Assuming analyzer.py is in the same directory or accessible
from analyzer import HealthAnalyzer

def hotkey_worker(capture_queue, error_logger):
    """The function that runs in a separate thread to listen for hotkeys."""
    CROP_SAVE_DIR = os.path.join("Version 3.2", "crops")
    
    # Ensure the crop directory exists at startup
    os.makedirs(CROP_SAVE_DIR, exist_ok=True)

    def on_hotkey():
        """
        This function is called when the hotkey is pressed.
        It captures the screen, runs the analysis, saves the crop, and prints the result.
        """
        print("\nHotkey 'ctrl+shift+h' detected. Starting analysis...")
        try:
            # 1. Capture the entire screen
            screenshot_pil = ImageGrab.grab()
            if screenshot_pil is None or screenshot_pil.size == (0, 0):
                raise ValueError("Failed to capture screen (ImageGrab returned None).")

            screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

            # 2. Analyze the full screenshot using the new analyzer
            analysis_result = HealthAnalyzer.analyze(screenshot_cv)
            
            # 3. Print results for immediate user feedback
            print(f"Analysis complete: Health: {analysis_result['health_percent']}, Timestamp: {analysis_result['timestamp']}")

            # 4. Save the center crop image
            crop_image = analysis_result.get('center_crop')
            if crop_image is not None and crop_image.size > 0:
                timestamp_str = analysis_result['timestamp'].strftime("%Y%m%d_%H%M%S_%f")
                filename = os.path.join(CROP_SAVE_DIR, f"crop_{timestamp_str}.png")
                cv2.imwrite(filename, crop_image)
                print(f"Saved center crop to: {filename}")
                # Add filename to the result for the main app to use
                analysis_result['crop_filepath'] = filename
            else:
                print("Warning: Analyzer did not return a valid crop image to save.")

            # 5. Put the full analysis result into the queue for the main application
            capture_queue.put(analysis_result)

        except Exception:
            import traceback
            error_details = traceback.format_exc()
            print(f"An error occurred in on_hotkey:\n{error_details}")
            # Still put an error in the queue so the main thread knows something happened
            capture_queue.put({"error": error_details})

    keyboard.add_hotkey('ctrl+shift+h', on_hotkey)
    print(f"Hotkey listener ready. Press Ctrl+Shift+H to analyze. Crops will be saved in '{CROP_SAVE_DIR}'.")
    print("Press Ctrl+Shift+Q in this terminal to exit.")
    keyboard.wait('ctrl+shift+q')

def start_hotkey_listener(capture_queue, error_logger):
    """Creates and starts the hotkey listener thread."""
    hotkey_thread = threading.Thread(target=hotkey_worker, args=(capture_queue, error_logger), daemon=True)
    hotkey_thread.start()
    print("Hotkey listener thread started.")