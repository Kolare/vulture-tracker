import cv2
import numpy as np
import time
import math
import colorsys
from PIL import ImageGrab
import keyboard 
import datetime
import os

# --- Configuration ---
CROP_BOX_SIZE = 50 
SAMPLE_RADII = [19, 20, 21]

# HSV thresholds
HEALTH_HUE_RANGES_CV = [ (0, 10), (170, 179), (20, 70) ] 
HEALTH_SATURATION_MIN = 80 
HEALTH_VALUE_MIN = 70      

def analyze_health_final(roi_image_cv):
    """
    Analyzes the provided ROI image and returns a dictionary with health data.
    """
    height, width = roi_image_cv.shape[:2]
    center_x, center_y = width // 2, height // 2
    hsv_image = cv2.cvtColor(roi_image_cv, cv2.COLOR_BGR2HSV)
    
    found_angles = set()
    scan_steps = 1440 
    
    for i in range(scan_steps):
        angle = i / (scan_steps / 360.0)
        rad = math.radians(angle)
        
        for radius in SAMPLE_RADII:
            x = int(round(center_x + radius * math.sin(rad)))
            y = int(round(center_y - radius * math.cos(rad)))

            if 0 <= x < width and 0 <= y < height:
                hue, sat, val = hsv_image[y, x]
                is_health_hue = any(lower <= hue <= upper for lower, upper in HEALTH_HUE_RANGES_CV)
                
                if is_health_hue and sat >= HEALTH_SATURATION_MIN and val >= HEALTH_VALUE_MIN:
                    found_angles.add(angle)
                    break 

    if not found_angles:
        return {"health_percent": 0.0}

    if not any(0 <= a <= 1.0 for a in found_angles):
        return {"health_percent": 0.0}

    last_continuous_angle = 0.0
    gap_tolerance_degrees = 5
    step_size = 360.0 / scan_steps
    
    for i in range(1, scan_steps):
        angle = i * step_size
        is_gap = not any(angle - step_size < a <= angle for a in found_angles)
        if is_gap:
            if (angle - last_continuous_angle) > gap_tolerance_degrees:
                break
        else:
            last_continuous_angle = angle
            
    arc_degrees = last_continuous_angle
    if arc_degrees > 360 - gap_tolerance_degrees:
        arc_degrees = 360

    health = (arc_degrees / 360) * 100
        
    return {"health_percent": health}

def trigger_analysis():
    """
    This function is called when the hotkey is pressed.
    It captures the screen, runs the analysis, and prints/saves the output.
    """
    print("\nHotkey detected! Analyzing...")
    try:
        timestamp = datetime.datetime.now()
        
        # --- THIS LINE HAS BEEN CHANGED for AM/PM format ---
        timestamp_str = timestamp.strftime("%Y-%m-%d %I:%M:%S %p")
        
        filename_ts = timestamp.strftime("%Y%m%d_%H%M%S")
        output_filename = f"capture_{filename_ts}.png"
        output_path = os.path.join("captures", output_filename)

        # 1. Capture the screen
        screenshot_pil = ImageGrab.grab()
        screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

        # 2. Crop to the central ROI
        h, w = screenshot_cv.shape[:2]
        x1_roi = (w - CROP_BOX_SIZE) // 2
        y1_roi = (h - CROP_BOX_SIZE) // 2
        center_roi = screenshot_cv[y1_roi:y1_roi+CROP_BOX_SIZE, x1_roi:x1_roi+CROP_BOX_SIZE]

        # 3. Save the 50px ROI to a file
        cv2.imwrite(output_path, center_roi)

        # 4. Run the analysis
        analysis_data = analyze_health_final(center_roi)
        health = analysis_data["health_percent"]
        
        # 5. Output all data to the console
        print("-----------------------------")
        print(f"Health: {health:.2f}%")
        print(f"Timestamp: {timestamp_str}")
        print(f"Saved to: {output_path}")
        print("-----------------------------")

    except Exception as e:
        print(f" -> An error occurred during analysis: {e}")

def main():
    """
    Sets up the output folder and hotkey listeners.
    """
    os.makedirs("captures", exist_ok=True)

    print("--- Vulture Health Analyzer ---")
    print("Output will be saved in the 'captures' subfolder.")
    print("Listener started.")
    print("Press 'Ctrl+Shift+H' to capture and analyze screen.")
    print("Press 'Ctrl+Shift+Q' to quit the script.")
    print("-----------------------------")
    
    keyboard.add_hotkey('ctrl+shift+h', trigger_analysis)
    keyboard.wait('ctrl+shift+q')
    
    print("\nQuit hotkey detected. Shutting down.")

if __name__ == "__main__":
    main()