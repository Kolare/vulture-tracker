import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from PIL import Image, ImageTk
import os
import shutil
import datetime

class ScrollableFrame(ttk.Frame):
    # (This class remains unchanged)
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg="#1f2937", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Bind mouse wheel scrolling to the canvas
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows
        self.canvas.bind_all("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel) # Linux scroll down

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """Cross-platform mouse wheel scroll event."""
        # Check if the mouse is over this specific canvas
        if not str(self.canvas.winfo_containing(event.x_root, event.y_root)).startswith(str(self.canvas)):
            return

        if event.num == 5 or event.delta == -120:
            self.canvas.yview_scroll(1, "units")
        if event.num == 4 or event.delta == 120:
            self.canvas.yview_scroll(-1, "units")

class SietchManagerWindow(tk.Toplevel):
    """A Toplevel window for adding, renaming, and deleting sietches."""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Manage Sietches")
        self.transient(parent)
        self.grab_set()

        # Left side for list
        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(side="left", fill="y", padx=5)
        ttk.Label(list_frame, text="Existing Sietches:").pack(anchor='w')
        self.sietch_listbox = tk.Listbox(list_frame, width=30)
        self.sietch_listbox.pack(fill="y", expand=True)
        self.populate_list()

        # Right side for actions
        action_frame = ttk.Frame(self, padding=10)
        action_frame.pack(side="left", fill="y", padx=5)
        
        # Add Sietch
        ttk.Label(action_frame, text="Add New Sietch:").pack(anchor='w')
        self.new_sietch_var = tk.StringVar()
        ttk.Entry(action_frame, textvariable=self.new_sietch_var).pack(fill='x', pady=5)
        ttk.Button(action_frame, text="Add", command=self.add_sietch).pack(fill='x')

        # Rename Sietch
        ttk.Button(action_frame, text="Rename Selected", command=self.rename_sietch).pack(fill='x', pady=(20, 5))
        
        # Delete Sietch
        ttk.Button(action_frame, text="Delete Selected", command=self.delete_sietch).pack(fill='x', pady=5)

    def populate_list(self):
        self.sietch_listbox.delete(0, tk.END)
        sietches = self.app.db.get_sietches()
        for sietch in sietches:
            self.sietch_listbox.insert(tk.END, sietch)

    def add_sietch(self):
        name = self.new_sietch_var.get().strip()
        if name:
            success, msg = self.app.db.add_sietch(name)
            if success:
                self.new_sietch_var.set("")
                self.populate_list()
                self.app.refresh_all_ui()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def rename_sietch(self):
        selected_index = self.sietch_listbox.curselection()
        if not selected_index: return
        old_name = self.sietch_listbox.get(selected_index)
        
        new_name = simpledialog.askstring("Rename Sietch", f"Enter new name for '{old_name}':", parent=self)
        if new_name and new_name.strip() and new_name.strip() != old_name:
            success, msg = self.app.db.rename_sietch(old_name, new_name.strip())
            if success:
                self.populate_list()
                self.app.refresh_all_ui()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def delete_sietch(self):
        selected_index = self.sietch_listbox.curselection()
        if not selected_index: return
        name = self.sietch_listbox.get(selected_index)
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{name}' and all its locations and objects? This cannot be undone.", parent=self):
            self.app.db.delete_sietch(name)
            self.populate_list()
            self.app.refresh_all_ui()

class MapFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.pins = {}
        # Zoom/Pan state variables
        self.zoom_level = 1.0
        self.view_x, self.view_y = 0, 0
        self.pan_start_x, self.pan_start_y = 0, 0
        self.original_map_image = None
        
        control_frame = ttk.Frame(self)
        control_frame.pack(fill='x', pady=5)
        ttk.Label(control_frame, text="Filter by Sietch:").pack(side='left', padx=5)
        self.sietch_filter_var = tk.StringVar(value="All")
        self.sietch_filter_menu = ttk.Combobox(control_frame, textvariable=self.sietch_filter_var, state="readonly")
        self.sietch_filter_menu.pack(side='left', padx=5)
        self.sietch_filter_menu.bind("<<ComboboxSelected>>", self.redraw_canvas)

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill='x')
        
        self.dragged_pin_id = None
        self.dragged_pin_visual = None

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self.on_pin_press) # Left-click to start drag
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start) # Middle mouse for pan
        self.canvas.bind("<B2-Motion>", self.on_pan_move)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom) # For Linux
        self.canvas.bind("<Button-5>", self.on_zoom) # For Linux
        self.canvas.bind("<Button-3>", self.on_right_click) # General right-click handler

        # Create the context menu but don't show it yet
        self.pin_context_menu = tk.Menu(self.canvas, tearoff=0)
        self.pin_context_menu.add_command(label="Rename Location", command=self.rename_pin)
        self.pin_context_menu.add_command(label="Delete Location", command=self.delete_pin)
        self.context_menu_pin_id = None
        
        self.load_map()

    def on_right_click(self, event):
        """Handles right-clicks, prioritizing context menu on pins over adding new pins."""
        items = self.canvas.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)

        found_pin = False
        if items:
            for item_id in reversed(items):
                tags = self.canvas.gettags(item_id)
                if "pin_oval" in tags:
                    # Found a pin, show context menu
                    for tag in tags:
                        if tag.startswith("loc_pk_"):
                            self.context_menu_pin_id = int(tag.split('_')[2])
                            self.pin_context_menu.tk_popup(event.x_root, event.y_root)
                            found_pin = True
                            break # Stop inner loop
                    if found_pin:
                        break # Stop outer loop

        if not found_pin:
            # No pin was found in the click area, so add a new one
            self.add_pin(event)

    def rename_pin(self):
        """Renames the location associated with the context-clicked pin."""
        if self.context_menu_pin_id is None: return

        loc_pk = self.context_menu_pin_id
        old_name = self.app.db.get_location_name(loc_pk)
        new_name = simpledialog.askstring("Rename Location", f"Enter new name for '{old_name}':", parent=self)

        if new_name and new_name.strip() and new_name.strip() != old_name:
            success, msg = self.app.db.rename_location(loc_pk, new_name.strip())
            if success:
                self.app.refresh_all_ui()
            else:
                messagebox.showerror("Error", msg, parent=self)
        self.context_menu_pin_id = None

    def delete_pin(self):
        """Deletes the location associated with the context-clicked pin."""
        if self.context_menu_pin_id is None: return

        loc_pk = self.context_menu_pin_id
        loc_name = self.app.db.get_location_name(loc_pk)
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the location '{loc_name}' and all its objects? This is irreversible.", parent=self):
            self.app.db.delete_location(loc_pk)
            self.app.refresh_all_ui()
        self.context_menu_pin_id = None

    def on_pin_press(self, event):
        """Selects a pin to be dragged using an overlapping search."""
        items = self.canvas.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)
        if not items:
            return

        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "pin_oval" in tags:
                for tag in tags:
                    if tag.startswith("loc_pk_"):
                        self.dragged_pin_id = int(tag.split('_')[2])
                        self.dragged_pin_visual = item_id
                        self.canvas.bind("<B1-Motion>", self.on_pin_drag)
                        self.canvas.bind("<ButtonRelease-1>", self.on_pin_drop)
                        return # Exit after finding the first pin

    def on_pin_drag(self, event):
        """Moves the selected pin visual on the canvas."""
        if self.dragged_pin_visual:
            # Move the oval part of the pin
            self.canvas.coords(self.dragged_pin_visual, event.x - 5, event.y - 5, event.x + 5, event.y + 5)
            # Find the corresponding text and move it as well
            text_item = self.canvas.find_withtag(f"text_for_{self.dragged_pin_id}")
            if text_item:
                self.canvas.coords(text_item[0], event.x, event.y - 10)

    def on_pin_drop(self, event):
        """Updates the pin's location in the database after dragging."""
        if self.dragged_pin_id:
            # Convert final canvas coordinates back to original image coordinates
            new_image_x = self.view_x + event.x / self.zoom_level
            new_image_y = self.view_y + event.y / self.zoom_level

            # Update database
            self.app.db.update_pin_location(self.dragged_pin_id, int(new_image_x), int(new_image_y))

        # Cleanup
        self.dragged_pin_id = None
        self.dragged_pin_visual = None
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.app.refresh_all_ui()

    def add_pin(self, event):
        """Callback to add a new pin at the clicked location."""
        if not self.original_map_image:
            messagebox.showwarning("No Map", "Cannot add a pin without a map loaded.", parent=self)
            return

        # Convert canvas coordinates to original image coordinates
        image_x = self.view_x + event.x / self.zoom_level
        image_y = self.view_y + event.y / self.zoom_level

        # Ask for location name
        loc_name = simpledialog.askstring("New Location", "Enter the name for this new location:", parent=self)
        if not loc_name or not loc_name.strip():
            return # User cancelled or entered empty name

        # Determine the sietch
        selected_sietch = self.sietch_filter_var.get()
        if not selected_sietch or selected_sietch == "All":
            messagebox.showerror("Sietch Required", "Please select a specific Sietch from the filter dropdown before adding a pin.", parent=self)
            return

        # Add to database
        self.app.db.add_location(selected_sietch, loc_name.strip(), int(image_x), int(image_y))

        # Refresh UI
        self.app.refresh_all_ui()

    def load_map(self):
        map_path = self.app.db.get_config("main_map_path")
        if map_path and os.path.exists(map_path):
            self.original_map_image = Image.open(map_path)
            self.zoom_level = 1.0
            self.view_x, self.view_y = 0, 0
            self.app.root.after(100, self.redraw_canvas)
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="No Map Set. Use File -> Set Main Map Image...", fill="white")
            self.canvas.config(width=800, height=600)

    def redraw_canvas(self, event=None):
        if not self.original_map_image: return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 2: canvas_width=800 # Default size if not drawn yet
        if canvas_height < 2: canvas_height=600

        # Calculate the portion of the original image to show
        crop_w = int(canvas_width / self.zoom_level)
        crop_h = int(canvas_height / self.zoom_level)
        
        # Crop from the original full-resolution image
        crop_box = (self.view_x, self.view_y, self.view_x + crop_w, self.view_y + crop_h)
        map_crop = self.original_map_image.crop(crop_box)
        
        # Resize the crop to fit the canvas
        resized_crop = map_crop.resize((canvas_width, canvas_height))
        
        self.app.photo_references['map'] = ImageTk.PhotoImage(resized_crop)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.app.photo_references['map'])
        self.load_pins()

    def load_pins(self):
        selected_sietch = self.sietch_filter_var.get()
        locations = self.app.db.get_all_pinned_locations()
        for loc_pk, loc_id, pin_x, pin_y, sietch_name in locations:
            if selected_sietch != "All" and sietch_name != selected_sietch:
                continue
            
            # Translate original image coordinates to canvas coordinates
            canvas_x = (pin_x - self.view_x) * self.zoom_level
            canvas_y = (pin_y - self.view_y) * self.zoom_level

            # Only draw pin if it's visible on the current canvas
            if 0 < canvas_x < self.canvas.winfo_width() and 0 < canvas_y < self.canvas.winfo_height():
                # Add specific tags for dragging and identification
                pin_tags = ("pin", "pin_oval", f"loc_pk_{loc_pk}")
                text_tags = ("pin", "pin_text", f"text_for_{loc_pk}")

                self.canvas.create_oval(canvas_x-5, canvas_y-5, canvas_x+5, canvas_y+5, fill="red", outline="white", tags=pin_tags)
                self.canvas.create_text(canvas_x, canvas_y - 10, text=loc_id, fill="white", tags=text_tags)
                
    def on_pan_start(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_pan_move(self, event):
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.view_x -= dx / self.zoom_level
        self.view_y -= dy / self.zoom_level

        # Clamp the view to the image boundaries
        self.clamp_view()

        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.redraw_canvas()

    def on_zoom(self, event):
        if not self.original_map_image: return
        scale_factor = 1.2

        if (event.delta > 0 or event.num == 4): # Zoom in
            new_zoom = self.zoom_level * scale_factor
        elif (event.delta < 0 or event.num == 5): # Zoom out
            new_zoom = self.zoom_level / scale_factor
        else:
            return

        # Clamp zoom level
        min_zoom = max(self.canvas.winfo_width() / self.original_map_image.width, self.canvas.winfo_height() / self.original_map_image.height)
        new_zoom = max(min_zoom, min(new_zoom, 10.0)) # Min zoom fills canvas, max is 10x

        # Get mouse position relative to the canvas
        mouse_x, mouse_y = event.x, event.y
        
        # Get the point on the original image under the mouse
        image_x = self.view_x + mouse_x / self.zoom_level
        image_y = self.view_y + mouse_y / self.zoom_level

        self.zoom_level = new_zoom
        
        # Recalculate view to keep the point under the mouse stationary
        self.view_x = image_x - mouse_x / self.zoom_level
        self.view_y = image_y - mouse_y / self.zoom_level
        
        self.clamp_view()
        self.redraw_canvas()

    def clamp_view(self):
        """Ensures the view stays within the map boundaries."""
        if not self.original_map_image: return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        crop_w = canvas_width / self.zoom_level
        crop_h = canvas_height / self.zoom_level

        max_x = self.original_map_image.width - crop_w
        max_y = self.original_map_image.height - crop_h

        self.view_x = max(0, min(self.view_x, max_x))
        self.view_y = max(0, min(self.view_y, max_y))

    def update_filter_options(self):
        sietches = ["All"] + self.app.db.get_sietches()
        self.sietch_filter_menu['values'] = sietches

class SietchOverviewFrame(ttk.Frame):
    """A dedicated frame for displaying the detailed, collapsible sietch/location/object overview."""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self.db = app.db

        # This will be the main container for all the collapsible frames
        self.container = ScrollableFrame(self)
        self.container.pack(fill='both', expand=True)
        self.content_frame = self.container.scrollable_frame

    def refresh_overview(self):
        """Clears and rebuilds the entire overview from the database."""
        # Clear existing content
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        sietches = self.db.get_sietches()
        if not sietches:
            ttk.Label(self.content_frame, text="No Sietches found. Add one from the File menu.").pack(pady=10)
            return

        for sietch_name in sietches:
            self.create_sietch_frame(sietch_name)

    def create_sietch_frame(self, sietch_name):
        """Creates the collapsible frame for a single sietch and its locations."""
        sietch_frame = ttk.LabelFrame(self.content_frame, text=sietch_name, padding=10)
        sietch_frame.pack(fill='x', expand=True, pady=2, padx=5)

        locations = self.db.query("SELECT id, location_id FROM locations WHERE sietch_name=? ORDER BY location_id", (sietch_name,)).fetchall()

        if not locations:
            ttk.Label(sietch_frame, text="No locations in this sietch.", style='Italic.TLabel').pack()
        else:
            for loc_pk, loc_id in locations:
                self.create_location_frame(sietch_frame, loc_pk, loc_id)

    def create_location_frame(self, parent_frame, loc_pk, loc_id):
        """Creates the collapsible frame for a single location and its objects."""
        loc_frame = ttk.Frame(parent_frame, style='Object.TFrame')
        loc_frame.pack(fill='x', expand=True, pady=(2,0))

        header_frame = ttk.Frame(loc_frame, style='Location.TFrame', cursor="hand2")
        header_frame.pack(fill='x', expand=True)

        objects_container = ttk.Frame(loc_frame, padding=(10, 5, 0, 0))

        def toggle(event):
            self.toggle_visibility(objects_container)

        header_frame.bind("<Button-1>", toggle)

        label = ttk.Label(header_frame, text=loc_id, font=('Arial', 11, 'bold'))
        label.pack(side='left', padx=(5,0))
        label.bind("<Button-1>", toggle)

        status = self.db.get_location_status(loc_pk)
        last_updated_ts, lowest_health = status if status else (None, None)

        status_dot_canvas = tk.Canvas(header_frame, width=12, height=12, highlightthickness=0, bg=self.app.accent_color)
        status_dot_canvas.pack(side='left', padx=10)
        status_dot_canvas.bind("<Button-1>", toggle)

        dot_color = "#4b5563" # Gray for no data
        if last_updated_ts:
            now_ts = datetime.datetime.now().timestamp()
            history_counts = self.db.query("SELECT COUNT(h.id) FROM history h JOIN objects o ON h.object_fk = o.id WHERE o.location_fk = ?", (loc_pk,)).fetchone()
            total_history_points = history_counts[0] if history_counts else 0

            if total_history_points <= 1:
                dot_color = "#3b82f6" # Blue for single data point
            else:
                age_hours = (now_ts - last_updated_ts) / 3600
                if age_hours <= 12: dot_color = "#22c55e" # Green
                elif age_hours <= 48: dot_color = "#f59e0b" # Yellow
                else: dot_color = "#ef4444" # Red

        status_dot_canvas.create_oval(2, 2, 10, 10, fill=dot_color, outline=dot_color)

        if lowest_health is not None:
            # Calculate time to wreck for the location's most critical item
            time_to_wreck_str = ""
            priority_list = self.db.get_priority_watch_list(limit=100) # Get a larger list to find our item
            for item in priority_list:
                if item['sietch'] == parent_frame.cget('text') and item['location'] == loc_id:
                    wreck_time = datetime.datetime.fromtimestamp(item['estimated_wreck_time'])
                    time_diff = wreck_time - datetime.datetime.now()
                    if time_diff.total_seconds() < 0:
                        time_to_wreck_str = "(Now)"
                    else:
                        days, rem = divmod(time_diff.total_seconds(), 86400)
                        hours, rem = divmod(rem, 3600)
                        mins, _ = divmod(rem, 60)
                        time_to_wreck_str = f"({int(days)}d {int(hours)}h)" if days > 0 else f"({int(hours)}h {int(mins)}m)"
                    break

            health_text = f" | {lowest_health:.1f}% {time_to_wreck_str}" if lowest_health > 0 else f" | Wrecked {time_to_wreck_str}"
            health_label = ttk.Label(header_frame, text=health_text)
            health_label.pack(side='left')
            health_label.bind("<Button-1>", toggle)

        objects = self.db.get_objects_for_location(loc_pk)
        if not objects:
            ttk.Label(objects_container, text="No objects at this location.", style='Italic.TLabel').pack(anchor='w')
        else:
            for obj_pk, obj_id, obj_img_path, base_hp in objects:
                self.create_object_frame(objects_container, obj_pk, obj_id, obj_img_path, base_hp)

    def toggle_visibility(self, frame):
        """Shows or hides a frame."""
        if frame.winfo_viewable():
            frame.pack_forget()
        else:
            frame.pack(fill='x', expand=True)

    def create_object_frame(self, parent_frame, obj_pk, obj_id, obj_img_path, base_hp):
        """Creates the detailed, interactive frame for a single object."""
        obj_container = ttk.LabelFrame(parent_frame, text=obj_id, padding=5)
        obj_container.pack(fill='x', expand=True, padx=0, pady=2)

        top_section = ttk.Frame(obj_container)
        top_section.pack(fill='x', expand=True)

        # Left side: User Image and Sub-map
        left_panel = ttk.Frame(top_section)
        left_panel.pack(side='left', padx=(0, 10))

        # User-provided image
        img_label = ttk.Label(left_panel, text="No Image")
        img_label.pack(pady=5)
        if obj_img_path and os.path.exists(obj_img_path):
            try:
                img = Image.open(obj_img_path)
                img.thumbnail((150, 150))
                self.app.photo_references[f"obj_{obj_pk}"] = ImageTk.PhotoImage(img)
                img_label.config(image=self.app.photo_references[f"obj_{obj_pk}"])
            except Exception as e:
                img_label.config(text="Error loading image")
                print(f"Error loading object image {obj_img_path}: {e}")

        # Sub-map would be complex, adding a placeholder for now
        ttk.Label(left_panel, text="Sub-map placeholder").pack(pady=5)

        # Right side: History and controls
        right_panel = ttk.Frame(top_section)
        right_panel.pack(side='left', fill='x', expand=True)

        # Decay Graph placeholder
        graph_canvas = tk.Canvas(right_panel, height=60, bg="#2d3748")
        graph_canvas.pack(fill='x', pady=5)
        graph_canvas.create_text(10, 10, text="Decay graph to be implemented here.", fill='white', anchor='nw')

        # History Frame
        history_frame = ttk.Frame(right_panel)
        history_frame.pack(fill='x', expand=True)
        ttk.Label(history_frame, text="History:", font=('Arial', 10, 'bold')).pack(anchor='w')

        history_records = self.db.get_history_for_object(obj_pk)
        if not history_records:
            ttk.Label(history_frame, text="No history records.").pack(anchor='w')
        else:
            for hist_pk, ts, health, path in history_records:
                record_frame = ttk.Frame(history_frame)
                record_frame.pack(fill='x', pady=2)

                # Thumbnail of the center crop
                thumb_label = ttk.Label(record_frame)
                thumb_label.pack(side='left', padx=5)
                if path and os.path.exists(path):
                    try:
                        thumb_img = Image.open(path)
                        thumb_img.thumbnail((40, 40))
                        self.app.photo_references[f"hist_{hist_pk}"] = ImageTk.PhotoImage(thumb_img)
                        thumb_label.config(image=self.app.photo_references[f"hist_{hist_pk}"])
                    except: pass

                ts_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                health_str = f"Health: {health}"
                ttk.Label(record_frame, text=f"{ts_str} | {health_str}").pack(side='left', expand=True, fill='x')

                # Buttons for interaction
                ttk.Button(record_frame, text="Adjust", command=lambda h_pk=hist_pk: self.adjust_health(h_pk)).pack(side='right')
                ttk.Button(record_frame, text="Remove", command=lambda h_pk=hist_pk: self.remove_history(h_pk)).pack(side='right', padx=5)

    def adjust_health(self, hist_pk):
        """Placeholder for the health adjustment UI."""
        new_health = simpledialog.askstring("Adjust Health", "Enter new health value or 'wrecked':", parent=self)
        if new_health is not None:
            self.db.update_history_health(hist_pk, new_health.strip())
            self.app.refresh_all_ui()

    def remove_history(self, hist_pk):
        """Removes a history point after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this data point? This cannot be undone.", parent=self):
            self.db.delete_history_point(hist_pk)
            self.app.refresh_all_ui()