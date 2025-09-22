import cv2
import numpy as np
import math

class HealthAnalyzer:
    CROP_BOX_SIZE = 50
    SAMPLE_RADII = [19, 20, 21]
    HEALTH_HUE_RANGES_CV = [(0, 10), (170, 179), (20, 70)]
    HEALTH_SATURATION_MIN = 80
    HEALTH_VALUE_MIN = 70

    @staticmethod
    def analyze(roi_image_cv):
        height, width = roi_image_cv.shape[:2]
        center_x, center_y = width // 2, height // 2
        hsv_image = cv2.cvtColor(roi_image_cv, cv2.COLOR_BGR2HSV)
        
        found_angles = set()
        scan_steps = 1440
        
        for i in range(scan_steps):
            angle = i / (scan_steps / 360.0)
            rad = math.radians(angle)
            for radius in HealthAnalyzer.SAMPLE_RADII:
                x = int(round(center_x + radius * math.sin(rad)))
                y = int(round(center_y - radius * math.cos(rad)))
                if 0 <= x < width and 0 <= y < height:
                    hue, sat, val = hsv_image[y, x]
                    is_health_hue = any(lower <= hue <= upper for lower, upper in HealthAnalyzer.HEALTH_HUE_RANGES_CV)
                    if is_health_hue and sat >= HealthAnalyzer.HEALTH_SATURATION_MIN and val >= HealthAnalyzer.HEALTH_VALUE_MIN:
                        found_angles.add(angle)
                        break
        
        if not found_angles or not any(0 <= a <= 1.0 for a in found_angles):
            return {"health_percent": 0.0}

        last_continuous_angle = 0.0
        gap_tolerance_degrees = 5
        step_size = 360.0 / scan_steps
        for i in range(1, scan_steps):
            angle = i * step_size
            if not any(angle - step_size < a <= angle for a in found_angles):
                if (angle - last_continuous_angle) > gap_tolerance_degrees:
                    break
            else:
                last_continuous_angle = angle
        
        arc_degrees = last_continuous_angle
        if arc_degrees > 360 - gap_tolerance_degrees:
            arc_degrees = 360
        health = (arc_degrees / 360) * 100
        return {"health_percent": health}