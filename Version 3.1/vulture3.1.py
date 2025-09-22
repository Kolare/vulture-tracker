import cv2
import numpy as np
import os
import tkinter as tk
from tkinter import filedialog
import math

# --- Configuration ---
CROP_BOX_SIZE = 50 
MAX_DISPLAY_WIDTH = 1600
MAX_DISPLAY_HEIGHT = 900
SAMPLE_RADII = [19, 20, 21]

# HSV thresholds used to find all possible health pixels
HEALTH_HUE_RANGES_CV = [ (0, 10), (170, 179), (20, 70) ] 
HEALTH_SATURATION_MIN = 80 # Slightly more lenient to catch all candidates
HEALTH_VALUE_MIN = 70      

def select_image_file():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(title="Select your screenshot file")

def analyze_health_final(roi_image_cv):
    height, width = roi_image_cv.shape[:2]
    center_x, center_y = width // 2, height // 2
    hsv_image = cv2.cvtColor(roi_image_cv, cv2.COLOR_BGR2HSV)
    
    # --- STAGE 1: Find ALL candidate health pixels ---
    # This finds every pixel that could be part of the bar, ignoring continuity for now.
    found_angles = set()
    scan_steps = 1440 # Quarter-degree precision
    
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

    # --- STAGE 2: Filter the found pixels for a continuous arc starting at 12 o'clock ---
    if not found_angles:
        return {"health_percent": 0.0, "arc_degrees": 0, "start_angle": -1}

    # Check for a strict start. Is there a health pixel within the first degree?
    if not any(0 <= a <= 1.0 for a in found_angles):
        return {"health_percent": 0.0, "arc_degrees": 0, "start_angle": -1}

    # Now trace the continuous arc from the start
    last_continuous_angle = 0.0
    gap_tolerance_degrees = 5
    step_size = 360.0 / scan_steps # 0.25 degrees
    
    for i in range(1, scan_steps):
        angle = i * step_size
        
        # Check if the current angle slice is missing
        is_gap = not any(angle - step_size < a <= angle for a in found_angles)
        
        if is_gap:
            # If the gap is too large, stop the trace
            if (angle - last_continuous_angle) > gap_tolerance_degrees:
                break
        else:
            last_continuous_angle = angle
            
    arc_degrees = last_continuous_angle
    # Handle perfect 100% case
    if arc_degrees > 360 - gap_tolerance_degrees:
        arc_degrees = 360

    health = (arc_degrees / 360) * 100
        
    return {"health_percent": health, "center": (center_x, center_y), "start_angle": 0, "arc_degrees": arc_degrees}

def main():
    path = select_image_file()
    if not path: return

    full_image = cv2.imread(path)
    if full_image is None: return
    
    h, w = full_image.shape[:2]
    x1_roi = (w - CROP_BOX_SIZE) // 2
    y1_roi = (h - CROP_BOX_SIZE) // 2
    
    center_roi = full_image[y1_roi:y1_roi+CROP_BOX_SIZE, x1_roi:x1_roi+CROP_BOX_SIZE]
    
    analysis_data = analyze_health_final(center_roi)
    
    display_image = full_image.copy()
    
    health = analysis_data["health_percent"]
    roi_center = analysis_data["center"]
    
    full_img_center = (roi_center[0] + x1_roi, roi_center[1] + y1_roi)
    print(f"Health determined to be: {health:.2f}%")

    cv2.rectangle(display_image, (x1_roi, y1_roi), (x1_roi + CROP_BOX_SIZE, y1_roi + CROP_BOX_SIZE), (0, 0, 255), 2)

    avg_radius = int(np.mean(SAMPLE_RADII))
    
    text = f"Health: {health:.2f}%"
    if health > 0:
        start_angle = analysis_data["start_angle"]
        arc_degrees = analysis_data["arc_degrees"]
        cv2.ellipse(display_image, full_img_center, (avg_radius, avg_radius), 270, start_angle, start_angle + arc_degrees, (0, 0, 255), 3)

    cv2.putText(display_image, text, (full_img_center[0] - 60, full_img_center[1] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    h, w = display_image.shape[:2]
    scale = min(MAX_DISPLAY_WIDTH / w, MAX_DISPLAY_HEIGHT / h) if h > MAX_DISPLAY_HEIGHT or w > MAX_DISPLAY_WIDTH else 1
    if scale < 1:
        display_image = cv2.resize(display_image, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)

    cv2.imshow("Health Analysis", display_image)
    while True:
        if cv2.waitKey(1) & 0xFF == ord('q') or cv2.getWindowProperty("Health Analysis", cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()