import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import math

# Assuming analyzer.py is in the same directory
from analyzer import HealthAnalyzer

class ManualTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vulture Tracker - Manual Analyzer Test")
        self.root.geometry("1000x800")

        self.filepath = None
        self.image_cv = None
        self.photo_image = None

        # --- UI Elements ---
        
        # Top Frame for controls
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10)

        self.btn_select = tk.Button(top_frame, text="Select Screenshot", command=self.select_file)
        self.btn_select.pack(side=tk.LEFT, padx=5)

        self.lbl_filepath = tk.Label(top_frame, text="No file selected.", width=60, anchor='w')
        self.lbl_filepath.pack(side=tk.LEFT, padx=5)

        self.btn_process = tk.Button(top_frame, text="Process Image", command=self.process_image, state=tk.DISABLED)
        self.btn_process.pack(side=tk.LEFT, padx=5)

        # Image display
        self.canvas = tk.Canvas(self.root, bg="gray")
        self.canvas.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)

        # Result display
        self.txt_result = tk.Text(self.root, height=6)
        self.txt_result.pack(pady=10, padx=10, fill=tk.X)

    def select_file(self):
        filepath = filedialog.askopenfilename(
            title="Select a screenshot",
            filetypes=(("PNG files", "*.png"), ("JPG files", "*.jpg"), ("All files", "*.*"))
        )
        if not filepath:
            return

        self.filepath = filepath
        self.lbl_filepath.config(text=self.filepath)
        self.btn_process.config(state=tk.NORMAL)
        
        # Display the selected image without debug info first
        self.image_cv = cv2.imread(self.filepath)
        if self.image_cv is None:
            messagebox.showerror("Error", f"Failed to load image: {self.filepath}")
            return
        self.display_image(self.image_cv)

    def process_image(self):
        if self.image_cv is None:
            messagebox.showerror("Error", "No image loaded to process.")
            return

        # --- Run Analysis ---
        try:
            result = HealthAnalyzer.analyze(self.image_cv.copy())
        except Exception as e:
            messagebox.showerror("Analysis Error", f"An error occurred during analysis: {e}")
            return
            
        # --- Create Debug Image ---
        debug_image = self.image_cv.copy()
        height, width = debug_image.shape[:2]
        center_x, center_y = width // 2, height // 2

        # 1. Draw the cyan scan path
        for radius in HealthAnalyzer.SAMPLE_RADII:
            cv2.circle(debug_image, (center_x, center_y), radius, (255, 255, 0), 1) # Cyan

        # 2. Draw the green start line (12 o'clock)
        cv2.line(debug_image, (center_x, center_y), (center_x, center_y - HealthAnalyzer.SAMPLE_RADII[-1]), (0, 255, 0), 2) # Green

        # 3. Draw the red end line
        health_percent = result.get('health_percent')
        if isinstance(health_percent, (int, float)):
            end_angle_deg = (health_percent / 100.0) * 360.0
            end_angle_rad = math.radians(end_angle_deg)
            
            end_x = int(round(center_x + HealthAnalyzer.SAMPLE_RADII[-1] * math.sin(end_angle_rad)))
            end_y = int(round(center_y - HealthAnalyzer.SAMPLE_RADII[-1] * math.cos(end_angle_rad)))
            cv2.line(debug_image, (center_x, center_y), (end_x, end_y), (0, 0, 255), 2) # Red

        # --- Display Results ---
        self.display_image(debug_image)
        
        result_text = (
            f"Health: {result.get('health_percent', 'N/A')}\n"
            f"Timestamp: {result.get('timestamp', 'N/A')}\n"
            f"Center Crop Shape: {result.get('center_crop').shape if result.get('center_crop') is not None else 'N/A'}"
        )
        self.txt_result.delete(1.0, tk.END)
        self.txt_result.insert(tk.END, result_text)

    def display_image(self, image_to_display_cv):
        # Resize image to fit canvas while maintaining aspect ratio
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width < 2 or canvas_height < 2: # Canvas not ready yet
            canvas_width, canvas_height = 900, 600 # Default size

        img_height, img_width = image_to_display_cv.shape[:2]
        aspect_ratio = img_width / img_height

        if (canvas_width / aspect_ratio) < canvas_height:
            new_width = canvas_width
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = canvas_height
            new_width = int(new_height * aspect_ratio)
            
        resized_image = cv2.resize(image_to_display_cv, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # Convert from CV2 BGR to PIL RGB format
        image_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        self.photo_image = ImageTk.PhotoImage(pil_image)

        self.canvas.delete("all")
        self.canvas.create_image(canvas_width/2, canvas_height/2, anchor=tk.CENTER, image=self.photo_image)


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ManualTestUI(root)
        
        def on_resize(event):
            if app.image_cv is not None:
                app.display_image(app.image_cv)

        app.canvas.bind('<Configure>', on_resize)
        
        root.mainloop()
    except ImportError:
        print("Tkinter or Pillow is not installed. Please install them to run this UI.")
        print("pip install pillow")
    except Exception as e:
        print(f"An error occurred: {e}")