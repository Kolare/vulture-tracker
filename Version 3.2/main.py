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
from gui_components import ScrollableFrame, MapFrame, SietchManagerWindow

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
        self.refresh_all_ui()
        
        start_hotkey_listener(self.capture_queue, self.log_error)
        self.check_capture_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        # Full styling would be implemented here
        pass

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Main Map Image...", command=self.set_main_map_image)
        file_menu.add_command(label="Manage Sietches...", command=self.open_sietch_manager) # New Menu Item
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
        
        # Sietch Management Frame is now removed from here.
        
        self.map_frame = MapFrame(self.right_content_frame, self)
        self.map_frame.pack(fill='x', anchor='n', pady=10)
        self.overview_container = ttk.Frame(self.right_content_frame, padding=10)
        self.overview_container.pack(fill='both', expand=True, anchor='n')
        ttk.Label(self.overview_container, text="Sietch Overview (To be built)", font=('Arial', 14, 'bold')).pack(anchor='w')

    def open_sietch_manager(self):
        """Opens the new Toplevel window for managing sietches."""
        SietchManagerWindow(self.root, self)

    # (Other methods like check_capture_queue, save_captured_data, etc. remain largely the same)
    def check_capture_queue(self):
        try:
            capture = self.capture_queue.get_nowait()
            if "error" in capture: self.log_error(source="Hotkey Listener", error_data=capture["error"])
            else: self.last_capture_data = capture; self.populate_form_with_capture()
        except queue.Empty: pass
        finally: self.root.after(100, self.check_capture_queue)

    def populate_form_with_capture(self):
        data = self.last_capture_data; health = data["health"]; ts = data["timestamp"].strftime("%Y-%m-%d %I:%M:%S %p")
        roi_pil = Image.fromarray(cv2.cvtColor(data["roi_image"], cv2.COLOR_BGR2RGB)); roi_pil.thumbnail((100, 100))
        photo = ImageTk.PhotoImage(roi_pil); self.photo_references['capture'] = photo
        self.capture_preview_label.config(image=photo, text=f"Health: {health:.2f}%\n{ts}", compound='top')
        self.save_button.config(state="normal"); print(f"Captured data ready in form: Health {health:.2f}%")

    def save_captured_data(self):
        data_to_save = {"sietch": self.sietch_var.get(), "location_id": self.location_var.get(), "object_id": self.object_id_var.get().strip(), "health": self.last_capture_data["health"], "timestamp": self.last_capture_data["timestamp"], "roi_image": self.last_capture_data["roi_image"]}
        if not all([data_to_save["sietch"], data_to_save["location_id"], data_to_save["object_id"]]): messagebox.showerror("Error", "Sietch, Location, and Object ID are required."); return
        self.db.add_location(data_to_save["sietch"], data_to_save["location_id"])
        success, message = self.db.save_data_point(data_to_save, self.image_folder)
        if success: messagebox.showinfo("Success", "Data point saved successfully!"); self.last_capture_data = None; self.save_button.config(state="disabled"); self.object_id_var.set(""); self.refresh_all_ui()
        else: messagebox.showerror("Database Error", message)
    
    def refresh_all_ui(self):
        self.refresh_sietch_list()
        self.update_location_dropdown()
        if hasattr(self, 'map_frame'): self.map_frame.load_pins()
        
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