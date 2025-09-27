import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import os
import queue
import shutil
import datetime
import traceback
import keyboard
import cv2

from database import DatabaseManager
from hotkey_listener import start_hotkey_listener
from gui_components import ScrollableFrame, MapFrame, SietchManagerWindow, SietchOverviewFrame

class VultureTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vulture Tracker v3.2 (Multi-File)")
        self.root.configure(bg="#111827")
        self.root.state('zoomed')

        self.image_folder = "vulture_tracker_images_v3"
        os.makedirs(self.image_folder, exist_ok=True)
        self.db = DatabaseManager("vulture_tracker_v3.db")

        self.photo_references = {}
        self.last_capture_data = None
        self.capture_queue = queue.Queue()

        self.setup_styles()
        self.create_widgets()
        self.load_recent_base_hp() # Load recent values on startup
        self.refresh_all_ui()
        
        start_hotkey_listener(self.capture_queue, self.log_error)
        self.check_capture_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        """Defines the color scheme and styles for the application's widgets."""
        self.bg_color = "#1f2937"  # Cool Gray 800
        self.fg_color = "#f3f4f6"  # Cool Gray 100 (Eggshell)
        self.accent_color = "#374151" # Cool Gray 700

        style = ttk.Style()
        style.theme_use('clam')

        # General widget styling
        style.configure('.', background=self.bg_color, foreground=self.fg_color)
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color, padding=3)
        style.configure('TButton', background=self.accent_color, foreground=self.fg_color)
        style.map('TButton', background=[('active', '#4b5563')]) # Cool Gray 600

        # Special styling for overview components
        style.configure('TLabelFrame', background=self.bg_color)
        style.configure('TLabelFrame.Label', background=self.bg_color, foreground=self.fg_color, font=('Arial', 12, 'bold'))
        style.configure('Location.TFrame', background=self.accent_color)
        style.configure('Object.TFrame', background=self.bg_color)
        style.configure('Italic.TLabel', font=('Arial', 9, 'italic'), foreground="#9ca3af") # Cool Gray 400

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Main Map Image...", command=self.set_main_map_image)
        file_menu.add_command(label="Manage Sietches...", command=self.open_sietch_manager) # New Menu Item
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Main layout frames
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill='x', pady=10, padx=10)

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill='both', expand=True, padx=10, pady=(0,10))

        # Configure resizing behavior
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # --- Top Frame Content ---
        map_frame_container = ttk.Frame(top_frame, width=800)
        map_frame_container.pack(side='left', fill='x', expand=True, padx=(0, 10))

        self.map_frame = MapFrame(map_frame_container, self)
        self.map_frame.pack(fill='x')

        priority_list_container = ttk.Frame(top_frame, width=400)
        priority_list_container.pack(side='right', fill='y')

        ttk.Label(priority_list_container, text="Priority Watch List", font=('Arial', 14, 'bold')).pack(anchor='n')
        self.priority_list_frame = ttk.Frame(priority_list_container, padding=5)
        self.priority_list_frame.pack(fill='both', expand=True)

        # --- Bottom Frame Content (Sietch Overview) ---
        self.overview_frame = SietchOverviewFrame(bottom_frame, self)
        self.overview_frame.pack(fill='both', expand=True)

        # --- Data Entry Form ---
        # We will keep the capture form in a less prominent place for now
        # Let's put it in a small frame in the priority list area
        form_frame = ttk.Frame(priority_list_container, padding=10)
        form_frame.pack(fill='x', pady=(10,0), side='bottom')
        ttk.Label(form_frame, text="Captured Data Point").grid(row=0, columnspan=2, pady=5, sticky='w')
        self.sietch_var, self.location_var, self.object_id_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(form_frame, text="Sietch:").grid(row=1, column=0, sticky='w', pady=2)
        self.sietch_menu = ttk.Combobox(form_frame, textvariable=self.sietch_var, state="readonly", width=15)
        self.sietch_menu.grid(row=1, column=1, sticky='ew')
        self.sietch_menu.bind("<<ComboboxSelected>>", self.update_location_dropdown)
        ttk.Label(form_frame, text="Location ID:").grid(row=2, column=0, sticky='w', pady=2)
        self.location_menu = ttk.Combobox(form_frame, textvariable=self.location_var, state="readonly", width=15)
        self.location_menu.grid(row=2, column=1, sticky='ew')
        ttk.Label(form_frame, text="Object ID:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(form_frame, textvariable=self.object_id_var).grid(row=3, column=1, sticky='ew')

        ttk.Label(form_frame, text="Base HP (Opt.):").grid(row=4, column=0, sticky='w', pady=2)
        self.base_hp_var = tk.StringVar()
        self.base_hp_combo = ttk.Combobox(form_frame, textvariable=self.base_hp_var)
        self.base_hp_combo.grid(row=4, column=1, sticky='ew')

        self.capture_preview_label = ttk.Label(form_frame, text="Press Ctrl+Shift+H in-game...")
        self.capture_preview_label.grid(row=5, columnspan=2, pady=10)
        self.save_button = ttk.Button(form_frame, text="Save Captured Data", command=self.save_captured_data, state="disabled")
        self.save_button.grid(row=6, columnspan=2, sticky='ew', pady=5)

    def open_sietch_manager(self):
        """Opens the new Toplevel window for managing sietches."""
        SietchManagerWindow(self.root, self)

    def check_capture_queue(self):
        """Checks the queue for new data from the hotkey listener."""
        try:
            capture_data = self.capture_queue.get_nowait()
            if "error" in capture_data:
                self.log_error(source="Hotkey Listener", error_data=capture_data["error"])
            else:
                # This is the new analysis_result dictionary
                self.last_capture_data = capture_data
                self.populate_form_with_capture()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_capture_queue)

    def populate_form_with_capture(self):
        """Updates the UI form with the data from the latest capture."""
        data = self.last_capture_data
        health = data["health_percent"]
        ts = data["timestamp"].strftime("%Y-%m-%d %I:%M:%S %p")

        # Display the 50x50 center crop as the preview
        crop_image_cv = data.get("center_crop")
        if crop_image_cv is not None:
            crop_pil = Image.fromarray(cv2.cvtColor(crop_image_cv, cv2.COLOR_BGR2RGB))
            crop_pil.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(crop_pil)
            self.photo_references['capture'] = photo
            self.capture_preview_label.config(image=photo, text=f"Health: {health}\n{ts}", compound='top')
        else:
            self.capture_preview_label.config(image=None, text=f"Health: {health}\n{ts}")

        self.save_button.config(state="normal")
        print(f"Captured data ready in form: Health {health}")

    def save_captured_data(self):
        """Saves the captured data point and updates the Base HP if provided."""
        sietch = self.sietch_var.get()
        location_id = self.location_var.get()
        object_id = self.object_id_var.get().strip()
        base_hp_str = self.base_hp_var.get().strip()

        if not all([sietch, location_id, object_id]):
            messagebox.showerror("Error", "Sietch, Location, and Object ID are required.")
            return

        if self.last_capture_data is None:
            messagebox.showerror("Error", "No captured data to save.")
            return

        self.db.add_location(sietch, location_id)
        success, message = self.db.save_data_point(sietch, location_id, object_id, self.last_capture_data)

        if success:
            if base_hp_str.isdigit():
                obj_pk = self.db.query("SELECT id FROM objects WHERE location_fk=(SELECT id FROM locations WHERE sietch_name=? AND location_id=?) AND object_id=?", (sietch, location_id, object_id)).fetchone()[0]
                self.db.set_object_base_hp(obj_pk, int(base_hp_str))
                self.update_recent_base_hp(base_hp_str)

            messagebox.showinfo("Success", "Data point saved successfully!")
            self.last_capture_data = None
            self.save_button.config(state="disabled")
            self.object_id_var.set("")
            self.base_hp_var.set("")
            self.refresh_all_ui()
        else:
            messagebox.showerror("Database Error", message)

    def load_recent_base_hp(self):
        """Loads the recent Base HP values into the combobox."""
        recent_hp_str = self.db.get_config("recent_base_hp")
        if recent_hp_str:
            self.base_hp_combo['values'] = recent_hp_str.split(',')

    def update_recent_base_hp(self, new_hp):
        """Adds a new HP value to the recent list, keeping it at 5 unique entries."""
        current_values = self.base_hp_combo['values']
        if isinstance(current_values, str):
            current_values = list(current_values.split(','))

        if new_hp in current_values:
            current_values.remove(new_hp)

        updated_values = [new_hp] + current_values
        updated_values = updated_values[:5] # Keep only the top 5

        self.db.set_config("recent_base_hp", ",".join(updated_values))
        self.base_hp_combo['values'] = updated_values
    
    def refresh_priority_list(self):
        """Fetches and displays the top 10 most urgent items."""
        for widget in self.priority_list_frame.winfo_children():
            widget.destroy()

        try:
            priority_items = self.db.get_priority_watch_list()
            if not priority_items:
                ttk.Label(self.priority_list_frame, text="No items with calculable decay.").pack()
                return

            for item in priority_items:
                wreck_time = datetime.datetime.fromtimestamp(item['estimated_wreck_time'])
                time_diff = wreck_time - datetime.datetime.now()

                if time_diff.total_seconds() < 0:
                    time_str = "Now"
                else:
                    days, remainder = divmod(time_diff.total_seconds(), 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_str = ""
                    if days > 0: time_str += f"{int(days)}d "
                    if hours > 0: time_str += f"{int(hours)}h "
                    time_str += f"{int(minutes)}m"

                entry_text = f"{item['sietch']} | {item['location']} | {item['object']}\n"
                entry_text += f"  > Wrecks in: {time_str} ({item['current_health']:.1f}%)"

                ttk.Label(self.priority_list_frame, text=entry_text, anchor='w').pack(fill='x', pady=2)

        except Exception as e:
            self.log_error("Priority List Refresh", e)
            ttk.Label(self.priority_list_frame, text="Error loading priority list.").pack()

    def refresh_all_ui(self):
        """Refreshes all visible UI components to reflect database changes."""
        self.refresh_sietch_list()
        self.update_location_dropdown()
        self.refresh_priority_list()
        if hasattr(self, 'map_frame'):
            self.map_frame.load_pins()
        if hasattr(self, 'overview_frame'):
            self.overview_frame.refresh_overview()
        
    def refresh_sietch_list(self):
        self.sietch_menu['values'] = self.db.get_sietches()
        if hasattr(self, 'map_frame'): self.map_frame.update_filter_options()
    
    def update_location_dropdown(self, event=None):
        self.location_menu['values'] = [""] + self.db.get_locations_for_sietch(self.sietch_var.get()); self.location_var.set("")
        
    def set_main_map_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")]);
        if not path: return
        dest_path = os.path.join(self.image_folder, "main_map" + os.path.splitext(path)[1])
        shutil.copy(path, dest_path)
        self.db.set_config("main_map_path", dest_path)
        self.map_frame.load_map()

    def on_closing(self):
        self.db.close(); keyboard.send('ctrl+shift+q'); self.root.destroy()

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