import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import os
import queue
import shutil
from datetime import datetime, timedelta
import traceback
import threading
import cv2
import numpy as np
from mss import mss
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

from database import DatabaseManager
from gui_components import ScrollableFrame, MapFrame, SietchManagerWindow
from analyzer import HealthAnalyzer

class VultureTrackerApp:
    AVG_STORM_CYCLE_HOURS = 0.875
    MIN_STORM_INTERVAL_H = 0.75
    MAX_STORM_INTERVAL_H = 1.0

    def __init__(self, root):
        self.root = root
        self.root.title("Vulture Tracker v3.3")
        self.root.configure(bg="#111827")
        self.root.state('zoomed')

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.image_folder = os.path.join(script_dir, "vulture_tracker_images_v3")
        os.makedirs(self.image_folder, exist_ok=True)
        db_path = os.path.join(script_dir, "vulture_tracker_v3.db")
        self.db = DatabaseManager(db_path)

        self.photo_references = {}
        self.last_capture_data = None
        self.capture_queue = queue.Queue()
        self.graph_canvas = None

        self.setup_styles()
        self.create_widgets()
        self.root.after(100, self.refresh_all_ui)

        self.root.bind_all("<Control-Shift-h>", self._trigger_capture)

        self.check_capture_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("Vulture Tracker UI is running. Press Ctrl+Shift+H in-game to capture.")

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        BG_COLOR, FG_COLOR, BORDER_COLOR, SELECT_BG = "#111827", "#E5E7EB", "#374151", "#4B5563"

        style.configure('.', background=BG_COLOR, foreground=FG_COLOR, fieldbackground=BG_COLOR, borderwidth=1)
        style.map('.', foreground=[('disabled', '#6B7280')])

        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR, padding=5, font=('Arial', 10))
        style.configure('TButton', background=BORDER_COLOR, foreground=FG_COLOR, borderwidth=0, focusthickness=0)
        style.map('TButton', background=[('active', SELECT_BG)])

        self.root.option_add('*TCombobox*Listbox.background', BORDER_COLOR)
        self.root.option_add('*TCombobox*Listbox.foreground', FG_COLOR)
        self.root.option_add('*TCombobox*Listbox.selectBackground', SELECT_BG)
        self.root.option_add('*TCombobox*Listbox.selectForeground', FG_COLOR)
        style.configure('TCombobox',
                        selectbackground=BORDER_COLOR,
                        fieldbackground=BORDER_COLOR,
                        background=BORDER_COLOR,
                        arrowcolor=FG_COLOR,
                        foreground=FG_COLOR)
        style.map('TCombobox', fieldbackground=[('readonly', BORDER_COLOR)], selectbackground=[('readonly', BORDER_COLOR)], selectforeground=[('readonly', FG_COLOR)])

        style.configure('TEntry', fieldbackground=BORDER_COLOR, foreground=FG_COLOR, insertcolor=FG_COLOR, borderwidth=1, relief='flat')

        style.configure('Treeview',
                        rowheight=25,
                        fieldbackground=BG_COLOR,
                        background=BG_COLOR,
                        foreground=FG_COLOR,
                        borderwidth=0,
                        relief='flat')
        style.map('Treeview', background=[('selected', SELECT_BG)], foreground=[('selected', FG_COLOR)])
        style.configure("Treeview.Heading", background=BORDER_COLOR, foreground=FG_COLOR, relief="flat", font=('Arial', 10, 'bold'))
        style.map("Treeview.Heading", background=[('active', SELECT_BG)])

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Main Map Image...", command=self.set_main_map_image)
        file_menu.add_command(label="Manage Sietches...", command=self.open_sietch_manager)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # --- Main Window Grid Configuration ---
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # --- Left Column ---
        left_column_frame = ttk.Frame(self.root)
        left_column_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        # Configure rows later in specific steps

        # --- Right Column ---
        right_column_frame = ttk.Frame(self.root)
        right_column_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        # Configure rows later in specific steps

        # --- Re-parent existing frames ---
        # Left side components
        form_frame = ttk.Frame(left_column_frame, padding=10)
        form_frame.pack(side='bottom', fill='x', expand=False, pady=(10,0))
        form_frame.columnconfigure(1, weight=1)

        self.map_frame = MapFrame(left_column_frame, self)
        self.map_frame.pack(side='top', fill='both', expand=True)

        ttk.Label(form_frame, text="Captured Data Point", font=('Arial', 14, 'bold')).grid(row=0, columnspan=2, pady=5, sticky='w')
        self.sietch_var, self.location_var, self.object_id_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(form_frame, text="Sietch:").grid(row=1, column=0, sticky='w', pady=2, padx=5)
        self.sietch_menu = ttk.Combobox(form_frame, textvariable=self.sietch_var, state="readonly", width=15)
        self.sietch_menu.grid(row=1, column=1, sticky='ew', padx=5)
        self.sietch_menu.bind("<<ComboboxSelected>>", self.on_sietch_select)

        ttk.Label(form_frame, text="Location ID:").grid(row=2, column=0, sticky='w', pady=2, padx=5)
        self.location_menu = ttk.Combobox(form_frame, textvariable=self.location_var, width=15, state="readonly")
        self.location_menu.grid(row=2, column=1, sticky='ew', padx=5)

        ttk.Label(form_frame, text="Object ID:").grid(row=3, column=0, sticky='w', pady=2, padx=5)
        ttk.Entry(form_frame, textvariable=self.object_id_var, width=15).grid(row=3, column=1, sticky='ew', padx=5)

        self.capture_preview_label = ttk.Label(form_frame, text="Press Ctrl+Shift+H in-game...")
        self.capture_preview_label.grid(row=4, columnspan=2, pady=10)

        self.save_button = ttk.Button(form_frame, text="Save Captured Data", command=self.save_captured_data, state="disabled")
        self.save_button.grid(row=5, columnspan=2, sticky='ew', pady=5, padx=5)

        # --- Right Column Grid Configuration ---
        right_column_frame.grid_rowconfigure(0, weight=1) # Top half for lists
        right_column_frame.grid_rowconfigure(1, weight=1) # Bottom half for graph/history
        right_column_frame.grid_columnconfigure(0, weight=1)

        # --- Top Right Container (for lists) ---
        top_right_frame = ttk.Frame(right_column_frame)
        top_right_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=(5,0))
        top_right_frame.grid_rowconfigure(1, weight=1) # Row for Priority Tree
        top_right_frame.grid_rowconfigure(3, weight=2) # Row for Main Object Tree
        top_right_frame.grid_columnconfigure(0, weight=1)

        # --- Bottom Right Container (for graph/history) ---
        self.graph_frame = ttk.Frame(right_column_frame)
        self.graph_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.graph_frame, text="Select an object from the list to view its history.").pack(expand=True)

        # --- Populate Top Right Container ---
        # Priority Watch List
        ttk.Label(top_right_frame, text="Priority Watch List", font=('Arial', 14, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        priority_tree_frame = ttk.Frame(top_right_frame)
        priority_tree_frame.grid(row=1, column=0, sticky='nsew', padx=5)
        priority_tree_frame.column_configure(0, weight=1)
        self.priority_tree = ttk.Treeview(priority_tree_frame, columns=("Time to Failure", "Object"), show="headings", height=5)
        self.priority_tree.heading("Time to Failure", text="Time to Failure"); self.priority_tree.heading("Object", text="Object")
        self.priority_tree.column("Time to Failure", width=120, anchor='w'); self.priority_tree.column("Object", width=280, anchor='w')
        self.priority_tree.grid(row=0, column=0, sticky='nsew')
        priority_scroll = ttk.Scrollbar(priority_tree_frame, orient="vertical", command=self.priority_tree.yview)
        priority_scroll.grid(row=0, column=1, sticky='ns')
        self.priority_tree.configure(yscrollcommand=priority_scroll.set)

        # Separator
        ttk.Separator(top_right_frame, orient='horizontal').grid(row=2, column=0, sticky='ew', pady=10, padx=5)

        # Main Object Tree
        ttk.Label(top_right_frame, text="All Tracked Objects", font=('Arial', 14, 'bold')).grid(row=4, column=0, sticky='w', padx=5)
        tree_frame = ttk.Frame(top_right_frame)
        tree_frame.grid(row=5, column=0, sticky='nsew', padx=5, pady=5)
        tree_frame.column_configure(0, weight=1)
        tree_frame.row_configure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("Sietch", "Location", "Object"), show="headings")
        self.tree.heading("Sietch", text="Sietch"); self.tree.heading("Location", text="Location"); self.tree.heading("Object", text="Object")
        self.tree.column("Sietch", width=100, anchor='w'); self.tree.column("Location", width=150, anchor='w'); self.tree.column("Object", width=150, anchor='w')
        self.tree.grid(row=0, column=0, sticky='nsew')
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_object_select)
        self.tree.bind("<Button-3>", self._show_object_context_menu)

    def _trigger_capture(self, event=None):
        print("Capture hotkey triggered...")
        try:
            with mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                full_image_cv = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                analysis_result = HealthAnalyzer.analyze(full_image_cv)
                if analysis_result:
                    self.capture_queue.put(analysis_result)
        except Exception as e:
            self.log_error(source="Screenshot Capture", error_data=traceback.format_exc())

    def open_sietch_manager(self):
        SietchManagerWindow(self.root, self)

    def check_capture_queue(self):
        try:
            capture = self.capture_queue.get_nowait()
            if "error" in capture: self.log_error(source="Hotkey Listener", error_data=capture["error"])
            else: self.last_capture_data = capture; self.populate_form_with_capture()
        except queue.Empty: pass
        finally: self.root.after(100, self.check_capture_queue)

    def populate_form_with_capture(self):
        data = self.last_capture_data
        health = data["health_percent"]
        ts = data["timestamp"].strftime("%Y-%m-%d %I:%M:%S %p")
        roi_pil = Image.fromarray(cv2.cvtColor(data["center_crop"], cv2.COLOR_BGR2RGB)); roi_pil.thumbnail((100, 100))
        photo = ImageTk.PhotoImage(roi_pil); self.photo_references['capture'] = photo
        self.capture_preview_label.config(image=photo, text=f"Health: {health:.2f}%\n{ts}", compound='top')
        self.save_button.config(state="normal")

        sietches = self.db.get_sietches()
        if not self.sietch_var.get() and sietches:
            self.sietch_var.set(sietches[0])

    def save_captured_data(self):
        data_to_save = {
            "sietch": self.sietch_var.get(),
            "location_id": self.location_var.get(),
            "object_id": self.object_id_var.get().strip(),
            "health": self.last_capture_data["health_percent"],
            "timestamp": self.last_capture_data["timestamp"],
            "roi_image": self.last_capture_data["center_crop"]
        }
        if not all([data_to_save["sietch"], data_to_save["location_id"], data_to_save["object_id"]]):
            messagebox.showerror("Error", "Sietch, Location, and Object ID are required.")
            return
        self.db.add_location(data_to_save["sietch"], data_to_save["location_id"])
        success, message = self.db.save_data_point(data_to_save, self.image_folder)
        if success:
            messagebox.showinfo("Success", "Data point saved successfully!")
            self.last_capture_data = None
            self.save_button.config(state="disabled")
            self.object_id_var.set("")
            self.refresh_all_ui()
        else:
            messagebox.showerror("Database Error", message)

    def on_sietch_select(self, event=None):
        sietch = self.sietch_var.get()
        if sietch:
            locations = self.db.get_locations_for_sietch(sietch)
            self.location_menu['values'] = locations
            if locations:
                self.location_var.set(locations[0])
            else:
                self.location_var.set("")
        else:
            self.location_menu['values'] = []
            self.location_var.set("")

    def refresh_all_ui(self):
        self.refresh_sietch_list()
        self.on_sietch_select() # Update location list based on current sietch
        self.refresh_object_tree()
        self.refresh_priority_watch_list()
        if hasattr(self, 'map_frame'): self.map_frame.load_pins()

    def refresh_sietch_list(self):
        sietches = self.db.get_sietches()
        self.sietch_menu['values'] = sietches
        if sietches and not self.sietch_var.get():
            self.sietch_var.set(sietches[0])
        if hasattr(self, 'map_frame'): self.map_frame.update_filter_options()

    def refresh_object_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        all_objects = self.db.get_all_objects_with_sietch_and_location()

        # Group objects by location to build the hierarchy
        locations = {}
        for sietch, location, obj_id in all_objects:
            key = (sietch, location)
            if key not in locations:
                locations[key] = []
            locations[key].append(obj_id)

        for (sietch, location), objects in sorted(locations.items()):
            # Insert location as a parent node, initially closed
            loc_node_id = self.tree.insert("", "end", values=(sietch, location, ""), open=False)

            for obj_id in sorted(objects):
                # Insert objects as children of the location node
                self.tree.insert(loc_node_id, "end", values=("", "", obj_id))

    def on_object_select(self, event):
        tree = self.tree
        selected_item = tree.focus()

        if not selected_item:
            return

        parent_id = tree.parent(selected_item)

        # If the item has no parent, it's a Location node.
        if not parent_id:
            # Accordion logic for locations: close all other locations
            for sibling in tree.get_children(""):
                if sibling != selected_item:
                    tree.item(sibling, open=False)

            # Toggle the selected location's state
            is_open = tree.item(selected_item, "open")
            tree.item(selected_item, open=not is_open)

            # Clear the graph pane since a location is selected, not an object
            if self.graph_canvas:
                self.graph_canvas.get_tk_widget().destroy()
                plt.close('all')
            for widget in self.graph_frame.winfo_children():
                widget.destroy()
            ttk.Label(self.graph_frame, text="Select an object from the list to view its history.").pack()

        # If the item has a parent, it's an Object node.
        else:
            sietch, location, _ = tree.item(parent_id, 'values')
            _, _, obj_id = tree.item(selected_item, 'values')
            if obj_id:
                self.display_object_history(sietch, location, obj_id)

    def _show_object_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        self.tree.selection_set(item_id)

        is_parent = not self.tree.parent(item_id)

        menu = tk.Menu(self.root, tearoff=0)

        if is_parent:
            menu.add_command(label="Rename Location", command=self._rename_location)
            menu.add_command(label="Delete Location", command=self._delete_location)
        else:
            menu.add_command(label="Rename Object", command=self._rename_object)
            menu.add_command(label="Delete Object", command=self._delete_object)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _rename_location(self):
        selected_item = self.tree.focus()
        if not selected_item or self.tree.parent(selected_item): return

        sietch, old_loc_id, _ = self.tree.item(selected_item)['values']
        loc_pk = self.db.get_location_pk_by_name(sietch, old_loc_id)
        if not loc_pk: return

        new_loc_id = simpledialog.askstring("Rename Location", f"Enter new ID for location '{old_loc_id}':", parent=self.root)
        if new_loc_id and new_loc_id.strip() and new_loc_id.strip() != old_loc_id:
            success, msg = self.db.rename_location(loc_pk, new_loc_id.strip())
            if success:
                self.refresh_all_ui()
            else:
                messagebox.showerror("Error", msg, parent=self.root)

    def _delete_location(self):
        selected_item = self.tree.focus()
        if not selected_item or self.tree.parent(selected_item): return

        sietch, loc_id, _ = self.tree.item(selected_item)['values']
        loc_pk = self.db.get_location_pk_by_name(sietch, loc_id)
        if not loc_pk: return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the location '{loc_id}' and all its tracked objects? This cannot be undone.", parent=self.root):
            self.db.delete_location(loc_pk)
            self.refresh_all_ui()
            for widget in self.graph_frame.winfo_children(): widget.destroy()
            ttk.Label(self.graph_frame, text="Select an object from the list to view its history.").pack()

    def _rename_object(self):
        selected_item = self.tree.focus()
        parent_id = self.tree.parent(selected_item)
        if not selected_item or not parent_id: return

        sietch, loc_id, _ = self.tree.item(parent_id)['values']
        _, _, old_obj_id = self.tree.item(selected_item)['values']

        obj_pk = self.db.get_object_pk_by_name(sietch, loc_id, old_obj_id)
        if not obj_pk: return

        new_obj_id = simpledialog.askstring("Rename Object", f"Enter new ID for object '{old_obj_id}':", parent=self.root)
        if new_obj_id and new_obj_id.strip() and new_obj_id.strip() != old_obj_id:
            success, msg = self.db.rename_object(obj_pk, new_obj_id.strip())
            if success:
                self.refresh_all_ui()
            else:
                messagebox.showerror("Error", msg, parent=self.root)

    def _delete_object(self):
        selected_item = self.tree.focus()
        parent_id = self.tree.parent(selected_item)
        if not selected_item or not parent_id: return

        sietch, loc_id, _ = self.tree.item(parent_id)['values']
        _, _, obj_id = self.tree.item(selected_item)['values']

        obj_pk = self.db.get_object_pk_by_name(sietch, loc_id, obj_id)
        if not obj_pk: return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the object '{obj_id}'? This cannot be undone.", parent=self.root):
            self.db.delete_object(obj_pk)
            self.refresh_all_ui()
            for widget in self.graph_frame.winfo_children(): widget.destroy()
            ttk.Label(self.graph_frame, text="Select an object from the list to view its history.").pack()

    def _adjust_health(self, history_id, sietch, location, obj_id):
        current_health_row = self.db.query("SELECT health_percent FROM history WHERE id = ?", (history_id,)).fetchone()
        if not current_health_row: return

        new_health = simpledialog.askfloat("Adjust Health", "Enter the correct health percentage:", parent=self.root, minvalue=0.0, maxvalue=100.0, initialvalue=current_health_row[0])
        if new_health is not None:
            self.db.update_history_health(history_id, new_health)
            self.display_object_history(sietch, location, obj_id)

    def _remove_point(self, history_id, sietch, location, obj_id):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this data point? This cannot be undone.", parent=self.root):
            self.db.delete_history_point(history_id)
            self.display_object_history(sietch, location, obj_id)

    def refresh_priority_watch_list(self):
        for i in self.priority_tree.get_children():
            self.priority_tree.delete(i)

        all_objects = self.db.get_all_objects_with_sietch_and_location()
        projections = []
        now = datetime.now()

        for sietch, location, obj_id in all_objects:
            history = self.db.get_history_for_object(sietch, location, obj_id)
            if len(history) < 2: continue

            # Estimate current health based on simple decay first
            last_point, second_last_point = history[-1], history[-2]
            time_delta_hours_lin = (last_point['timestamp'] - second_last_point['timestamp']).total_seconds() / 3600
            health_delta_lin = second_last_point['health'] - last_point['health']

            current_health_estimate = last_point['health']
            if time_delta_hours_lin > 0 and health_delta_lin > 0:
                decay_rate_per_hour = health_delta_lin / time_delta_hours_lin
                hours_since_last = (now - last_point['timestamp']).total_seconds() / 3600
                current_health_estimate = max(0, last_point['health'] - (decay_rate_per_hour * hours_since_last))

            if current_health_estimate <= 0: continue

            # Now calculate DSC projections with the estimated current health
            dsc_projs = self._calculate_dsc_projections(history, current_health_estimate)
            if dsc_projs:
                projections.append({
                    "failure_time": dsc_projs['worst'],
                    "object_str": f"{sietch} / {location} / {obj_id}"
                })

        projections.sort(key=lambda x: x['failure_time'])

        for proj in projections[:10]: # Display top 10
            time_to_failure = proj['failure_time'] - now
            if time_to_failure.total_seconds() > 0:
                self.priority_tree.insert("", "end", values=(self._format_timedelta(time_to_failure), proj['object_str']))

    def _format_timedelta(self, td):
        days, remainder = divmod(td.total_seconds(), 86400)
        hours, _ = divmod(remainder, 3600)
        return f"{int(days)}d, {int(hours)}h"

    def _calculate_dsc_projections(self, history, current_health_estimate):
        if len(history) < 2: return None
        first_obs, last_obs = history[0], history[-1]
        time_elapsed_hours = (last_obs['timestamp'] - first_obs['timestamp']).total_seconds() / 3600
        if time_elapsed_hours <= 0: return None
        estimated_scs = time_elapsed_hours / self.AVG_STORM_CYCLE_HOURS
        if estimated_scs <= 0: return None
        total_damage = first_obs['health'] - last_obs['health']
        if total_damage <= 0: return None
        dsc = total_damage / estimated_scs
        if dsc <= 0: return None
        remaining_scs = current_health_estimate / dsc
        now = datetime.now()
        return {
            "worst": now + timedelta(hours=remaining_scs * self.MIN_STORM_INTERVAL_H),
            "median": now + timedelta(hours=remaining_scs * self.AVG_STORM_CYCLE_HOURS),
            "latest": now + timedelta(hours=remaining_scs * self.MAX_STORM_INTERVAL_H),
        }

    def display_object_history(self, sietch, location, selected_object):
        if self.graph_canvas:
            self.graph_canvas.get_tk_widget().destroy()
            plt.close('all')
        for widget in self.graph_frame.winfo_children(): widget.destroy()

        self.graph_frame.grid_rowconfigure(0, weight=1)
        self.graph_frame.grid_rowconfigure(1, weight=1)
        self.graph_frame.grid_columnconfigure(0, weight=1)

        graph_container = ttk.Frame(self.graph_frame)
        graph_container.grid(row=0, column=0, sticky="nsew")
        history_container = ttk.Frame(self.graph_frame)
        history_container.grid(row=1, column=0, sticky="nsew")

        history = self.db.get_history_for_object(sietch, location, selected_object)

        if len(history) < 2:
            ttk.Label(graph_container, text="Not enough data to plot a graph.").pack(expand=True)
        else:
            fig = Figure(figsize=(5, 3), dpi=100)
            fig.patch.set_facecolor('#1f2937')
            ax = fig.add_subplot(111)
            last_point, second_last_point = history[-1], history[-2]
            time_delta_hours = (last_point['timestamp'] - second_last_point['timestamp']).total_seconds() / 3600
            health_delta = second_last_point['health'] - last_point['health']
            decay_rate_per_hour = (health_delta / time_delta_hours) if (time_delta_hours > 0 and health_delta > 0) else 0
            if decay_rate_per_hour > 0:
                hours_to_failure = last_point['health'] / decay_rate_per_hour
                failure_date = last_point['timestamp'] + timedelta(hours=hours_to_failure)
                ax.plot([last_point['timestamp'], failure_date], [last_point['health'], 0], 'b-', label='Projected Decay')
            timestamps = [h['timestamp'] for h in history]; healths = [h['health'] for h in history]
            ax.plot(timestamps, healths, 'g-o', label='Actual Decay', markersize=4)
            now = datetime.now()
            hours_since_last_capture = (now - last_point['timestamp']).total_seconds() / 3600
            current_health_estimate = last_point['health'] - (decay_rate_per_hour * hours_since_last_capture) if decay_rate_per_hour > 0 else last_point['health']
            current_health_estimate = max(0, current_health_estimate)
            if current_health_estimate < last_point['health']: ax.plot([last_point['timestamp'], now], [last_point['health'], current_health_estimate], 'g-')
            if current_health_estimate > 0:
                projections = self._calculate_dsc_projections(history, current_health_estimate)
                if projections:
                    ax.plot([now, projections['worst']], [current_health_estimate, 0], 'g:', label='DSC: W')
                    ax.plot([now, projections['median']], [current_health_estimate, 0], 'y:', label='DSC: M')
                    ax.plot([now, projections['latest']], [current_health_estimate, 0], 'r:', label='DSC: L')
            ax.set_facecolor('#0f172a'); ax.tick_params(axis='x', colors='white', labelsize=8); ax.tick_params(axis='y', colors='white', labelsize=8)
            for spine in ax.spines.values(): spine.set_color('white')
            ax.set_xlabel("Date", color='white', fontsize=10); ax.set_ylabel("Health %", color='white', fontsize=10)
            ax.set_title(f"Decay History for {selected_object}", color='white', fontsize=12)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M')); fig.autofmt_xdate(rotation=30)
            ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='#475569')
            ax.set_ylim(0, max(h['health'] for h in history) * 1.05 if history else 100)
            legend = ax.legend(facecolor='#1f2937', edgecolor='white', fontsize=8)
            for text in legend.get_texts(): text.set_color('white')
            fig.tight_layout(pad=1.5)
            self.graph_canvas = FigureCanvasTkAgg(fig, master=graph_container)
            self.graph_canvas.draw()
            self.graph_canvas.get_tk_widget().pack(side=tk.TOP, fill='both', expand=True)

        history_container.grid_rowconfigure(2, weight=1)
        history_container.grid_columnconfigure(0, weight=1)
        ttk.Separator(history_container).grid(row=0, column=0, sticky='ew', padx=5, pady=(0, 5))
        ttk.Label(history_container, text="Data Points", font=('Arial', 12, 'bold')).grid(row=1, column=0, sticky='w', padx=5)
        history_frame = ScrollableFrame(history_container)
        history_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=(5,0))

        if not history:
            ttk.Label(history_frame.scrollable_frame, text="No history for this object.").pack()
        for point in reversed(history):
            point_frame = ttk.Frame(history_frame.scrollable_frame, padding=5)
            point_frame.pack(fill='x', expand=True, pady=2)
            point_frame.columnconfigure(1, weight=1)
            img_path = point.get("image_path")
            thumb_label = ttk.Label(point_frame)
            if img_path and os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    img.thumbnail((50, 50))
                    photo_key = f"history_{point['id']}"
                    self.photo_references[photo_key] = ImageTk.PhotoImage(img)
                    thumb_label.config(image=self.photo_references[photo_key])
                except Exception as e:
                    self.log_error("Image Loading", f"Failed to load {img_path}: {e}")
            thumb_label.grid(row=0, column=0, sticky='w', padx=(0, 10))
            info_text = f"Health: {point['health']:.2f}%  -  {point['timestamp'].strftime('%Y-%m-%d %H:%M')}"
            ttk.Label(point_frame, text=info_text).grid(row=0, column=1, sticky='w')
            adjust_btn = ttk.Button(point_frame, text="Adjust", command=lambda p=point: self._adjust_health(p['id'], sietch, location, selected_object))
            adjust_btn.grid(row=0, column=2, sticky='e', padx=(5,0))
            remove_btn = ttk.Button(point_frame, text="Remove", command=lambda p=point: self._remove_point(p['id'], sietch, location, selected_object))
            remove_btn.grid(row=0, column=3, sticky='e', padx=(5,0))

    def set_main_map_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")]);
        if not path: return
        dest_path = os.path.join(self.image_folder, "main_map" + os.path.splitext(path)[1])
        shutil.copy(path, dest_path)
        self.db.set_config("main_map_path", dest_path)
        self.map_frame.load_map()

    def on_closing(self):
        self.db.close()
        self.root.destroy()

    @staticmethod
    def log_error(source="Application", error_data=None):
        print(f"\n--- ERROR in {source} ---")
        if error_data: print(error_data)
        else: traceback.print_exc()
        print("----------------------------------\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = VultureTrackerApp(root)
    root.mainloop()