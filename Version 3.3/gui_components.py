import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from PIL import Image, ImageTk
import os

class ScrollableFrame(ttk.Frame):
    # (This class remains unchanged)
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg="#1f2937", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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

        # Bind events
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_move)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom) # For Linux
        self.canvas.bind("<Button-5>", self.on_zoom) # For Linux

        self.load_map()

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
                self.canvas.create_oval(canvas_x-5, canvas_y-5, canvas_x+5, canvas_y+5, fill="red", outline="white", tags="pin")
                self.canvas.create_text(canvas_x, canvas_y - 10, text=loc_id, fill="white", tags="pin")

    def on_pan_start(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_pan_move(self, event):
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.view_x -= dx / self.zoom_level
        self.view_y -= dy / self.zoom_level
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.redraw_canvas()

    def on_zoom(self, event):
        scale_factor = 1.2
        if (event.delta > 0 or event.num == 4): # Zoom in
            new_zoom = self.zoom_level * scale_factor
        elif (event.delta < 0 or event.num == 5): # Zoom out
            new_zoom = self.zoom_level / scale_factor
        else:
            return

        # Get mouse position relative to the canvas
        mouse_x, mouse_y = event.x, event.y

        # Get the point on the original image under the mouse
        image_x = self.view_x + mouse_x / self.zoom_level
        image_y = self.view_y + mouse_y / self.zoom_level

        self.zoom_level = new_zoom

        # Recalculate view to keep the point under the mouse stationary
        self.view_x = image_x - mouse_x / self.zoom_level
        self.view_y = image_y - mouse_y / self.zoom_level

        self.redraw_canvas()

    def update_filter_options(self):
        sietches = ["All"] + self.app.db.get_sietches()
        self.sietch_filter_menu['values'] = sietches