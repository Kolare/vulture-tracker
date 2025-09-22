import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageGrab
import sqlite3
import os
import datetime
import math
import cv2
import numpy as np
import keyboard
import threading
import queue
import time

# --- Health Analysis Module (Our perfected logic) ---
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

# --- Main Application ---
class VultureTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vulture Tracker v3")
        self.root.configure(bg="#111827")
        self.root.minsize(1200, 800)

        self.db_path = "vulture_tracker_v3.db"
        self.image_folder = "vulture_tracker_images_v3"
        os.makedirs(self.image_folder, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.create_tables()

        self.photo_references = {}
        self.last_capture_data = None
        self.capture_queue = queue.Queue()

        self.setup_styles()
        self.create_widgets()
        self.refresh_sietch_list()
        self.setup_hotkey_listener()
        self.check_capture_queue()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        # (Styling code omitted for brevity, but would be here)

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS sietches (name TEXT PRIMARY KEY)')
        cursor.execute('''CREATE TABLE IF NOT EXISTS locations (
                            id INTEGER PRIMARY KEY, sietch_name TEXT, location_id TEXT, 
                            pin_x INTEGER, pin_y INTEGER, 
                            FOREIGN KEY(sietch_name) REFERENCES sietches(name) ON DELETE CASCADE,
                            UNIQUE(sietch_name, location_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS objects (
                            id INTEGER PRIMARY KEY, location_fk INTEGER, object_id TEXT, 
                            FOREIGN KEY(location_fk) REFERENCES locations(id) ON DELETE CASCADE,
                            UNIQUE(location_fk, object_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
                            id INTEGER PRIMARY KEY, object_fk INTEGER, timestamp INTEGER, 
                            health_percent REAL, screenshot_path TEXT, 
                            FOREIGN KEY(object_fk) REFERENCES objects(id) ON DELETE CASCADE)''')
        self.conn.commit()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(main_frame, width=350)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)
        
        # --- Left Panel (Data Entry) ---
        form_frame = ttk.Frame(left_frame, padding=10)
        form_frame.pack(fill='x', pady=(0,10))
        ttk.Label(form_frame, text="Captured Data Point", font=('Arial', 14, 'bold')).grid(row=0, columnspan=2, pady=5, sticky='w')

        self.sietch_var, self.location_var, self.object_id_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        
        ttk.Label(form_frame, text="Sietch:").grid(row=1, column=0, sticky='w', pady=2)
        self.sietch_menu = ttk.Combobox(form_frame, textvariable=self.sietch_var, state="readonly")
        self.sietch_menu.grid(row=1, column=1, sticky='ew')
        self.sietch_menu.bind("<<ComboboxSelected>>", self.update_location_dropdown)

        ttk.Label(form_frame, text="Location ID:").grid(row=2, column=0, sticky='w', pady=2)
        self.location_menu = ttk.Combobox(form_frame, textvariable=self.location_var, state="readonly")
        self.location_menu.grid(row=2, column=1, sticky='ew')

        ttk.Label(form_frame, text="Object ID:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(form_frame, textvariable=self.object_id_var).grid(row=3, column=1, sticky='ew')

        self.capture_preview_label = ttk.Label(form_frame, text="Press Ctrl+Shift+H in-game...")
        self.capture_preview_label.grid(row=4, columnspan=2, pady=10)

        self.save_button = ttk.Button(form_frame, text="Save Captured Data", command=self.save_captured_data, state="disabled")
        self.save_button.grid(row=5, columnspan=2, sticky='ew', pady=5)
        
        # ... Other widgets for managing sietches, etc. would go here ...

        # --- Right Panel (Map and Data View) ---
        # (Simplified for this example, would contain map and treeview)
        ttk.Label(right_frame, text="Map and Data View Area", font=('Arial', 20)).pack(expand=True)


    def setup_hotkey_listener(self):
        hotkey_thread = threading.Thread(target=self.hotkey_worker, daemon=True)
        hotkey_thread.start()

    def hotkey_worker(self):
        def on_hotkey():
            try:
                screenshot_pil = ImageGrab.grab()
                screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
                h, w = screenshot_cv.shape[:2]
                x1 = (w - HealthAnalyzer.CROP_BOX_SIZE) // 2
                y1 = (h - HealthAnalyzer.CROP_BOX_SIZE) // 2
                roi = screenshot_cv[y1:y1+CROP_BOX_SIZE, x1:x1+CROP_BOX_SIZE]
                
                analysis = HealthAnalyzer.analyze(roi)
                timestamp = datetime.datetime.now()
                
                # Safely put data into the queue for the main thread
                self.capture_queue.put({
                    "health": analysis["health_percent"],
                    "timestamp": timestamp,
                    "roi_image": roi
                })
            except Exception as e:
                print(f"Hotkey error: {e}")

        keyboard.add_hotkey('ctrl+shift+h', on_hotkey)
        keyboard.wait('ctrl+shift+q') # This will block until quit hotkey

    def check_capture_queue(self):
        try:
            self.last_capture_data = self.capture_queue.get_nowait()
            self.populate_form_with_capture()
        except queue.Empty:
            pass # No new data
        finally:
            self.root.after(100, self.check_capture_queue) # Check again in 100ms

    def populate_form_with_capture(self):
        if not self.last_capture_data: return
        
        data = self.last_capture_data
        health = data["health"]
        ts = data["timestamp"].strftime("%Y-%m-%d %I:%M:%S %p")
        
        # Create a thumbnail of the ROI for display
        roi_pil = Image.fromarray(cv2.cvtColor(data["roi_image"], cv2.COLOR_BGR2RGB))
        roi_pil.thumbnail((100, 100))
        photo = ImageTk.PhotoImage(roi_pil)
        self.photo_references['capture'] = photo
        
        self.capture_preview_label.config(image=photo, text=f"Health: {health:.2f}%\n{ts}", compound='top')
        self.save_button.config(state="normal")
        print(f"Captured data ready in form: Health {health:.2f}%")

    def save_captured_data(self):
        if not self.last_capture_data:
            messagebox.showerror("Error", "No captured data to save.")
            return

        sietch = self.sietch_var.get()
        loc_id_str = self.location_var.get()
        obj_id_str = self.object_id_var.get().strip()

        if not all([sietch, loc_id_str, obj_id_str]):
            messagebox.showerror("Error", "Sietch, Location, and Object ID are required.")
            return

        try:
            cursor = self.conn.cursor()
            loc_fk = cursor.execute("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, loc_id_str)).fetchone()
            if not loc_fk:
                messagebox.showerror("Error", f"Location '{loc_id_str}' not found in Sietch '{sietch}'.")
                return
            loc_fk = loc_fk[0]

            cursor.execute("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (loc_fk, obj_id_str))
            obj_fk = cursor.execute("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_fk, obj_id_str)).fetchone()[0]

            # Save the ROI image
            ts = self.last_capture_data["timestamp"]
            filename = f"capture_{ts.strftime('%Y%m%d_%H%M%S')}.png"
            path = os.path.join(self.image_folder, filename)
            cv2.imwrite(path, self.last_capture_data["roi_image"])
            
            # Insert the history record
            cursor.execute("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)",
                           (obj_fk, int(ts.timestamp()), self.last_capture_data["health"], path))
            self.conn.commit()
            
            messagebox.showinfo("Success", "Data point saved successfully!")
            self.last_capture_data = None
            self.save_button.config(state="disabled")
            self.object_id_var.set("")
            # A full implementation would refresh the data view here
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def refresh_sietch_list(self):
        sietches = self.conn.cursor().execute("SELECT name FROM sietches ORDER BY name").fetchall()
        self.sietch_menu['values'] = [s[0] for s in sietches]

    def update_location_dropdown(self, event=None):
        sietch = self.sietch_var.get()
        locations = self.conn.cursor().execute("SELECT location_id FROM locations WHERE sietch_name=? ORDER BY location_id", (sietch,)).fetchall()
        self.location_menu['values'] = [l[0] for l in locations]
        self.location_var.set("")
    
    # ... Many other functions from V2.0 for map, treeview, decay, etc. would be added here ...

if __name__ == "__main__":
    root = tk.Tk()
    app = VultureTrackerApp(root)
    root.mainloop()