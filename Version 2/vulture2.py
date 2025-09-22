import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import sqlite3
import os
import datetime
import json
import shutil
import math
import base64
import re
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import colorsys

try:
    from tkcalendar import Calendar
except ImportError:
    messagebox.showerror("Missing Library", "The 'tkcalendar' library is required. Please install it by running: pip install tkcalendar")
    exit()

# Helper class to make a frame scrollable
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg="#1f2937", highlightthickness=0, yscrollincrement=1)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.bind('<Enter>', self._bind_mousewheel)
        self.canvas.bind('<Leave>', self._unbind_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

    def _on_mousewheel(self, event):
        if not self.canvas.winfo_exists(): return
        if hasattr(event, 'delta'):
             self.canvas.yview_scroll(int(-1*(event.delta/120) * 80), "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-80, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(80, "units")
    
    def _bind_mousewheel(self, event):
        self.winfo_toplevel().bind_all("<MouseWheel>", self._on_mousewheel)
        self.winfo_toplevel().bind_all("<Button-4>", self._on_mousewheel)
        self.winfo_toplevel().bind_all("<Button-5>", self._on_mousewheel)
    
    def _unbind_mousewheel(self, event):
        self.winfo_toplevel().unbind_all("<MouseWheel>")
        self.winfo_toplevel().unbind_all("<Button-4>")
        self.winfo_toplevel().unbind_all("<Button-5>")


class VultureTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vulture List v2 - Cetralise's Vulture Tracker")
        self.root.configure(bg="#111827")
        self.root.minsize(1200, 800)

        self.db_path = "vulture_tracker.db"
        self.image_folder = "vulture_tracker_images"
        os.makedirs(self.image_folder, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = 1")
        self.create_tables()

        self.photo_references = {} 
        self.active_detail_frame = None
        self.sietch_frames = {}

        self.setup_styles()
        self.create_widgets()
        self.refresh_all_ui()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure(".", background="#1f2937", foreground="#d1d5db", font=('Arial', 10))
        self.style.configure("TFrame", background="#1f2937")
        self.style.configure("TLabel", background="#1f2937", foreground="#d1d5db", font=('Arial', 10))
        self.style.configure("Header.TLabel", font=('Arial', 14, 'bold'), foreground="#67e8f9")
        self.style.configure("Subheader.TLabel", font=('Arial', 11, 'bold'), foreground="#a5f3fc")
        self.style.configure("TButton", background="#0e7490", foreground="white", font=('Arial', 10, 'bold'), borderwidth=0, padding=5)
        self.style.map("TButton", background=[('active', '#0891b2')])
        self.style.configure("Red.TButton", background="#be123c", foreground="white")
        self.style.map("Red.TButton", background=[('active', '#9f1239')])
        self.style.configure("Yellow.TButton", background="#ca8a04", foreground="white")
        self.style.map("Yellow.TButton", background=[('active', '#a16207')])
        self.style.configure("TEntry", fieldbackground="#374151", foreground="#d1d5db", bordercolor="#4b5563", insertcolor="#d1d5db")
        self.style.configure("TCombobox", fieldbackground="#374151", foreground="#d1d5db", bordercolor="#4b5563", arrowcolor="#9ca3af")
        self.style.configure("Treeview", background="#1f2937", foreground="#d1d5db", fieldbackground="#1f2937", rowheight=25, font=('Arial', 9))
        self.style.map("Treeview", background=[('selected', '#0e7490')])
        self.style.configure("Treeview.Heading", background="#374151", foreground="#d1d5db", font=('Arial', 10, 'bold'))

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS sietches (name TEXT PRIMARY KEY)')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS locations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            sietch_name TEXT, 
                            location_id TEXT, 
                            pin_x INTEGER, 
                            pin_y INTEGER, 
                            FOREIGN KEY(sietch_name) REFERENCES sietches(name) ON DELETE CASCADE, 
                            UNIQUE(sietch_name, location_id))''')

        cursor.execute("PRAGMA table_info(locations)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'pin_x' not in columns:
            cursor.execute("ALTER TABLE locations ADD COLUMN pin_x INTEGER")
        if 'pin_y' not in columns:
            cursor.execute("ALTER TABLE locations ADD COLUMN pin_y INTEGER")
        try:
            if 'map_screenshot_path' in columns:
                pass
        except sqlite3.OperationalError:
            pass 

        cursor.execute('''CREATE TABLE IF NOT EXISTS objects (id INTEGER PRIMARY KEY AUTOINCREMENT, location_fk INTEGER, object_id TEXT, total_hp INTEGER, object_screenshot_path TEXT, FOREIGN KEY(location_fk) REFERENCES locations(id) ON DELETE CASCADE, UNIQUE(location_fk, object_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, object_fk INTEGER, timestamp INTEGER, health_percent REAL, screenshot_path TEXT, FOREIGN KEY(object_fk) REFERENCES objects(id) ON DELETE CASCADE)''')
        self.conn.commit()

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, background="#1f2937", foreground="#d1d5db")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Main Map Image...", command=self.set_main_map_image)
        file_menu.add_command(label="Import from Web App Backup...", command=self.import_from_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        left_frame = ttk.Frame(main_frame, width=350)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)
        
        self.right_scroll_frame = ScrollableFrame(main_frame)
        self.right_scroll_frame.pack(side="right", fill="both", expand=True)
        self.right_content_frame = self.right_scroll_frame.scrollable_frame

        # --- Left Panel ---
        form_frame = ttk.Frame(left_frame, padding=10)
        form_frame.pack(fill='x', pady=(0,10))
        ttk.Label(form_frame, text="Add New Data Point", style="Header.TLabel").grid(row=0, column=0, columnspan=3, pady=5, sticky='w')
        
        self.sietch_var, self.location_id_var, self.object_id_var, self.total_hp_var, self.screenshot_path_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.timestamp_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"))
        
        ttk.Label(form_frame, text="Sietch:").grid(row=1, column=0, sticky='w', pady=2)
        self.sietch_menu = ttk.Combobox(form_frame, textvariable=self.sietch_var, state="readonly", width=25)
        self.sietch_menu.grid(row=1, column=1, columnspan=2, sticky='ew', pady=2)
        self.sietch_menu.bind("<<ComboboxSelected>>", self.on_sietch_select)

        ttk.Label(form_frame, text="Location ID:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(form_frame, textvariable=self.location_id_var).grid(row=2, column=1, columnspan=2, sticky='ew', pady=2)
        ttk.Label(form_frame, text="Object ID:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(form_frame, textvariable=self.object_id_var).grid(row=3, column=1, columnspan=2, sticky='ew', pady=2)
        ttk.Label(form_frame, text="Screenshot:").grid(row=4, column=0, sticky='w', pady=2)
        sf = ttk.Frame(form_frame); sf.grid(row=4, column=1, columnspan=2, sticky='ew')
        self.screenshot_label = ttk.Label(sf, text="No file selected.", width=18, wraplength=150); self.screenshot_label.pack(side='left', fill='x', expand=True)
        ttk.Button(sf, text="...", command=self.browse_screenshot, width=4).pack(side='right')
        
        ttk.Label(form_frame, text="Timestamp:").grid(row=5, column=0, sticky='w', pady=2)
        ts_frame = ttk.Frame(form_frame); ts_frame.grid(row=5, column=1, columnspan=2, sticky='ew')
        ttk.Entry(ts_frame, textvariable=self.timestamp_var).pack(side='left', fill='x', expand=True)
        ttk.Button(ts_frame, text="Now", command=self.set_timestamp_now, width=4).pack(side='left', padx=(5,2))
        ttk.Button(ts_frame, text="...", command=self.open_date_picker, width=3).pack(side='left')


        ttk.Label(form_frame, text="Total HP:").grid(row=6, column=0, sticky='w', pady=2)
        ttk.Entry(form_frame, textvariable=self.total_hp_var).grid(row=6, column=1, columnspan=2, sticky='ew', pady=2)
        ttk.Button(form_frame, text="Analyze & Add Data", command=self.add_data_point).grid(row=7, column=0, columnspan=3, sticky='ew', pady=10)

        self.analysis_label = ttk.Label(left_frame, text="", wraplength=330)
        self.analysis_label.pack(fill='x', padx=10)
        self.debug_image_label = ttk.Label(left_frame)
        self.debug_image_label.pack(fill='x', padx=10, pady=5)

        sietch_manage_frame = ttk.Frame(left_frame, padding=10)
        sietch_manage_frame.pack(fill='x', pady=10)
        ttk.Label(sietch_manage_frame, text="Manage Sietches", style="Header.TLabel").pack(fill='x', pady=5)
        self.new_sietch_var = tk.StringVar()
        ttk.Entry(sietch_manage_frame, textvariable=self.new_sietch_var).pack(fill='x', pady=(0, 5))
        ttk.Button(sietch_manage_frame, text="Add Sietch", command=self.add_sietch).pack(fill='x')

        # --- Right Panel Content ---
        self.map_frame = MapFrame(self.right_content_frame, self)
        self.map_frame.pack(fill='x', anchor='n')

        dashboard_frame = ttk.Frame(self.right_content_frame, padding=10)
        dashboard_frame.pack(fill='x', anchor='n')
        ttk.Label(dashboard_frame, text="Priority Watchlist", style="Header.TLabel").pack(anchor='w')
        self.dashboard_tree = ttk.Treeview(dashboard_frame, columns=("Sietch", "Location", "Object", "Health", "Decay", "obj_pk"), displaycolumns=("Sietch", "Location", "Object", "Health", "Decay"), show="headings", height=4)
        for col in self.dashboard_tree['columns']: 
            if col != "obj_pk":
                self.dashboard_tree.heading(col, text=col)
                self.dashboard_tree.column(col, width=120, anchor='w')
        self.dashboard_tree.pack(fill='x', pady=5, expand=True)
        self.dashboard_tree.bind("<<TreeviewSelect>>", self.on_dashboard_select)
        
        self.overview_container = ttk.Frame(self.right_content_frame, padding=10)
        self.overview_container.pack(fill='both', expand=True, anchor='n')
        ttk.Label(self.overview_container, text="Sietch Overview", style="Header.TLabel").pack(anchor='w')

    def set_main_map_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if path:
            dest_path = os.path.join(self.image_folder, "main_map" + os.path.splitext(path)[1])
            shutil.copy(path, dest_path)
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("main_map_path", dest_path))
            self.conn.commit()
            self.map_frame.load_map()

    def open_date_picker(self):
        def on_date_select(selected_date_str):
            self.timestamp_var.set(selected_date_str)
        try:
            initial_date = datetime.datetime.strptime(self.timestamp_var.get(), "%Y-%m-%d %I:%M %p")
        except ValueError:
            initial_date = datetime.datetime.now()
        DatePicker(self.root, on_date_select, initial_date)

    def on_sietch_select(self, event=None):
        self.location_id_var.set("")
        self.object_id_var.set("")

    def set_timestamp_now(self):
        self.timestamp_var.set(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"))

    def on_dashboard_select(self, event):
        selection = self.dashboard_tree.selection()
        if not selection: return
        item_values = self.dashboard_tree.item(selection[0], 'values')
        if not item_values: return
        
        obj_pk = item_values[-1] 
        
        sietch_name = item_values[0]
        if sietch_name in self.sietch_frames:
            sietch_frame = self.sietch_frames[sietch_name]
            if not sietch_frame.is_open:
                sietch_frame.toggle_expand()
            
            if obj_pk in sietch_frame.object_frames:
                object_frame = sietch_frame.object_frames[obj_pk]
                object_frame.toggle_details()
                self.right_scroll_frame.update_idletasks()
                self.right_scroll_frame.canvas.yview_moveto(object_frame.winfo_y() / self.right_scroll_frame.scrollable_frame.winfo_height())

    def focus_on_location(self, loc_pk):
        row = self.conn.cursor().execute("SELECT sietch_name FROM locations WHERE id=?", (loc_pk,)).fetchone()
        if not row: return
        sietch_name = row[0]

        if sietch_name in self.sietch_frames:
            sietch_frame = self.sietch_frames[sietch_name]
            if not sietch_frame.is_open:
                sietch_frame.toggle_expand()
            
            if str(loc_pk) in sietch_frame.location_frames:
                location_frame = sietch_frame.location_frames[str(loc_pk)]
                self.right_scroll_frame.update_idletasks()
                self.right_scroll_frame.canvas.yview_moveto(location_frame.winfo_y() / self.right_scroll_frame.scrollable_frame.winfo_height())


    def add_data_point(self):
        try:
            sietch, loc_id_str, obj_id_str, screenshot_path = self.sietch_var.get(), self.location_id_var.get().strip(), self.object_id_var.get().strip(), self.screenshot_path_var.get()
            if not all([sietch, loc_id_str, obj_id_str, screenshot_path]): raise ValueError("All fields are required.")
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"health_{sietch}_{loc_id_str}_{obj_id_str}_{timestamp_str}{os.path.splitext(screenshot_path)[1]}"
            new_path = os.path.join(self.image_folder, filename)
            shutil.copy(screenshot_path, new_path)
            analysis = self.analyze_image(new_path, draw_debug=True)
            health_percent = analysis['health_percent']
            cursor = self.conn.cursor()
            
            loc_fk_row = cursor.execute("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, loc_id_str)).fetchone()
            if not loc_fk_row:
                raise ValueError(f"Location '{loc_id_str}' does not exist in Sietch '{sietch}'. Please add it via the map first.")
            loc_fk = loc_fk_row[0]

            cursor.execute("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (loc_fk, obj_id_str))
            obj_fk = cursor.execute("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_fk, obj_id_str)).fetchone()[0]
            timestamp = int(datetime.datetime.strptime(self.timestamp_var.get(), "%Y-%m-%d %I:%M %p").timestamp())
            cursor.execute("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)", (obj_fk, timestamp, health_percent, new_path))
            if self.total_hp_var.get(): cursor.execute("UPDATE objects SET total_hp=? WHERE id=?", (int(self.total_hp_var.get()), obj_fk))
            self.conn.commit()
            self.analysis_label.config(text=f"Success! Health: {health_percent:.2f}%.", foreground="lime")
            self.refresh_all_ui()
        except Exception as e:
            self.analysis_label.config(text=f"Error: {e}", foreground="red")

    def browse_screenshot(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if path:
            self.screenshot_path_var.set(path)
            self.screenshot_label.config(text=os.path.basename(path))
            match = re.search(r'(\d{4}-\d{2}-\d{2})[ _](\d{2})(\d{2})(\d{2})', os.path.basename(path))
            if match: 
                ts_24hr = datetime.datetime.strptime(f"{match.group(1)} {match.group(2)}:{match.group(3)}", "%Y-%m-%d %H:%M")
                self.timestamp_var.set(ts_24hr.strftime("%Y-%m-%d %I:%M %p"))

    def add_sietch(self):
        new_sietch = self.new_sietch_var.get().strip()
        if new_sietch:
            try:
                self.conn.cursor().execute("INSERT INTO sietches (name) VALUES (?)", (new_sietch,))
                self.conn.commit()
                self.new_sietch_var.set("")
                self.refresh_all_ui()
            except sqlite3.IntegrityError: messagebox.showwarning("Duplicate", "Sietch name already exists.")

    def import_from_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not path: return
        if not messagebox.askyesno("Confirm Import", "This will ERASE all current data..."): return
        with open(path, 'r') as f: data = json.load(f)
        cursor = self.conn.cursor()
        for table in ["history", "objects", "locations", "sietches"]: cursor.execute(f"DELETE FROM {table}")
        for sietch_name in data.get('sietches', []): cursor.execute("INSERT INTO sietches (name) VALUES (?)", (sietch_name,))
        
        for item_key, item_data in data.get('items', {}).items():
            sietch, loc_id, obj_id = item_data['sietch'], item_data['locationId'], item_data['objectId']
            cursor.execute("INSERT OR IGNORE INTO locations (sietch_name, location_id) VALUES (?, ?)", (sietch, loc_id))
            loc_fk = cursor.execute("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, loc_id)).fetchone()[0]
            obj_ss_path = self.save_base64_image(item_data['objectScreenshotURL']) if item_data.get('objectScreenshotURL') else None
            cursor.execute("INSERT OR IGNORE INTO objects (location_fk, object_id, total_hp, object_screenshot_path) VALUES (?, ?, ?, ?)", (loc_fk, obj_id, item_data.get('totalHp'), obj_ss_path))
            obj_fk = cursor.execute("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_fk, obj_id)).fetchone()[0]
            for entry in item_data.get('history', []):
                new_path = self.save_base64_image(entry['screenshotDataURL'])
                cursor.execute("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)", (obj_fk, entry['timestamp'] / 1000, entry['healthPercent'], new_path))
        self.conn.commit()
        self.refresh_all_ui()
        messagebox.showinfo("Success", "Data imported successfully! Please place pins for any imported locations on the map.")

    def save_base64_image(self, b64_string):
        if not b64_string or "base64," not in b64_string: return None
        try:
            header, encoded = b64_string.split(",", 1)
            data = base64.b64decode(encoded)
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"imported_{timestamp_str}.jpg"
            path = os.path.join(self.image_folder, filename)
            with open(path, "wb") as f: f.write(data)
            return path
        except Exception:
            return None
    
    def analyze_image(self, image_path, draw_debug=False):
        img = Image.open(image_path).convert('RGBA')
        data = list(img.getdata())
        width, height = img.size
        
        marker_pixels = []
        marker_rgb = [(255, 245, 230), (253, 255, 230), (240, 255, 230), (230, 240, 255), (233, 230, 255)]
        for i, p in enumerate(data):
            r, g, b, a = p
            if a < 200: continue
            for mr, mg, mb in marker_rgb:
                if math.sqrt((r - mr)**2 + (g - mg)**2 + (b - mb)**2) < 45:
                    marker_pixels.append({'x': i % width, 'y': i // width}); break
        
        if len(marker_pixels) < 10: raise ValueError("Not enough marker-colored pixels found.")
        clusters, visited = [], set()
        for pixel in marker_pixels:
            pixel_key = f"{pixel['x']},{pixel['y']}"
            if pixel_key in visited: continue
            new_cluster, queue = [], [pixel]
            visited.add(pixel_key)
            head = 0
            while head < len(queue):
                current = queue[head]; head += 1
                new_cluster.append(current)
                for neighbor in marker_pixels:
                    neighbor_key = f"{neighbor['x']},{neighbor['y']}"
                    if neighbor_key not in visited and (current['x']-neighbor['x'])**2 + (current['y']-neighbor['y'])**2 < 8**2:
                        visited.add(neighbor_key); queue.append(neighbor)
            clusters.append(new_cluster)
        
        valid_clusters = [c for c in clusters if len(c) > 2]
        if len(valid_clusters) < 4: raise ValueError(f"Found only {len(valid_clusters)} of 4 white markers.")

        cluster_centers = [{'x': sum(p['x'] for p in c)/len(c), 'y': sum(p['y'] for p in c)/len(c)} for c in valid_clusters]
        
        initial_rough_center = {'x': sum(c['x'] for c in cluster_centers)/len(cluster_centers), 'y': sum(c['y'] for c in cluster_centers)/len(cluster_centers)}
        distances = [math.hypot(c['x']-initial_rough_center['x'], c['y']-initial_rough_center['y']) for c in cluster_centers]
        avg_dist = sum(distances) / len(distances)
        inlier_centers = [cluster_centers[i] for i, dist in enumerate(distances) if dist < avg_dist * 1.5]
        if len(inlier_centers) < 4: raise ValueError("Could not find a stable center point (too many outliers).")
        rough_center = {'x': sum(c['x'] for c in inlier_centers)/len(inlier_centers), 'y': sum(c['y'] for c in inlier_centers)/len(inlier_centers)}


        quadrants = {'tl': [], 'tr': [], 'bl': [], 'br': []}
        for center in inlier_centers:
            if center['x'] < rough_center['x'] and center['y'] < rough_center['y']: quadrants['tl'].append(center)
            elif center['x'] > rough_center['x'] and center['y'] < rough_center['y']: quadrants['tr'].append(center)
            elif center['x'] < rough_center['x'] and center['y'] > rough_center['y']: quadrants['bl'].append(center)
            elif center['x'] > rough_center['x'] and center['y'] > rough_center['y']: quadrants['br'].append(center)
        
        if not all(quadrants.values()): raise ValueError("Could not isolate marker in each quadrant.")
        
        def find_furthest(q): return max(q, key=lambda p: math.hypot(p['x']-rough_center['x'], p['y']-rough_center['y']))
        final_markers = {k: find_furthest(v) for k, v in quadrants.items()}
        
        def find_intersection(p1, p2, p3, p4):
            den = (p1['x'] - p2['x']) * (p3['y'] - p4['y']) - (p1['y'] - p2['y']) * (p3['x'] - p4['x'])
            if den == 0: return None
            t = ((p1['x'] - p3['x']) * (p3['y'] - p4['y']) - (p1['y'] - p3['y']) * (p3['x'] - p4['x'])) / den
            return {'x': p1['x'] + t * (p2['x'] - p1['x']), 'y': p1['y'] + t * (p2['y'] - p1['y'])}

        intersection = find_intersection(final_markers['tl'], final_markers['br'], final_markers['tr'], final_markers['bl'])
        if not intersection: raise ValueError("Could not find marker intersection.")
        
        center_x, center_y = intersection['x'], intersection['y']
        avg_radius = sum(math.hypot(p['x']-center_x, p['y']-center_y) for p in final_markers.values()) / 4
        sample_radius = avg_radius * 2.5

        first_angle, last_angle = -1, -1
        gap_counter, gap_tolerance_degrees = 0, 5

        def rgb_to_hsv(r,g,b):
             return colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

        def is_health_color(r, g, b):
            h, s, v = rgb_to_hsv(r,g,b)
            is_health_hue = (h*360 <= 130) or (h*360 >= 350) 
            is_saturated = s > 0.4
            is_bright = v > 0.3
            return is_health_hue and is_saturated and is_bright

        for angle_deg in range(0, 720):
            angle = angle_deg / 2.0
            rad = math.radians(angle)
            x, y = int(round(center_x + sample_radius * math.sin(rad))), int(round(center_y - sample_radius * math.cos(rad)))
            
            is_pixel_health_color = False
            if 0 <= x < width and 0 <= y < height:
                r, g, b, a = data[y * width + x]
                if a > 200 and is_health_color(r,g,b):
                    is_pixel_health_color = True
            
            if is_pixel_health_color:
                if first_angle == -1:
                    first_angle = angle
                last_angle = angle
                gap_counter = 0 
            elif first_angle != -1:
                gap_counter += 0.5 
                if gap_counter > gap_tolerance_degrees:
                    break 

        if last_angle == -1:
            health = 0.01 
        elif first_angle < 5 and last_angle > (360 - gap_tolerance_degrees - 5):
            health = 100.0 
        else:
            health = (last_angle / 360) * 100

        if draw_debug:
            display_width = 300
            scale = display_width / width
            display_height = int(height * scale)
            
            debug_img = img.copy().resize((display_width, display_height))
            draw = ImageDraw.Draw(debug_img)
            
            cx_s, cy_s = center_x * scale, center_y * scale
            r_s = sample_radius * scale

            draw.ellipse([(cx_s - r_s, cy_s - r_s), (cx_s + r_s, cy_s + r_s)], outline="cyan", width=1)
            draw.point((cx_s, cy_s), fill="yellow")
            draw.line([(cx_s, cy_s), (cx_s, cy_s - r_s)], fill="lime", width=2)
            end_rad = math.radians(health * 3.6)
            end_x, end_y = cx_s + r_s * math.sin(end_rad), cy_s - r_s * math.cos(end_rad)
            draw.line([(cx_s, cy_s), (end_x, end_y)], fill="red", width=2)
            photo = ImageTk.PhotoImage(debug_img)
            self.debug_image_label.config(image=photo)
            self.photo_references['debug'] = photo
        
        return {"health_percent": health, "center_x": center_x, "center_y": center_y, "sample_radius": sample_radius}

    def populate_form(self, obj_pk):
        data = self.conn.cursor().execute("SELECT s.name, l.location_id, o.object_id, o.total_hp FROM objects o JOIN locations l ON o.location_fk = l.id JOIN sietches s ON l.sietch_name = s.name WHERE o.id = ?", (obj_pk,)).fetchone()
        if data:
            sietch, loc, obj, hp = data
            self.sietch_var.set(sietch)
            self.location_id_var.set(loc)
            self.object_id_var.set(obj)
            self.total_hp_var.set(str(hp) if hp is not None else "")

    def refresh_all_ui(self):
        self.update_sietch_dropdown()
        self.update_dashboard()
        self.update_sietch_overview()
        self.map_frame.load_pins()

    def update_sietch_dropdown(self):
        sietches = self.conn.cursor().execute("SELECT name FROM sietches ORDER BY name").fetchall()
        self.sietch_menu['values'] = [s[0] for s in sietches]
        self.map_frame.update_filter_options()


    def update_dashboard(self):
        for item in self.dashboard_tree.get_children(): self.dashboard_tree.delete(item)
        query = "SELECT s.name, l.location_id, o.object_id, h.health_percent, o.id FROM history h JOIN objects o ON h.object_fk=o.id JOIN locations l ON o.location_fk=l.id JOIN sietches s ON l.sietch_name=s.name WHERE h.id IN (SELECT MAX(id) FROM history GROUP BY object_fk)"
        
        items_with_latest_health = self.conn.cursor().execute(query).fetchall()

        all_items_data = []
        for item in items_with_latest_health:
            sietch, loc, obj, health, obj_pk = item
            decay_time, decay_str = self._calculate_decay_info(obj_pk)
            all_items_data.append({
                'sietch': sietch, 'loc': loc, 'obj': obj, 'health': health,
                'obj_pk': obj_pk, 'decay_time': decay_time, 'decay_str': decay_str
            })
            
        def sort_key(item):
            if item['decay_time'] is None:
                return (datetime.datetime.max, item['health'])
            return (item['decay_time'], item['health'])

        all_items_data.sort(key=sort_key)
        
        top_items = all_items_data[:4]

        for item_data in top_items:
            health_str = "Wrecked" if item_data['health'] == 0.01 else f"{item_data['health']:.2f}%"
            self.dashboard_tree.insert("", "end", values=(
                item_data['sietch'], item_data['loc'], item_data['obj'], 
                health_str, item_data['decay_str'], item_data['obj_pk']
            ))


    def update_sietch_overview(self):
        self.sietch_frames = {}
        for widget in self.overview_container.winfo_children():
            if not isinstance(widget, ttk.Label) or widget.cget("style") != "Header.TLabel": widget.destroy()
        
        sietches = self.conn.cursor().execute("SELECT name FROM sietches").fetchall()
        sietch_data = []
        for (sietch_name,) in sietches:
            count = self.conn.cursor().execute("SELECT COUNT(DISTINCT id) FROM locations WHERE sietch_name=?", (sietch_name,)).fetchone()[0]
            sietch_data.append((sietch_name, count))
        sietch_data.sort(key=lambda x: (-x[1], x[0]))

        for sietch_name, count in sietch_data:
            self.sietch_frames[sietch_name] = SietchFrame(self.overview_container, self, sietch_name, count)

    def _calculate_decay_info(self, object_pk):
        history = self.conn.cursor().execute("SELECT timestamp, health_percent FROM history WHERE object_fk=? ORDER BY timestamp DESC LIMIT 2", (object_pk,)).fetchall()
        if len(history) < 2: return (None, "N/A")
        (ts1, hp1), (ts2, hp2) = history
        if hp1 == 0.01: return (None, "Destroyed")
        time_diff_hr = (ts1 - ts2) / 3600.0
        health_diff = hp2 - hp1
        if time_diff_hr <= 0 or health_diff <= 0: return (None, "Stable")
        rate = health_diff / time_diff_hr
        if rate == 0: return (None, "Stable")
        hours_to_zero = hp1 / rate
        decay_time = datetime.datetime.fromtimestamp(ts1) + datetime.timedelta(hours=hours_to_zero)
        return (decay_time, decay_time.strftime("%Y-%m-%d %I:%M %p"))

    def on_closing(self):
        if self.conn: self.conn.close()
        self.root.destroy()

class SietchFrame(ttk.Frame):
    def __init__(self, parent, app, sietch_name, count):
        super().__init__(parent, style="TFrame", padding=5)
        self.pack(fill='x', pady=2)
        self.app = app
        self.sietch_name = sietch_name
        self.is_open = False
        self.object_frames = {}
        self.location_frames = {}

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill='x')
        header.bind("<Button-1>", self.toggle_expand)
        
        self.title_label = ttk.Label(header, text=f"► {sietch_name} ({count})", style="Subheader.TLabel", cursor="hand2")
        self.title_label.pack(side="left")
        self.title_label.bind("<Button-1>", self.toggle_expand)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="Edit", style="Yellow.TButton", command=self.edit_sietch).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Delete", style="Red.TButton", command=self.delete_sietch).pack(side='left', padx=2)
        
        self.content_frame = ttk.Frame(self)
        self.build_locations()

    def toggle_expand(self, event=None):
        self.is_open = not self.is_open
        if self.is_open:
            self.title_label.config(text=self.title_label.cget('text').replace("►", "▼"))
            self.content_frame.pack(fill='x', pady=5)
        else:
            self.title_label.config(text=self.title_label.cget('text').replace("▼", "►"))
            self.content_frame.forget()

    def build_locations(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        locations = self.app.conn.cursor().execute("SELECT id, location_id FROM locations WHERE sietch_name=? ORDER BY location_id", (self.sietch_name,)).fetchall()
        for loc_pk, loc_id_str in locations:
            loc_frame = LocationFrame(self.content_frame, self.app, self.sietch_name, loc_pk, loc_id_str)
            self.location_frames[str(loc_pk)] = loc_frame
            for obj_pk, obj_frame in loc_frame.object_frames.items():
                self.object_frames[str(obj_pk)] = obj_frame

    def edit_sietch(self):
        new_name = simpledialog.askstring("Edit Sietch", "Enter new name:", parent=self.app.root, initialvalue=self.sietch_name)
        if new_name and new_name.strip() and new_name.strip() != self.sietch_name:
            try:
                self.app.conn.cursor().execute("UPDATE sietches SET name=? WHERE name=?", (new_name.strip(), self.sietch_name))
                self.app.conn.commit()
                self.app.refresh_all_ui()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "A sietch with that name already exists.")
    
    def delete_sietch(self):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete Sietch '{self.sietch_name}' and ALL its contents?"):
            self.app.conn.cursor().execute("DELETE FROM sietches WHERE name=?", (self.sietch_name,))
            self.app.conn.commit()
            self.app.refresh_all_ui()

class LocationFrame(ttk.Frame):
    def __init__(self, parent, app, sietch_name, loc_pk, loc_id):
        super().__init__(parent, style="TFrame", padding=(15, 5, 5, 5))
        self.pack(fill='x')
        self.app = app
        self.sietch_name = sietch_name
        self.loc_pk = loc_pk
        self.loc_id = loc_id
        self.object_frames = {}
        
        header = ttk.Frame(self)
        header.pack(fill='x')
        ttk.Label(header, text=loc_id).pack(side='left')
        ttk.Button(header, text="Delete Loc", style="Red.TButton", command=self.delete_location).pack(side='right')

        objects = self.app.conn.cursor().execute("SELECT id, object_id FROM objects WHERE location_fk=? ORDER BY object_id", (self.loc_pk,)).fetchall()
        for obj_pk, obj_id_str in objects:
            self.object_frames[str(obj_pk)] = ObjectFrame(self, self.app, obj_pk, obj_id_str)
            
    def delete_location(self):
        if messagebox.askyesno("Confirm Delete", f"Delete location '{self.loc_id}' and ALL its objects?"):
            self.app.conn.cursor().execute("DELETE FROM locations WHERE id=?", (self.loc_pk,))
            self.app.conn.commit()
            self.app.refresh_all_ui()

class ObjectFrame(ttk.Frame):
    def __init__(self, parent, app, obj_pk, obj_id):
        super().__init__(parent, style="TFrame", padding=(20, 2, 2, 2))
        self.pack(fill='x')
        self.app = app
        self.obj_pk = obj_pk
        self.obj_id = obj_id
        self.detail_frame = None

        header = ttk.Frame(self)
        header.pack(fill='x')
        header.bind("<Button-1>", self.toggle_details)
        
        cursor = self.app.conn.cursor()
        latest_history = cursor.execute("SELECT health_percent, timestamp FROM history WHERE object_fk=? ORDER BY timestamp DESC LIMIT 1", (self.obj_pk,)).fetchone()
        
        health_str = "N/A"
        if latest_history:
            health_val = latest_history[0]
            ts = datetime.datetime.fromtimestamp(latest_history[1]).strftime("%Y-%m-%d %I:%M %p")
            health_str = f"Wrecked ({ts})" if health_val == 0.01 else f"{health_val:.2f}% ({ts})"

        self.label = ttk.Label(header, text=f"> {self.obj_id} - {health_str}", cursor="hand2")
        self.label.pack(side='left')
        self.label.bind("<Button-1>", self.toggle_details)

        ttk.Button(header, text="Delete Obj", style="Red.TButton", command=self.delete_object, width=10).pack(side='right')

    def toggle_details(self, event=None):
        self.app.populate_form(self.obj_pk)
        if self.app.active_detail_frame and self.app.active_detail_frame != self.detail_frame:
            self.app.active_detail_frame.destroy()
        
        if self.detail_frame and self.detail_frame.winfo_exists():
            self.detail_frame.destroy()
            self.app.active_detail_frame = None
        else:
            self.detail_frame = DetailFrame(self, self.app, self.obj_pk)
            self.app.active_detail_frame = self.detail_frame

    def delete_object(self):
         if messagebox.askyesno("Confirm Delete", f"Delete object '{self.obj_id}'?"):
            self.app.conn.cursor().execute("DELETE FROM objects WHERE id=?", (self.obj_pk,))
            self.app.conn.commit()
            self.app.refresh_all_ui()

class DetailFrame(ttk.Frame):
    def __init__(self, parent, app, obj_pk):
        super().__init__(parent, style="TFrame", padding=10, borderwidth=1, relief="solid")
        self.pack(fill='x', expand=True, pady=5)
        self.app = app
        self.obj_pk = obj_pk
        self.photo_refs = {}
        self.create_detail_widgets()

    def create_detail_widgets(self):
        cursor = self.app.conn.cursor()
        data = cursor.execute("SELECT l.id, o.object_screenshot_path, o.total_hp FROM objects o JOIN locations l ON o.location_fk = l.id WHERE o.id = ?", (self.obj_pk,)).fetchone()
        self.loc_pk, obj_path, total_hp = data

        ss_frame = ttk.Frame(self); ss_frame.pack(fill='x')
        self.create_screenshot_uploader(ss_frame, "Map", self.loc_pk).pack(side='left', expand=True, padx=5)
        self.create_screenshot_uploader(ss_frame, "Object", obj_path, self.update_obj_screenshot).pack(side='right', expand=True, padx=5)

        info_frame = ttk.Frame(self); info_frame.pack(fill='x', pady=10)
        latest_health = cursor.execute("SELECT health_percent FROM history WHERE object_fk=? ORDER BY timestamp DESC LIMIT 1", (self.obj_pk,)).fetchone()
        health_str = f"{latest_health[0]:.2f}%" if latest_health else "N/A"
        if latest_health and latest_health[0] == 0.01: health_str = "Wrecked"
        ttk.Label(info_frame, text=f"Current Health: {health_str}").grid(row=0, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Total HP: {total_hp if total_hp else 'N/A'}").grid(row=0, column=1, sticky='w', padx=20)
        
        _, decay_str = self.app._calculate_decay_info(self.obj_pk)
        ttk.Label(info_frame, text=f"Decay Info: {decay_str}").grid(row=1, column=0, columnspan=2, sticky='w')
        
        history = cursor.execute("SELECT timestamp, health_percent FROM history WHERE object_fk=? ORDER BY timestamp", (self.obj_pk,)).fetchall()
        if len(history) > 1:
            fig = Figure(figsize=(5, 2.5), dpi=100, facecolor="#1f2937")
            ax = fig.add_subplot(111); ax.plot([datetime.datetime.fromtimestamp(ts) for ts, hp in history], [hp for ts, hp in history], color="#67e8f9")
            ax.set_facecolor("#374151"); ax.tick_params(axis='x', colors='white', rotation=30); ax.tick_params(axis='y', colors='white')
            ax.spines['top'].set_color('none'); ax.spines['right'].set_color('none'); ax.spines['bottom'].set_color('white'); ax.spines['left'].set_color('white')
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self); canvas.draw(); canvas.get_tk_widget().pack(fill='x', pady=5)

        history_frame = ttk.Frame(self); history_frame.pack(fill='x', pady=10)
        ttk.Label(history_frame, text="Health History", style="Subheader.TLabel").pack(anchor='w')
        
        history_scroll = ScrollableFrame(history_frame); history_scroll.pack(fill='x', expand=True)

        for hist_id, ts, hp, path in cursor.execute("SELECT id, timestamp, health_percent, screenshot_path FROM history WHERE object_fk=? ORDER BY timestamp DESC", (self.obj_pk,)):
            entry_frame = ttk.Frame(history_scroll.scrollable_frame, padding=5); entry_frame.pack(fill='x')
            img = self.load_image(path, (50, 50)); img_label = ttk.Label(entry_frame, image=img); img_label.pack(side='left')
            self.photo_refs[f"hist_{hist_id}"] = img
            info_text = f"{hp:.2f}% on {datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %I:%M %p')}"
            ttk.Label(entry_frame, text=info_text).pack(side='left', padx=10)
            
            btn_container = ttk.Frame(entry_frame); btn_container.pack(side='right')
            ttk.Button(btn_container, text="Adjust", style="Yellow.TButton", command=lambda p=path, h_id=hist_id: AdjustmentWindow(self.app.root, self.app, h_id, p)).pack(side='left', padx=2)
            ttk.Button(btn_container, text="Remove", style="Red.TButton", command=lambda h_id=hist_id: self.delete_history_entry(h_id)).pack(side='left', padx=2)


    def delete_history_entry(self, history_id):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to remove this history entry?"):
            self.app.conn.cursor().execute("DELETE FROM history WHERE id=?", (history_id,))
            self.app.conn.commit()
            self.app.refresh_all_ui()

    def create_screenshot_uploader(self, parent, title, path_or_pk, command=None):
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=title).pack()

        img = None
        if title == "Map":
            map_path_row = self.app.conn.cursor().execute("SELECT value FROM config WHERE key='main_map_path'").fetchone()
            loc_data = self.app.conn.cursor().execute("SELECT pin_x, pin_y FROM locations WHERE id=?",(self.loc_pk,)).fetchone()
            if map_path_row and os.path.exists(map_path_row[0]) and loc_data and loc_data[0] is not None:
                try:
                    map_img = Image.open(map_path_row[0])
                    px, py = loc_data
                    crop_radius = 400 
                    box = (px - crop_radius, py - crop_radius, px + crop_radius, py + crop_radius)
                    mini_map_crop = map_img.crop(box)
                    
                    draw = ImageDraw.Draw(mini_map_crop)
                    pin_center_x = mini_map_crop.width / 2
                    pin_center_y = mini_map_crop.height / 2
                    pin_radius = 10
                    draw.ellipse((pin_center_x - pin_radius, pin_center_y - pin_radius, pin_center_x + pin_radius, pin_center_y + pin_radius), fill="red", outline="white")
                    
                    mini_map_crop.thumbnail((200, 200))
                    img = ImageTk.PhotoImage(mini_map_crop)
                except Exception:
                    img = self.load_image(None, (200,200), placeholder=True)
            else:
                 img = self.load_image(None, (200,200), placeholder=True)
        else: # Object
            img = self.load_image(path_or_pk, (200, 200), placeholder=True)

        label = ttk.Label(frame, image=img)
        label.pack()
        self.photo_refs[f"detail_{self.obj_pk}_{title}"] = img
        if title == "Object":
            ttk.Button(frame, text="Upload...", command=command).pack(pady=5)
        return frame

    def load_image(self, path, size, placeholder=False):
        try:
            if not path or not os.path.exists(path):
                if placeholder: return ImageTk.PhotoImage(Image.new('RGB', size, color='#374151'))
                return None
            img = Image.open(path); img.thumbnail(size); return ImageTk.PhotoImage(img)
        except Exception: return None
        
    def update_map_screenshot(self):
        messagebox.showinfo("Info", "To change the map, please use the File -> Set Main Map Image... menu option.")
    
    def update_obj_screenshot(self):
        path = filedialog.askopenfilename()
        if path:
            new_path = self.copy_to_image_folder(path, "object")
            self.app.conn.cursor().execute("UPDATE objects SET object_screenshot_path=? WHERE id=?", (new_path, self.obj_pk))
            self.app.conn.commit(); self.app.refresh_all_ui()

    def copy_to_image_folder(self, src_path, prefix):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}{os.path.splitext(src_path)[1]}"
        dest_path = os.path.join(self.app.image_folder, filename)
        shutil.copy(src_path, dest_path)
        return dest_path

class AdjustmentWindow(tk.Toplevel):
    def __init__(self, parent, app, history_pk, image_path):
        super().__init__(parent)
        self.app = app
        self.history_pk = history_pk
        self.image_path = image_path
        
        self.title("Manual Health Adjustment")
        self.configure(bg="#1f2937")

        self.transient(parent)
        self.grab_set()

        try:
            self.original_img = Image.open(self.image_path)
            self.analysis_data = self.app.analyze_image(self.image_path)
            
            self.display_scale = 600 / self.original_img.width
            display_height = int(self.original_img.height * self.display_scale)
            self.display_img = self.original_img.resize((600, display_height))

            self.canvas = tk.Canvas(self, width=600, height=display_height, cursor="crosshair")
            self.canvas.pack(pady=10)
            self.photo_img = ImageTk.PhotoImage(self.display_img)
            self.canvas.create_image(0,0, anchor='nw', image=self.photo_img)

            self.new_health_var = tk.DoubleVar()
            current_health = self.app.conn.cursor().execute("SELECT health_percent FROM history WHERE id=?", (self.history_pk,)).fetchone()[0]
            self.new_health_var.set(current_health)
            
            self.health_label = ttk.Label(self, text=f"New Health: {current_health:.2f}%", style="Header.TLabel")
            self.health_label.pack(pady=10)

            self.draw_overlay()

            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<Button-1>", self.on_drag)

            btn_frame = ttk.Frame(self)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Save", command=self.save).pack(side='left', padx=10)
            ttk.Button(btn_frame, text="Cancel", command=self.destroy, style="Red.TButton").pack(side='left', padx=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open adjustment window: {e}", parent=self)
            self.destroy()

    def draw_overlay(self):
        self.canvas.delete("overlay")
        percent = self.new_health_var.get()
        
        cx = self.analysis_data['center_x'] * self.display_scale
        cy = self.analysis_data['center_y'] * self.display_scale
        r = self.analysis_data['sample_radius'] * self.display_scale

        self.canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill="yellow", tags="overlay", outline="")
        self.canvas.create_line(cx, cy, cx, cy-r, fill="lime", width=2, tags="overlay")
        
        angle = percent * 3.6
        rad = math.radians(angle)
        end_x, end_y = cx + r * math.sin(rad), cy - r * math.cos(rad)
        self.canvas.create_line(cx, cy, end_x, end_y, fill="red", width=2, tags="overlay")

    def on_drag(self, event):
        cx = self.analysis_data['center_x'] * self.display_scale
        cy = self.analysis_data['center_y'] * self.display_scale

        angle_rad = math.atan2(event.x - cx, -(event.y - cy))
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0: angle_deg += 360
        
        new_percent = (angle_deg / 360) * 100
        self.new_health_var.set(new_percent)
        self.health_label.config(text=f"New Health: {new_percent:.2f}%")
        self.draw_overlay()

    def save(self):
        new_health = self.new_health_var.get()
        self.app.conn.cursor().execute("UPDATE history SET health_percent=? WHERE id=?", (new_health, self.history_pk))
        self.app.conn.commit()
        self.app.refresh_all_ui()
        self.destroy()

class DatePicker(tk.Toplevel):
    def __init__(self, parent, callback, initial_date):
        super().__init__(parent)
        self.callback = callback
        self.title("Select Date & Time")
        self.transient(parent)
        self.grab_set()
        
        self.cal = Calendar(self, selectmode='day', year=initial_date.year, month=initial_date.month, day=initial_date.day)
        self.cal.pack(pady=10)

        time_frame = ttk.Frame(self)
        time_frame.pack(pady=10)
        
        self.hour_spin = ttk.Spinbox(time_frame, from_=1, to=12, width=3, wrap=True)
        self.minute_spin = ttk.Spinbox(time_frame, from_=0, to=59, width=3, format="%02.0f", wrap=True)
        self.ampm_var = tk.StringVar(value=initial_date.strftime("%p"))
        self.ampm_menu = ttk.Combobox(time_frame, textvariable=self.ampm_var, values=["AM", "PM"], width=3, state="readonly")
        
        self.hour_spin.set(initial_date.strftime("%I"))
        self.minute_spin.set(initial_date.strftime("%M"))
        
        self.hour_spin.pack(side='left', padx=5)
        ttk.Label(time_frame, text=":").pack(side='left')
        self.minute_spin.pack(side='left', padx=5)
        self.ampm_menu.pack(side='left', padx=5)

        ttk.Button(self, text="Select", command=self.on_select).pack(pady=10)

    def on_select(self):
        date_str = self.cal.get_date() # "month/day/yy"
        time_str = f"{int(self.hour_spin.get()):02}:{int(self.minute_spin.get()):02} {self.ampm_var.get()}"
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%m/%d/%y %I:%M %p")
        self.callback(dt.strftime("%Y-%m-%d %I:%M %p"))
        self.destroy()

class MapFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app
        self.pins = {}
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.original_map_image = None
        self.display_map_image = None

        control_frame = ttk.Frame(self)
        control_frame.pack(fill='x', pady=5)
        ttk.Label(control_frame, text="Filter by Sietch:").pack(side='left', padx=5)
        self.sietch_filter_var = tk.StringVar(value="All")
        self.sietch_filter_menu = ttk.Combobox(control_frame, textvariable=self.sietch_filter_var, state="readonly")
        self.sietch_filter_menu.pack(side='left', padx=5)
        self.sietch_filter_menu.bind("<<ComboboxSelected>>", self.filter_pins)

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill='x')
        
        self.canvas.bind("<ButtonPress-3>", self.show_context_menu)
        self.canvas.bind("<ButtonPress-1>", self.on_pin_press)
        self.canvas.bind("<B1-Motion>", self.on_pin_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_pin_release)
        
        self.load_map()

    def load_map(self):
        map_path_row = self.app.conn.cursor().execute("SELECT value FROM config WHERE key='main_map_path'").fetchone()
        
        if hasattr(self, 'upload_btn') and self.upload_btn.winfo_exists(): self.upload_btn.destroy()

        if map_path_row and os.path.exists(map_path_row[0]):
            self.map_path = map_path_row[0]
            self.original_map_image = Image.open(self.map_path)
            self.display_map()
            self.load_pins()
        else:
            self.upload_btn = ttk.Button(self, text="Click here to set the main map image", command=self.app.set_main_map_image)
            self.upload_btn.pack(pady=50, padx=50, expand=True)

    def display_map(self):
        container_width = self.app.right_content_frame.winfo_width()
        if container_width < 10: container_width = 800
        
        w, h = self.original_map_image.size
        self.display_scale = container_width / w
        new_height = int(h * self.display_scale)
        
        self.display_map_image = self.original_map_image.resize((container_width, new_height))
        self.photo_map = ImageTk.PhotoImage(self.display_map_image)
        self.canvas.config(width=container_width, height=new_height)
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo_map)

    def load_pins(self):
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists() or not hasattr(self, 'display_scale'): return
        self.canvas.delete("pin")
        self.pins = {}
        locations = self.app.conn.cursor().execute("SELECT id, location_id, pin_x, pin_y, sietch_name FROM locations WHERE pin_x IS NOT NULL AND pin_y IS NOT NULL").fetchall()
        
        for loc_pk, loc_id, pin_x, pin_y, sietch_name in locations:
            scaled_x, scaled_y = pin_x * self.display_scale, pin_y * self.display_scale
            pin_id = self.canvas.create_oval(scaled_x-5, scaled_y-5, scaled_x+5, scaled_y+5, fill="red", outline="white", tags=("pin", f"loc_{loc_pk}"))
            text_id = self.canvas.create_text(scaled_x, scaled_y - 10, text=loc_id, fill="white", tags=("pin", f"loc_{loc_pk}"))
            self.pins[pin_id] = {'loc_pk': loc_pk, 'loc_id': loc_id, 'sietch': sietch_name, 'text_id': text_id}
            self.pins[text_id] = self.pins[pin_id]
        self.filter_pins()

    def filter_pins(self, event=None):
        selected_sietch = self.sietch_filter_var.get()
        for pin_id, pin_data in self.pins.items():
            state = "normal" if selected_sietch == "All" or pin_data.get('sietch') == selected_sietch else "hidden"
            self.canvas.itemconfig(pin_id, state=state)
    
    def update_filter_options(self):
        sietches = ["All"] + [s[0] for s in self.app.conn.cursor().execute("SELECT name FROM sietches").fetchall()]
        self.sietch_filter_menu['values'] = sietches
        
    def show_context_menu(self, event):
        sietch_filter = self.sietch_filter_var.get()
        context_menu = tk.Menu(self.canvas, tearoff=0)
        
        clicked_items = self.canvas.find_overlapping(event.x-1, event.y-1, event.x+1, event.y+1)
        pin_items = [i for i in clicked_items if "pin" in self.canvas.gettags(i)]
        
        if pin_items:
            pin_data = self.pins[pin_items[0]]
            loc_pk = pin_data['loc_pk']
            context_menu.add_command(label="View in Overview", command=lambda: self.app.focus_on_location(loc_pk))
            context_menu.add_command(label="Rename Location", command=lambda: self.rename_pin(loc_pk))
            context_menu.add_command(label="Delete Location", command=lambda: self.delete_pin(loc_pk))
        elif sietch_filter != "All":
            unpinned_locs = self.app.conn.cursor().execute("SELECT id, location_id FROM locations WHERE sietch_name=? AND (pin_x IS NULL OR pin_y IS NULL)", (sietch_filter,)).fetchall()
            if unpinned_locs:
                place_menu = tk.Menu(context_menu, tearoff=0)
                for loc_pk, loc_id in unpinned_locs:
                    place_menu.add_command(label=loc_id, command=lambda pk=loc_pk, x=event.x, y=event.y: self.place_existing_pin(pk, x, y))
                context_menu.add_cascade(label="Place Existing Location", menu=place_menu)
            context_menu.add_command(label="Add New Pin Here", command=lambda: self.add_pin(event.x, event.y, sietch_filter))

        if context_menu.index('end') is not None:
            context_menu.post(event.x_root, event.y_root)
        
    def place_existing_pin(self, loc_pk, x, y):
        pin_x, pin_y = int(x / self.display_scale), int(y / self.display_scale)
        self.app.conn.cursor().execute("UPDATE locations SET pin_x=?, pin_y=? WHERE id=?",(pin_x, pin_y, loc_pk))
        self.app.conn.commit()
        self.app.refresh_all_ui()

    def add_pin(self, x, y, sietch_name):
        loc_id = simpledialog.askstring("New Location", "Enter Location ID:", parent=self.app.root)
        if not loc_id or not loc_id.strip(): return
        
        pin_x, pin_y = int(x / self.display_scale), int(y / self.display_scale)
        
        try:
            cursor = self.app.conn.cursor()
            cursor.execute("INSERT INTO locations (sietch_name, location_id, pin_x, pin_y) VALUES (?, ?, ?, ?)", (sietch_name, loc_id.strip(), pin_x, pin_y))
            self.app.conn.commit()
            self.app.refresh_all_ui()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "A location with this ID already exists in this Sietch.")
            
    def rename_pin(self, loc_pk):
        current_name = self.app.conn.cursor().execute("SELECT location_id FROM locations WHERE id=?",(loc_pk,)).fetchone()[0]
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=current_name)
        if new_name and new_name.strip() and new_name.strip() != current_name:
            try:
                self.app.conn.cursor().execute("UPDATE locations SET location_id=? WHERE id=?", (new_name.strip(), loc_pk))
                self.app.conn.commit()
                self.app.refresh_all_ui()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Name already exists.")

    def delete_pin(self, loc_pk):
        if messagebox.askyesno("Confirm", "Delete this location pin and all its objects?"):
            self.app.conn.cursor().execute("DELETE FROM locations WHERE id=?",(loc_pk,))
            self.app.conn.commit()
            self.app.refresh_all_ui()

    def on_pin_press(self, event):
        items = self.canvas.find_overlapping(event.x-1, event.y-1, event.x+1, event.y+1)
        pin_items = [i for i in items if "pin" in self.canvas.gettags(i)]
        if pin_items:
            self.drag_data["item"] = pin_items[0]
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_pin_drag(self, event):
        if self.drag_data["item"]:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            
            pin_data = self.pins[self.drag_data["item"]]
            oval_id = next(k for k,v in self.pins.items() if v==pin_data and self.canvas.type(k) == 'oval')
            
            self.canvas.move(oval_id, dx, dy)
            self.canvas.move(pin_data['text_id'], dx, dy)
            
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            
    def on_pin_release(self, event):
        if self.drag_data["item"]:
            pin_data = self.pins[self.drag_data["item"]]
            loc_pk = pin_data['loc_pk']
            
            oval_id = next(k for k,v in self.pins.items() if v==pin_data and self.canvas.type(k) == 'oval')
            new_coords = self.canvas.coords(oval_id)
            new_canvas_x = (new_coords[0] + new_coords[2]) / 2
            new_canvas_y = (new_coords[1] + new_coords[3]) / 2
            
            new_pin_x = int(new_canvas_x / self.display_scale)
            new_pin_y = int(new_canvas_y / self.display_scale)
            
            self.app.conn.cursor().execute("UPDATE locations SET pin_x=?, pin_y=? WHERE id=?", (new_pin_x, new_pin_y, loc_pk))
            self.app.conn.commit()
        
        self.drag_data["item"] = None

if __name__ == "__main__":
    root = tk.Tk()
    app = VultureTrackerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

