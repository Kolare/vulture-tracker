import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from PIL import Image, ImageTk
import os
import shutil
import datetime
import cv2
import math
import re
from analyzer import HealthAnalyzer

class ScrollableFrame(ttk.Frame):
    # (This class remains unchanged)
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg="#1f2937", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # This binding ensures the inner frame resizes horizontally with the canvas
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.window, width=e.width))
        # This binding updates the scrollregion when the inner frame's content changes
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Bind mouse wheel scrolling to the canvas
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows
        self.canvas.bind_all("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel) # Linux scroll down
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """Cross-platform mouse wheel scroll event."""
        try:
            # Check if the mouse is over this specific canvas
            if not str(self.canvas.winfo_containing(event.x_root, event.y_root)).startswith(str(self.canvas)):
                return
        except Exception:
            # This can happen if the mouse is over a temporary widget like a dropdown list.
            # Catching the generic exception is safer here.
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
        self.canvas.pack(fill='both', expand=True)
        
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
            
            # Invalidate the cached sub-map image for this location so it gets regenerated
            sub_map_key = f"submap_{self.dragged_pin_id}"
            if sub_map_key in self.app.photo_references:
                del self.app.photo_references[sub_map_key]

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
        selected_sietch_display = self.sietch_filter_var.get()
        if not selected_sietch_display or selected_sietch_display == "All":
            messagebox.showerror("Sietch Required", "Please select a specific Sietch from the filter dropdown before adding a pin.", parent=self)
            return
            
        sietch_name = selected_sietch_display.split(' (')[0]

        # Add to database
        self.app.db.add_location(sietch_name, loc_name.strip(), int(image_x), int(image_y))
        
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
        selected_sietch_display = self.sietch_filter_var.get()
        sietch_filter_name = selected_sietch_display.split(' (')[0] # Get the actual name
        
        locations = self.app.db.get_all_pinned_locations()
        for loc_pk, loc_id, pin_x, pin_y, sietch_name in locations:
            if sietch_filter_name != "All" and sietch_name != sietch_filter_name:
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
        sietch_data = self.app.db.get_sietches_with_location_counts()
        display_values = ["All"] + [f"{name} ({count})" for name, count in sietch_data]
        self.sietch_filter_menu['values'] = display_values

class SietchOverviewFrame(ttk.Frame):
    """A dedicated frame for displaying the detailed, collapsible sietch/location/object overview."""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self.db = app.db
        # This component no longer needs its own scrollbar, as its parent is now the scrollable frame.

    def refresh_overview(self):
        """Clears and rebuilds the entire overview from the database."""
        for widget in self.winfo_children():
            widget.destroy()

        sietch_data = self.db.get_sietches_with_location_counts()
        if not sietch_data:
            ttk.Label(self, text="No Sietches found. Add one from the File menu.").pack(pady=10)
            return

        for sietch_name, count in sietch_data:
            display_text = f"{sietch_name} ({count})"
            self.create_sietch_frame(sietch_name, display_text)

    def create_sietch_frame(self, sietch_name, display_text):
        """Creates the collapsible frame for a single sietch and its locations."""
        sietch_frame = ttk.LabelFrame(self, text=display_text, padding=10)
        sietch_frame.pack(fill='x', expand=True, pady=2, padx=5)
        
        locations = self.db.query("SELECT id, location_id, pin_x, pin_y FROM locations WHERE sietch_name=? ORDER BY location_id", (sietch_name,)).fetchall()
        
        if not locations:
            ttk.Label(sietch_frame, text="No locations in this sietch.", style='Italic.TLabel').pack()
        else:
            for loc_pk, loc_id, pin_x, pin_y in locations:
                self.create_location_frame(sietch_frame, loc_pk, loc_id, pin_x, pin_y)

    def create_location_frame(self, parent_frame, loc_pk, loc_id, pin_x, pin_y):
        """Creates the collapsible frame for a single location and its objects."""
        loc_frame = ttk.Frame(parent_frame, style='Object.TFrame')
        loc_frame.pack(fill='x', expand=True, pady=(2,0))
        
        header_frame = ttk.Frame(loc_frame, style='Location.TFrame', cursor="hand2")
        header_frame.pack(fill='x', expand=True)
        
        objects_container = ttk.Frame(loc_frame, padding=(10, 5, 0, 0))
        
        def toggle(event):
            self.toggle_visibility(objects_container)

        header_frame.bind("<Button-1>", toggle)
        
        status = self.db.get_location_status(loc_pk)
        last_updated_ts, lowest_health = status if status else (None, None)

        indicator_text = ""
        indicator_color = "red"
        if last_updated_ts:
            age_hours = (datetime.datetime.now().timestamp() - last_updated_ts) / 3600
            if age_hours <= 12:
                indicator_text = "✔"
                indicator_color = "green"
            else:
                indicator_text = "✘"
        else:
            indicator_text = "✘"
            
        indicator_label = ttk.Label(header_frame, text=indicator_text, font=('Arial', 12, 'bold'), foreground=indicator_color)
        indicator_label.pack(side='left', padx=(5,0))
        indicator_label.bind("<Button-1>", toggle)

        label = ttk.Label(header_frame, text=loc_id, font=('Arial', 11, 'bold'))
        label.pack(side='left', padx=(5,0))
        label.bind("<Button-1>", toggle)
        
        if lowest_health is not None:
            time_to_wreck_str = ""
            priority_list = self.db.get_priority_watch_list(limit=100)
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
                self.create_object_frame(objects_container, loc_pk, obj_pk, obj_id, obj_img_path, base_hp, pin_x, pin_y)

    def toggle_visibility(self, frame):
        """Shows or hides a frame."""
        if frame.winfo_viewable():
            frame.pack_forget()
        else:
            frame.pack(fill='x', expand=True)

    def create_object_frame(self, parent_frame, loc_pk, obj_pk, obj_id, obj_img_path, base_hp, pin_x, pin_y):
        """Creates the detailed, interactive, and collapsible frame for a single object."""
        obj_container = ttk.Frame(parent_frame, style='Object.TFrame')
        obj_container.pack(fill='x', expand=True, padx=0, pady=2)

        header_frame = ttk.Frame(obj_container, style='Location.TFrame', cursor="hand2")
        header_frame.pack(fill='x', expand=True)
        
        details_container = ttk.Frame(obj_container, padding=(10,5))
        # details_container starts hidden

        def toggle(event):
            self.toggle_visibility(details_container)

        header_frame.bind("<Button-1>", toggle)
        
        label = ttk.Label(header_frame, text=obj_id, font=('Arial', 10, 'bold'))
        label.pack(side='left', padx=5)
        label.bind("<Button-1>", toggle)

        # Add management buttons
        ttk.Button(header_frame, text="Delete", command=lambda o_pk=obj_pk: self.delete_object(o_pk)).pack(side='right')
        ttk.Button(header_frame, text="Rename", command=lambda o_pk=obj_pk, old_name=obj_id: self.rename_object(o_pk, old_name)).pack(side='right', padx=5)
        ttk.Button(header_frame, text="Set Image", command=lambda o_pk=obj_pk: self.set_object_image(o_pk)).pack(side='right', padx=5)
        ttk.Button(header_frame, text="Set Base HP", command=lambda o_pk=obj_pk, cur_hp=base_hp: self.set_base_hp(o_pk, cur_hp)).pack(side='right')

        top_section = ttk.Frame(details_container)
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

        # --- Sub-map implementation ---
        sub_map_canvas = tk.Canvas(left_panel, width=150, height=150, bg="black", highlightthickness=0)
        sub_map_canvas.pack(pady=5)

        main_map_image = self.app.map_frame.original_map_image
        sub_map_key = f"submap_{loc_pk}"

        if main_map_image and pin_x is not None and pin_y is not None:
            # Create the sub-map image only once per location and store it
            if sub_map_key not in self.app.photo_references:
                try:
                    crop_width = 300
                    crop_x1 = pin_x - (crop_width // 2)
                    crop_y1 = pin_y - (crop_width // 2)
                    crop_x2 = pin_x + (crop_width // 2)
                    crop_y2 = pin_y + (crop_width // 2)
                    
                    sub_map_crop = main_map_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                    sub_map_resized = sub_map_crop.resize((150, 150), Image.Resampling.LANCZOS)
                    self.app.photo_references[sub_map_key] = ImageTk.PhotoImage(sub_map_resized)
                except Exception as e:
                    print(f"Error creating sub-map for loc_pk {loc_pk}: {e}")
                    self.app.photo_references[sub_map_key] = None # Mark as failed
            
            # Display the stored sub-map image
            if self.app.photo_references.get(sub_map_key):
                sub_map_canvas.create_image(0, 0, anchor='nw', image=self.app.photo_references[sub_map_key])
                center = 150 / 2
                sub_map_canvas.create_oval(center-3, center-3, center+3, center+3, fill='red', outline='white')
            else:
                sub_map_canvas.create_text(75, 75, text="Error creating\nsub-map.", fill='white', anchor='center')
        else:
            sub_map_canvas.create_text(75, 75, text="No pin set for\nthis location.", fill='white', anchor='center')
        
        # Right side: History and controls
        right_panel = ttk.Frame(top_section)
        right_panel.pack(side='left', fill='x', expand=True)

        # Decay Graph
        history_records = self.db.get_history_for_object(obj_pk)
        graph = DecayGraph(right_panel, history_records)
        graph.pack(fill='x', pady=5)

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
                
                # Thumbnail or "M/E" for manual entry
                thumb_label = ttk.Label(record_frame, text="M/E", font=('Arial', 8, 'italic'))
                thumb_label.pack(side='left', padx=5, ipadx=5)
                
                if path and path != "M/E" and os.path.exists(path):
                    try:
                        thumb_img = Image.open(path)
                        thumb_img.thumbnail((40, 40))
                        self.app.photo_references[f"hist_{hist_pk}"] = ImageTk.PhotoImage(thumb_img)
                        thumb_label.config(image=self.app.photo_references[f"hist_{hist_pk}"], text="") # Clear text if image is shown
                    except:
                        thumb_label.config(text="ERR", font=('Arial', 8, 'bold')) # Show error if image fails to load
                
                ts_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                health_str = f"Health: {health}"
                ttk.Label(record_frame, text=f"{ts_str} | {health_str}").pack(side='left', expand=True, fill='x')
                
                # Buttons for interaction
                ttk.Button(record_frame, text="Adjust", command=lambda h_pk=hist_pk: self.adjust_health(h_pk)).pack(side='right')
                ttk.Button(record_frame, text="Remove", command=lambda h_pk=hist_pk: self.remove_history(h_pk)).pack(side='right', padx=5)

    def adjust_health(self, hist_pk):
        """Opens a new window to visually adjust the health for a history point."""
        HealthAdjustmentWindow(self, self.app, hist_pk)

    def remove_history(self, hist_pk):
        """Removes a history point after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this data point? This cannot be undone.", parent=self):
            self.db.delete_history_point(hist_pk)
            self.app.refresh_all_ui()

    def delete_object(self, obj_pk):
        """Deletes an entire object and all its history after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this entire object and all its history? This is irreversible.", parent=self):
            self.db.delete_object(obj_pk)
            self.app.refresh_all_ui()

    def rename_object(self, obj_pk, old_name):
        """Renames an object."""
        new_name = simpledialog.askstring("Rename Object", f"Enter new name for '{old_name}':", parent=self)
        if new_name and new_name.strip() and new_name.strip() != old_name:
            success, msg = self.db.rename_object(obj_pk, new_name.strip())
            if not success:
                messagebox.showerror("Error", msg, parent=self)
            self.app.refresh_all_ui()

    def set_object_image(self, obj_pk):
        """Opens a file dialog to set the representative image for an object."""
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")], parent=self)
        if not path: return
        
        dest_folder = self.app.image_folder
        filename = f"object_{obj_pk}{os.path.splitext(path)[1]}"
        dest_path = os.path.join(dest_folder, filename)
        shutil.copy(path, dest_path)
        
        self.db.set_object_image(obj_pk, dest_path)
        self.app.refresh_all_ui()

    def set_base_hp(self, obj_pk, current_hp):
        """Opens a dialog to set the base HP for an object."""
        new_hp = simpledialog.askinteger("Set Base HP", "Enter the total base HP for this object:", initialvalue=current_hp, parent=self)
        if new_hp is not None:
            self.db.set_object_base_hp(obj_pk, new_hp)
            self.app.refresh_all_ui()

class DataMigrationWindow(tk.Toplevel):
    """A window for manually entering historical data points."""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.db = app.db
        
        self.title("Manual Data Migration")
        self.transient(parent)
        self.grab_set()
        
        form_frame = ttk.Frame(self, padding=20)
        form_frame.pack(fill='both', expand=True)
        
        # --- UI Elements ---
        self.sietch_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.object_id_var = tk.StringVar()
        self.health_var = tk.StringVar()
        self.datetime_var = tk.StringVar()

        # Row 0: Sietch
        ttk.Label(form_frame, text="Sietch:").grid(row=0, column=0, sticky='w', pady=3)
        self.sietch_menu = ttk.Combobox(form_frame, textvariable=self.sietch_var, state="readonly")
        self.sietch_menu.grid(row=0, column=1, sticky='ew', pady=3)
        self.sietch_menu.bind("<<ComboboxSelected>>", self.update_location_dropdown)
        
        # Row 1: Location
        ttk.Label(form_frame, text="Location ID:").grid(row=1, column=0, sticky='w', pady=3)
        self.location_menu = ttk.Combobox(form_frame, textvariable=self.location_var, state="readonly")
        self.location_menu.grid(row=1, column=1, sticky='ew', pady=3)
        self.location_menu.bind("<<ComboboxSelected>>", self.update_object_dropdown)

        # Row 2: Object ID
        ttk.Label(form_frame, text="Object ID:").grid(row=2, column=0, sticky='w', pady=3)
        self.object_id_combo = ttk.Combobox(form_frame, textvariable=self.object_id_var)
        self.object_id_combo.grid(row=2, column=1, sticky='ew', pady=3)
        
        # Row 3: Health
        ttk.Label(form_frame, text="Health %:").grid(row=3, column=0, sticky='w', pady=3)
        ttk.Entry(form_frame, textvariable=self.health_var).grid(row=3, column=1, sticky='ew', pady=3)
        
        # Row 4: DateTime
        ttk.Label(form_frame, text="Date/Time:").grid(row=4, column=0, sticky='w', pady=3)
        ttk.Entry(form_frame, textvariable=self.datetime_var).grid(row=4, column=1, sticky='ew', pady=3)
        ttk.Label(form_frame, text="Format: MM-DD HH:MM AM/PM", style='Italic.TLabel').grid(row=5, column=1, sticky='w')

        # Row 6: Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=6, columnspan=2, pady=15)
        ttk.Button(button_frame, text="Save Entry", command=self.save_entry).pack(side='left')
        ttk.Button(button_frame, text="Close", command=self.destroy).pack(side='left', padx=10)
        
        # Initialize dropdowns
        self.sietch_menu['values'] = self.db.get_sietches()

    def update_location_dropdown(self, event=None):
        sietch = self.sietch_var.get()
        self.location_var.set("")
        self.object_id_var.set("")
        if not sietch:
            self.location_menu['values'] = []
            self.object_id_combo['values'] = []
        else:
            locations = self.db.get_locations_for_sietch(sietch)
            self.location_menu['values'] = locations
            
    def update_object_dropdown(self, event=None):
        sietch = self.sietch_var.get()
        location = self.location_var.get()
        self.object_id_var.set("")
        if not sietch or not location:
            self.object_id_combo['values'] = []
            return
        loc_pk = self.db.query("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, location)).fetchone()
        if loc_pk:
            objects = [obj[1] for obj in self.db.get_objects_for_location(loc_pk[0])]
            self.object_id_combo['values'] = objects
        else:
            self.object_id_combo['values'] = []

    def save_entry(self):
        """Validates and saves the manually entered data."""
        sietch = self.sietch_var.get()
        location = self.location_var.get()
        obj_id = self.object_id_var.get().strip()
        health_str = self.health_var.get().strip()
        datetime_str = self.datetime_var.get().strip()

        # --- Validation ---
        if not all([sietch, location, obj_id, health_str, datetime_str]):
            messagebox.showerror("Error", "All fields are required.", parent=self)
            return
        
        try:
            health_val = float(health_str)
        except ValueError:
            messagebox.showerror("Error", "Health must be a valid number.", parent=self)
            return
            
        try:
            # Step 1: Normalize the string for easier parsing
            norm_str = datetime_str.lower().replace(" ", "")

            # Step 2: Use regex to find the components in a flexible way
            # This pattern looks for M, D, H, M, and AM/PM with optional separators
            pattern = r"(\d{1,2})[-/]?(\d{1,2})[-/:\s]*(\d{1,2}):?(\d{2})\s*([ap]m?)"
            match = re.search(pattern, norm_str)

            # A second, more rigid pattern for cases with no separators like '09271215pm'
            if not match:
                pattern = r"(\d{2})(\d{2})(\d{1,2})(\d{2})([ap]m?)"
                match = re.search(pattern, norm_str)

            if not match:
                raise ValueError("Could not understand the date/time format.")

            month, day, hour, minute, ampm = match.groups()
            
            # Step 3: Reconstruct a standard string that strptime can reliably parse
            ampm_standard = 'PM' if 'p' in ampm else 'AM'
            standard_dt_str = f"{datetime.datetime.now().year}-{month}-{day} {hour}:{minute} {ampm_standard}"
            
            # Step 4: Parse the standardized string
            dt_obj = datetime.datetime.strptime(standard_dt_str, "%Y-%m-%d %I:%M %p")

        except (ValueError, AttributeError):
            messagebox.showerror("Error", "Invalid date/time format. Please use a format like 'MM-DD HH:MM AM/PM'.", parent=self)
            return

        # --- Database Operations ---
        try:
            # Ensure location and object exist
            self.db.add_location(sietch, location)
            loc_pk = self.db.query("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, location)).fetchone()[0]
            self.db.query("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (loc_pk, obj_id))
            self.db.commit()
            obj_pk = self.db.query("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_pk, obj_id)).fetchone()[0]

            # Save the manual history point
            success, msg = self.db.add_manual_history_point(obj_pk, dt_obj, health_val, "M/E")

            if success:
                messagebox.showinfo("Success", "Manual entry saved successfully.", parent=self)
                # Clear fields for next entry
                self.health_var.set("")
                self.datetime_var.set("")
                self.app.refresh_all_ui() # Refresh main UI to show new data
            else:
                messagebox.showerror("Database Error", msg, parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=self)

    def delete_object(self, obj_pk):
        """Deletes an entire object and all its history after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this entire object and all its history? This is irreversible.", parent=self):
            self.db.delete_object(obj_pk)
            self.app.refresh_all_ui()

    def rename_object(self, obj_pk, old_name):
        """Renames an object."""
        new_name = simpledialog.askstring("Rename Object", f"Enter new name for '{old_name}':", parent=self)
        if new_name and new_name.strip() and new_name.strip() != old_name:
            success, msg = self.db.rename_object(obj_pk, new_name.strip())
            if not success:
                messagebox.showerror("Error", msg, parent=self)
            self.app.refresh_all_ui()

    def set_object_image(self, obj_pk):
        """Opens a file dialog to set the representative image for an object."""
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")], parent=self)
        if not path: return
        
        dest_folder = self.app.image_folder
        filename = f"object_{obj_pk}{os.path.splitext(path)[1]}"
        dest_path = os.path.join(dest_folder, filename)
        shutil.copy(path, dest_path)
        
        self.db.set_object_image(obj_pk, dest_path)
        self.app.refresh_all_ui()

    def set_base_hp(self, obj_pk, current_hp):
        """Opens a dialog to set the base HP for an object."""
        new_hp = simpledialog.askinteger("Set Base HP", "Enter the total base HP for this object:", initialvalue=current_hp, parent=self)
        if new_hp is not None:
            self.db.set_object_base_hp(obj_pk, new_hp)
            self.app.refresh_all_ui()

class DecayGraph(tk.Canvas):
    """A canvas widget that draws a decay graph based on historical health data."""
    def __init__(self, parent, history_data, **kwargs):
        kwargs.setdefault('height', 60)
        kwargs.setdefault('bg', "#2d3748")
        kwargs.setdefault('highlightthickness', 0)
        super().__init__(parent, **kwargs)

        self.history_data = history_data
        self.bind("<Configure>", self.draw_graph)

    def draw_graph(self, event=None):
        self.delete("all")
        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()

        padding = {'top': 15, 'bottom': 20, 'left': 35, 'right': 10}
        graph_w = canvas_w - padding['left'] - padding['right']
        graph_h = canvas_h - padding['top'] - padding['bottom']

        if len(self.history_data) < 2:
            self.create_text(canvas_w / 2, canvas_h / 2, text="Not enough data to calculate decay.", fill='white', anchor='center')
            return

        points = sorted([p for p in [(ts, float(h)) for _, ts, h, _ in self.history_data if h != 'wrecked' and str(h).replace('.', '', 1).isdigit()] if isinstance(p[1], float)], key=lambda p: p[0])

        if len(points) < 2:
            self.create_text(canvas_w / 2, canvas_h / 2, text="Not enough valid data for decay.", fill='white', anchor='center')
            return

        # --- Dynamic Scaling Logic ---
        n, sum_x, sum_y, sum_xy, sum_xx = len(points), sum(p[0] for p in points), sum(p[1] for p in points), sum(p[0] * p[1] for p in points), sum(p[0]**2 for p in points)
        denominator = (n * sum_xx - sum_x**2)
        m = (n * sum_xy - sum_x * sum_y) / denominator if denominator != 0 else 0
        b = (sum_y - m * sum_x) / n if denominator != 0 else 0
        
        wreck_ts = -b / m if m < 0 else points[-1][0]

        first_ts = points[0][0]
        last_ts = max(points[-1][0], wreck_ts)
        time_range = (last_ts - first_ts) if (last_ts > first_ts) else 1

        max_health = max(p[1] for p in points)
        y_max = 100.0
        if max_health < 80:
            y_max = min(100.0, (max_health // 10 + 2) * 10.0)
        y_min = 0.0
        health_range = y_max - y_min if y_max > y_min else 1

        # --- Draw Axes and Labels ---
        self.create_line(padding['left'], padding['top'], padding['left'], canvas_h - padding['bottom'], fill='gray')
        self.create_line(padding['left'], canvas_h - padding['bottom'], canvas_w - padding['right'], canvas_h - padding['bottom'], fill='gray')
        
        self.create_text(padding['left'] - 5, padding['top'], text=f"{y_max:.0f}%", fill='white', anchor='e', font=('Arial', 7))
        self.create_text(padding['left'] - 5, canvas_h - padding['bottom'], text=f"{y_min:.0f}%", fill='white', anchor='e', font=('Arial', 7))
        
        self.create_text(padding['left'], canvas_h - padding['bottom'] + 5, text=datetime.datetime.fromtimestamp(first_ts).strftime('%b %d'), fill='white', anchor='n', font=('Arial', 7))
        self.create_text(canvas_w - padding['right'], canvas_h - padding['bottom'] + 5, text=datetime.datetime.fromtimestamp(last_ts).strftime('%b %d'), fill='white', anchor='n', font=('Arial', 7))

        # --- Draw Data ---
        def to_coords(p_ts, p_health):
            x = padding['left'] + ((p_ts - first_ts) / time_range) * graph_w
            y = (canvas_h - padding['bottom']) - ((p_health - y_min) / health_range) * graph_h
            return x, y

        coords = [to_coords(p[0], p[1]) for p in points]
        if len(coords) > 1:
            self.create_line(coords, fill="#60a5fa", width=2)

        if m < 0:
            start_y_trend = m * first_ts + b
            start_x_trend_ts = first_ts
            if start_y_trend > y_max:
                start_x_trend_ts = (y_max - b) / m
                start_y_trend = y_max

            start_coords = to_coords(start_x_trend_ts, start_y_trend)
            end_coords = to_coords(wreck_ts, 0)
            
            self.create_line(start_coords, end_coords, fill="#ef4444", dash=(4, 2))
            wreck_dt = datetime.datetime.fromtimestamp(wreck_ts)
            self.create_text(canvas_w - padding['right'], padding['top'], text=f"Est. Wreck: {wreck_dt.strftime('%b %d, %H:%M')}", anchor='ne', fill='white', font=('Arial', 8))

    def delete_object(self, obj_pk):
        """Deletes an entire object and all its history after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this entire object and all its history? This is irreversible.", parent=self):
            self.db.delete_object(obj_pk)
            self.app.refresh_all_ui()

    def rename_object(self, obj_pk, old_name):
        """Renames an object."""
        new_name = simpledialog.askstring("Rename Object", f"Enter new name for '{old_name}':", parent=self)
        if new_name and new_name.strip() and new_name.strip() != old_name:
            success, msg = self.db.rename_object(obj_pk, new_name.strip())
            if not success:
                messagebox.showerror("Error", msg, parent=self)
            self.app.refresh_all_ui()

    def set_object_image(self, obj_pk):
        """Opens a file dialog to set the representative image for an object."""
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")], parent=self)
        if not path: return
        
        # Copy the image to a local folder to ensure it's not lost
        dest_folder = self.app.image_folder
        filename = f"object_{obj_pk}{os.path.splitext(path)[1]}"
        dest_path = os.path.join(dest_folder, filename)
        shutil.copy(path, dest_path)
        
        self.db.set_object_image(obj_pk, dest_path)
        self.app.refresh_all_ui()

    def set_base_hp(self, obj_pk, current_hp):
        """Opens a dialog to set the base HP for an object."""
        new_hp = simpledialog.askinteger("Set Base HP", "Enter the total base HP for this object:", initialvalue=current_hp, parent=self)
        if new_hp is not None:
            self.db.set_object_base_hp(obj_pk, new_hp)
            self.app.refresh_all_ui()

class HealthAdjustmentWindow(tk.Toplevel):
    """A window for visually adjusting the health percentage on a screenshot."""
    def __init__(self, parent, app, history_pk):
        super().__init__(parent)
        self.app = app
        self.db = app.db
        self.history_pk = history_pk
        self.new_health_percent = None
        self.zoom_factor = 4.0  # Zoom by 400%

        self.title("Adjust Health")
        self.transient(parent)
        self.grab_set()

        history_data = self.db.query("SELECT screenshot_path, health_percent FROM history WHERE id=?", (self.history_pk,)).fetchone()
        if not history_data or not history_data[0] or not os.path.exists(history_data[0]):
            messagebox.showerror("Error", "Screenshot for this record not found.", parent=self)
            self.destroy()
            return
            
        self.image_path = history_data[0]
        self.original_health = history_data[1]
        original_image_cv = cv2.imread(self.image_path)
        
        # Resize image for zoom
        self.image_cv = cv2.resize(original_image_cv, (0,0), fx=self.zoom_factor, fy=self.zoom_factor, interpolation=cv2.INTER_NEAREST)
        
        self.canvas = tk.Canvas(self, width=self.image_cv.shape[1], height=self.image_cv.shape[0], highlightthickness=0)
        self.canvas.pack()
        
        self.photo_image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(self.image_cv, cv2.COLOR_BGR2RGB)))
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo_image)
        
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<Button-1>", self.on_mouse_drag)

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill='x', padx=10, pady=10)
        
        self.health_label_var = tk.StringVar(value=f"Current: {self.original_health}")
        ttk.Label(bottom_frame, textvariable=self.health_label_var).pack(side='left')
        
        ttk.Button(bottom_frame, text="Save", command=self.save_and_close).pack(side='right')
        ttk.Button(bottom_frame, text="Cancel", command=self.destroy).pack(side='right', padx=5)
        
        self.draw_overlay()

    def draw_overlay(self, event=None):
        self.canvas.delete("overlay")
        
        h, w = self.image_cv.shape[:2]
        center_x, center_y = w / 2, h / 2
        
        health_to_draw = self.new_health_percent if self.new_health_percent is not None else (float(self.original_health) if self.original_health != 'wrecked' else 0)

        # Draw the health arc
        if health_to_draw is not None and health_to_draw > 0:
            start_angle = 90 # 12 o'clock
            extent_angle = - (health_to_draw / 100.0) * 360.0
            
            for radius in HealthAnalyzer.SAMPLE_RADII:
                scaled_radius = radius * self.zoom_factor
                bbox = (center_x - scaled_radius, center_y - scaled_radius, center_x + scaled_radius, center_y + scaled_radius)
                self.canvas.create_arc(bbox, start=start_angle, extent=extent_angle, style=tk.ARC, outline="cyan", width=1, tags="overlay")

        scaled_max_radius = HealthAnalyzer.SAMPLE_RADII[-1] * self.zoom_factor
        self.canvas.create_line(center_x, center_y, center_x, center_y - scaled_max_radius, fill="green", width=2, tags="overlay")
        
        if health_to_draw is not None:
            end_angle_deg = (health_to_draw / 100.0) * 360.0
            end_angle_rad = math.radians(end_angle_deg)
            end_x = center_x + scaled_max_radius * math.sin(end_angle_rad)
            end_y = center_y - scaled_max_radius * math.cos(end_angle_rad)
            self.canvas.create_line(center_x, center_y, end_x, end_y, fill="red", width=2, tags="overlay")

    def on_mouse_drag(self, event):
        h, w = self.image_cv.shape[:2]
        center_x, center_y = w / 2, h / 2
        
        dx = event.x - center_x
        dy = center_y - event.y
        
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        
        final_angle = (90 - angle_deg) % 360
        
        self.new_health_percent = (final_angle / 360.0) * 100
        self.health_label_var.set(f"New: {self.new_health_percent:.1f}%")
        self.draw_overlay()

    def save_and_close(self):
        """Saves the new health value to the database and closes the window."""
        if self.new_health_percent is not None:
            self.db.update_history_health(self.history_pk, f"{self.new_health_percent:.1f}")
            self.app.refresh_all_ui()
        self.destroy()
            
    def remove_history(self, hist_pk):
        """Removes a history point after confirmation."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this data point? This cannot be undone.", parent=self):
            self.db.delete_history_point(hist_pk)
            self.app.refresh_all_ui()