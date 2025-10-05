import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta

class VultureTrackerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vulture Tracker - UI Mockup (Final)")
        self.geometry("1200x850")
        self.configure(bg="#2E2E2E")

        # --- Style Configuration ---
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#2E2E2E", foreground="#D3D3D3",
                             fieldbackground="#3C3C3C", selectbackground="#4A4A4A",
                             selectforeground="#FFFFFF")
        self.style.map("TButton", background=[('active', '#5A5A5A')], foreground=[('active', '#FFFFFF')])
        self.style.configure("TLabel", background="#2E2E2E", foreground="#D3D3D3")
        self.style.configure("TFrame", background="#2E2E2E")
        self.style.configure("Treeview", background="#3C3C3C",
                             foreground="#D3D3D3", fieldbackground="#3C3C3C", rowheight=25)
        self.style.map("Treeview", background=[('selected', '#5A5A5A')])
        self.style.configure("Treeview.Heading", background="#4A4A4A", foreground="#FFFFFF")
        self.style.configure("Vertical.TScrollbar", background="#4A4A4A", troughcolor="#2E2E2E")

        # Styles for mockup colors
        self.style.configure("Green.TFrame", background="green")
        self.style.configure("DarkBlue.TFrame", background="dark blue")
        self.style.configure("Cyan.TFrame", background="cyan")
        self.style.configure("Red.TFrame", background="red")
        self.style.configure("Yellow.TFrame", background="yellow")
        self.style.configure("Pink.TFrame", background="pink")
        self.style.configure("Orange.TFrame", background="orange")
        self.style.configure("White.TFrame", background="white")

        self._create_layout()

    def _create_layout(self):
        # --- Main Window Grid Configuration ---
        # Configure the main window to have two equal-width columns
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Column ---
        left_column_frame = ttk.Frame(self)
        left_column_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_column_frame.grid_rowconfigure(0, weight=3) # 75% height for map
        left_column_frame.grid_rowconfigure(1, weight=1) # 25% height for bottom
        left_column_frame.grid_columnconfigure(0, weight=1)

        self.map_pane = ttk.Frame(left_column_frame, relief=tk.RIDGE, borderwidth=2, style="Green.TFrame")
        self.map_pane.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.map_pane, text="Map Pane", background="green", foreground="white").pack(expand=True)

        bottom_left_frame = ttk.Frame(left_column_frame)
        bottom_left_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        bottom_left_frame.grid_columnconfigure(0, weight=2) # Wider capture panel
        bottom_left_frame.grid_columnconfigure(1, weight=1) # Narrower debug panel
        bottom_left_frame.grid_rowconfigure(0, weight=1)

        self.data_capture_frame = ttk.Frame(bottom_left_frame, relief=tk.GROOVE, borderwidth=1, style="DarkBlue.TFrame")
        self.data_capture_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.data_capture_frame, text="Captured Data Point Dialogue", background="dark blue", foreground="white").pack(pady=5, anchor="w", padx=5)
        ttk.Label(self.data_capture_frame, text="Object: [Name]", background="dark blue", foreground="white").pack(anchor="w", padx=5)
        ttk.Label(self.data_capture_frame, text="Health: [XX%]", background="dark blue", foreground="white").pack(anchor="w", padx=5)
        ttk.Label(self.data_capture_frame, text="Time: [DateTime]", background="dark blue", foreground="white").pack(anchor="w", padx=5)
        screenshot_placeholder = tk.Frame(self.data_capture_frame, width=52, height=52, bg="black", relief=tk.SUNKEN, borderwidth=1)
        screenshot_placeholder.pack(pady=10, padx=5)
        ttk.Label(screenshot_placeholder, text="50x50", background="black", foreground="grey").pack(expand=True)

        self.debug_panel = ttk.Frame(bottom_left_frame, relief=tk.GROOVE, borderwidth=1, style="Cyan.TFrame")
        self.debug_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.debug_panel, text="Debugging Panel", background="cyan", foreground="black").pack(pady=5)
        self.debug_text = tk.Text(self.debug_panel, height=5, state='disabled', bg="#3C3C3C", fg="#00FF00", bd=0)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._log_debug_message("System started...")

        # --- Right Column ---
        right_column_frame = ttk.Frame(self)
        right_column_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_column_frame.grid_rowconfigure(0, weight=1) # Equal height
        right_column_frame.grid_rowconfigure(1, weight=1) # Equal height
        right_column_frame.grid_columnconfigure(0, weight=1)

        top_right_frame = ttk.Frame(right_column_frame)
        top_right_frame.grid(row=0, column=0, sticky="nsew")
        top_right_frame.grid_rowconfigure(0, weight=1) # Priority panel
        top_right_frame.grid_rowconfigure(1, weight=2) # Nested table (taller)
        top_right_frame.grid_columnconfigure(0, weight=1)

        self.pink_padding_frame = ttk.Frame(right_column_frame, relief=tk.RIDGE, borderwidth=2, style="Pink.TFrame")
        self.pink_padding_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.pink_padding_frame.grid_rowconfigure(0, weight=1) # Equal height for orange
        self.pink_padding_frame.grid_rowconfigure(1, weight=1) # Equal height for white
        self.pink_padding_frame.grid_columnconfigure(0, weight=1)

        self.priority_watch_frame = ttk.Frame(top_right_frame, relief=tk.RIDGE, borderwidth=2, style="Red.TFrame")
        self.priority_watch_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.priority_watch_frame, text="Priority Watch Panel", background="red", foreground="white").pack(pady=5)
        self._create_priority_table(self.priority_watch_frame)

        self.nested_table_frame = ttk.Frame(top_right_frame, relief=tk.RIDGE, borderwidth=2, style="Yellow.TFrame")
        self.nested_table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.nested_table_frame, text="Nested Sietch/Location/Object List", background="yellow", foreground="black").pack(pady=5)
        self._create_nested_treeview(self.nested_table_frame)

        # --- Bottom Right Layout (inside Pink) ---
        self.graph_frame = ttk.Frame(self.pink_padding_frame, relief=tk.RIDGE, borderwidth=2, style="Orange.TFrame")
        self.graph_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.graph_frame, text="Decay Graph", background="orange", foreground="white").pack(pady=5)
        self._create_decay_graph(self.graph_frame)

        self.history_table_frame = ttk.Frame(self.pink_padding_frame, relief=tk.RIDGE, borderwidth=2, style="White.TFrame")
        self.history_table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Label(self.history_table_frame, text="Visual History Table", background="white", foreground="black").pack(pady=5)
        self._create_history_table(self.history_table_frame)


    def _log_debug_message(self, message):
        self.debug_text.config(state='normal')
        self.debug_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.debug_text.see(tk.END)
        self.debug_text.config(state='disabled')

    def _create_nested_treeview(self, parent):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        tree = ttk.Treeview(tree_frame, columns=("Details", "Status"), show="headings")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.heading("Details", text="Sietch / Location / Object")
        tree.heading("Status", text="Status")
        tree.column("Status", width=120, anchor=tk.CENTER)
        sietches = {"Sietch Prime (2)": {"Location 1 ✔️": {"🔴 Object A": "10% | 2025-10-01 10:00","🟢 Object B": "80% | 2025-10-01 11:30"},"Location 2 ❌": {"🟡 Object C": "35% | 2025-09-30 23:00"}},"Sietch Echo (1)": {"Location Z ✔️": {"🔴 Object X": "5% | 2025-10-01 09:00"}}}
        for sietch_name, locations in sietches.items():
            sietch_id = tree.insert("", tk.END, text=sietch_name, values=(sietch_name, ""), open=False)
            for loc_name, objects in locations.items():
                loc_id = tree.insert(sietch_id, tk.END, text=loc_name, values=(f"  {loc_name}", ""), open=False)
                for obj_name, obj_status in objects.items():
                    tree.insert(loc_id, tk.END, text=obj_name, values=(f"    {obj_name}", obj_status))
        tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.object_tree = tree

    def _on_tree_select(self, event):
        tree = event.widget
        selected_item = tree.focus()
        if not selected_item: return

        # Accordion logic
        parent = tree.parent(selected_item)
        for sibling in tree.get_children(parent):
            if sibling != selected_item:
                tree.item(sibling, open=False)
        tree.item(selected_item, open=not tree.item(selected_item, 'open'))

        if tree.parent(selected_item) and tree.parent(tree.parent(selected_item)):
            object_name_full = tree.item(selected_item, "values")[0].strip()
            object_name = object_name_full.split(" ", 1)[1]
            self._log_debug_message(f"Selected Object: {object_name}")
            self._update_decay_graph(object_name)
            self._update_history_table(object_name)

    def _create_history_table(self, parent):
        history_frame = ttk.Frame(parent)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_tree = ttk.Treeview(history_frame, columns=("Screenshot", "DateTime", "Health"), show="headings", height=5)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.heading("Screenshot", text="Screenshot")
        self.history_tree.heading("DateTime", text="Date/Time")
        self.history_tree.heading("Health", text="Health %")
        self.history_tree.column("Screenshot", width=100, anchor=tk.CENTER)
        self.history_tree.column("DateTime", width=150, anchor=tk.CENTER)
        self.history_tree.column("Health", width=70, anchor=tk.CENTER)
        self.history_tree.insert("", tk.END, values=("(Click object)", "(Click object)", "(Click object)"))

    def _create_priority_table(self, parent):
        tree = ttk.Treeview(parent, columns=("Sietch", "Loc", "Obj", "Health", "DSC_W", "DSC_M", "DSC_L", "Wrecked_Time"), show="headings", height=5)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Set headings
        tree.heading("Sietch", text="Sietch")
        tree.heading("Loc", text="Location")
        tree.heading("Obj", text="Object")
        tree.heading("Health", text="Health")
        tree.heading("DSC_W", text="DSC:W")
        tree.heading("DSC_M", text="DSC:M")
        tree.heading("DSC_L", text="DSC:L")
        tree.heading("Wrecked_Time", text="Wrecked")

        # CHANGE: Reduced column widths to prevent layout squishing
        tree.column("Sietch", width=60)
        tree.column("Loc", width=80)
        tree.column("Obj", width=80)
        tree.column("Health", width=50, anchor=tk.CENTER)
        tree.column("DSC_W", width=80)
        tree.column("DSC_M", width=80)
        tree.column("DSC_L", width=80)
        tree.column("Wrecked_Time", width=70)

        now = datetime.now()
        data = [("Alpha", "Loc A1", "Vulture-001", "15%", (now + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M'), ""),("Beta", "Loc B2", "Vulture-005", "8%", (now - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(hours=4)).strftime('%Y-%m-%d %H:%M'), "00:03:15"),("Gamma", "Loc G3", "Vulture-010", "22%", (now + timedelta(hours=10)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'), (now + timedelta(days=2)).strftime('%Y-%m-%d %H:%M'), ""),("Delta", "Loc D4", "Vulture-012", "1%", (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M'), (now - timedelta(days=1, hours=-4)).strftime('%Y-%m-%d %H:%M'), (now - timedelta(days=1, hours=-8)).strftime('%Y-%m-%d %H:%M'), "01:05:20")]

        def sort_key(item):
            wrecked_time_str = item[7]
            if wrecked_time_str:
                parts = list(map(int, wrecked_time_str.split(':')))
                wrecked_delta = timedelta(days=parts[0], hours=parts[1], minutes=parts[2])
                return (0, now - wrecked_delta)
            else:
                dsc_w_str = item[4]
                try:
                    dsc_w_time = datetime.strptime(dsc_w_str, '%Y-%m-%d %H:%M')
                    return (1, dsc_w_time)
                except ValueError:
                    return (2, now)

        data.sort(key=sort_key)
        for item in data: tree.insert("", tk.END, values=item)

    def _create_decay_graph(self, parent):
        self.fig, self.ax = plt.subplots(figsize=(5, 3), facecolor="#2E2E2E")
        self.fig.patch.set_facecolor("#2E2E2E")
        self.ax.set_facecolor("#3C3C3C")
        self.ax.tick_params(axis='x', colors='#D3D3D3'); self.ax.tick_params(axis='y', colors='#D3D3D3')
        self.ax.yaxis.label.set_color('#D3D3D3'); self.ax.xaxis.label.set_color('#D3D3D3')
        self.ax.set_title("Object Decay Projection", color="#D3D3D3")
        self.ax.set_xlabel("Date", color="#D3D3D3"); self.ax.set_ylabel("Health %", color="#D3D3D3")
        self.ax.grid(True, linestyle='--', alpha=0.6, color="#5A5A5A")
        dates = [datetime(2025, 10, 1), datetime(2025, 10, 15), datetime(2025, 10, 30)]
        health = [100, 50, 20]
        self.ax.plot(dates, health, color="blue", label="Simple Decay (Mock)")
        self.ax.legend(facecolor="#3C3C3C", edgecolor="#5A5A5A", labelcolor="#D3D3D3")
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _update_decay_graph(self, object_name):
        self.ax.clear(); self.ax.set_facecolor("#3C3C3C")
        self.ax.tick_params(axis='x', colors='#D3D3D3'); self.ax.tick_params(axis='y', colors='#D3D3D3')
        self.ax.yaxis.label.set_color('#D3D3D3'); self.ax.xaxis.label.set_color('#D3D3D3')
        self.ax.set_title(f"Decay Projection for {object_name}", color="#D3D3D3")
        self.ax.set_xlabel("Date", color="#D3D3D3"); self.ax.set_ylabel("Health %", color="#D3D3D3")
        self.ax.grid(True, linestyle='--', alpha=0.6, color="#5A5A5A")
        start_date = datetime.now() - timedelta(days=10)
        dates_simple = [start_date + timedelta(days=i) for i in range(15)]
        health_simple = [100 - i * 5 for i in range(15)]
        dates_dsc = [start_date + timedelta(days=i) for i in range(8)]
        health_dsc = [95, 88, 75, 60, 48, 35, 20, 10]
        last_dsc_date = dates_dsc[-1]; last_dsc_health = health_dsc[-1]
        dsc_w_date = last_dsc_date + timedelta(hours=5)
        dsc_m_date = last_dsc_date + timedelta(hours=10)
        dsc_l_date = last_dsc_date + timedelta(hours=15)
        self.ax.plot(dates_simple, health_simple, color="blue", label="Simple Decay")
        self.ax.plot(dates_dsc, health_dsc, color="green", marker='o', linestyle='-', label="DSC Data")
        self.ax.plot([last_dsc_date, dsc_w_date], [last_dsc_health, 5], color="green", linestyle='--', label="DSC:W (Mock)")
        self.ax.plot([last_dsc_date, dsc_m_date], [last_dsc_health, 2], color="yellow", linestyle='--', label="DSC:M (Mock)")
        self.ax.plot([last_dsc_date, dsc_l_date], [last_dsc_health, 0], color="red", linestyle='--', label="DSC:L (Mock)")
        self.ax.legend(facecolor="#3C3C3C", edgecolor="#5A5A5A", labelcolor="#D3D3D3")
        self.fig.autofmt_xdate(); self.canvas.draw()

    def _update_history_table(self, object_name):
        for item in self.history_tree.get_children(): self.history_tree.delete(item)
        now = datetime.now()
        data_points = [{"screenshot": "shot_001.png", "datetime": (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M'), "health": "85%"}, {"screenshot": "shot_002.png", "datetime": (now - timedelta(days=1, hours=12)).strftime('%Y-%m-%d %H:%M'), "health": "60%"}, {"screenshot": "shot_003.png", "datetime": now.strftime('%Y-%m-%d %H:%M'), "health": "30%"}]
        for dp in data_points: self.history_tree.insert("", tk.END, values=(dp["screenshot"], dp["datetime"], dp["health"]))

if __name__ == "__main__":
    app = VultureTrackerUI()
    app.mainloop()