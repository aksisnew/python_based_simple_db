import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Callable, Any, Dict, List, Optional

import createDB
import flatDB
import search
import plugins_interact


class FlatDBGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Virtual Flat JSON Database Engine")
        
        # Track last opened DB
        self.last_opened_db: Optional[str] = None

        # Apply UI Theme & Styling
        self._apply_custom_styles()

        # Responsive Screen Sizing & Window Setup
        self._apply_responsive_window_size()

        # Active state
        self.active_db: Optional[str] = None
        self.db_data: Dict[str, Any] = {"schema": {}, "data": []}
        self.displayed_records: List[Dict[str, Any]] = []

        # Concurrency & Search sequence guard to prevent race conditions
        self.search_sequence_id: int = 0
        self.search_lock = threading.Lock()
        self.ui_queue: queue.Queue = queue.Queue()

        # Plugin System Initialization
        self.plugin_manager = plugins_interact.PluginManager(self)

        self._setup_menu()
        self._setup_ui()
        self._check_ui_queue()
        self.refresh_db_list()

        # Load all plugins after UI is completely initialized
        self.plugin_manager.load_all_plugins()

    def _apply_custom_styles(self):
        """Applies a clean, modern style palette across Tkinter widgets."""
        self.style = ttk.Style()
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        # Palette Colors
        bg_color = "#f5f6f8"
        card_color = "#ffffff"
        primary_color = "#2563eb"
        text_color = "#1e293b"

        self.root.configure(bg=bg_color)

        # Style Configurations
        self.style.configure(".", background=bg_color, foreground=text_color, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("Card.TFrame", background=card_color, relief="flat")
        
        # Buttons
        self.style.configure("TButton", padding=(10, 5), font=("Segoe UI", 9, "bold"))
        self.style.map("TButton", background=[("active", "#e2e8f0")])
        
        self.style.configure("TMenubutton", padding=(10, 5), font=("Segoe UI", 9, "bold"))
        
        # Treeview (Data Grid)
        self.style.configure(
            "Treeview",
            background=card_color,
            fieldbackground=card_color,
            foreground=text_color,
            rowheight=28,
            font=("Segoe UI", 10)
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#e2e8f0",
            foreground="#0f172a",
            padding=(5, 5)
        )
        self.style.map("Treeview", background=[("selected", primary_color)], foreground=[("selected", "#ffffff")])

    def _apply_responsive_window_size(self):
        """Calculates screen dimensions and adapts window size and state automatically."""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        self.root.minsize(min(900, screen_width), min(550, screen_height))

        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    # -------------------------------------------------------------------
    # Menu Bar Setup
    # -------------------------------------------------------------------

    def _setup_menu(self):
        menubar = tk.Menu(self.root)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Database", command=self._on_create_db_click)
        file_menu.add_command(label="Open Last Opened", command=self._open_last_opened)
        file_menu.add_command(label="Open File...", command=self._open_external_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Plugins Menu Item
        plugin_menu = tk.Menu(menubar, tearoff=0)
        plugin_menu.add_command(
            label="Manage Plugins...",
            command=lambda: self.plugin_manager.show_plugins_dialog(self.root)
        )
        plugin_menu.add_command(
            label="Reload Plugins",
            command=lambda: self.plugin_manager.load_all_plugins()
        )
        menubar.add_cascade(label="Plugins", menu=plugin_menu)
        
        self.root.config(menu=menubar)

    # -------------------------------------------------------------------
    # Threading & UI Safe Dispatcher
    # -------------------------------------------------------------------

    def run_in_background(self, task_func: Callable, callback: Callable, *args: Any):
        """Runs heavy tasks in a background thread and returns results safely to UI thread."""
        def worker():
            try:
                result = task_func(*args)
                self.ui_queue.put((callback, result, None))
            except Exception as e:
                self.ui_queue.put((callback, None, e))

        threading.Thread(target=worker, daemon=True).start()

    def _check_ui_queue(self):
        """Processes completed background thread tasks on the main Tkinter thread."""
        while not self.ui_queue.empty():
            try:
                callback, result, err = self.ui_queue.get_nowait()
                if err:
                    messagebox.showerror("Operation Error", str(err))
                else:
                    callback(result)
            except queue.Empty:
                break
        self.root.after(100, self._check_ui_queue)

    # -------------------------------------------------------------------
    # UI Layout Setup
    # -------------------------------------------------------------------

    def _setup_ui(self):
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. Sidebar Frame
        sidebar = ttk.Frame(main_container, padding=12, style="Card.TFrame")
        main_container.add(sidebar, weight=1)

        ttk.Label(sidebar, text="Databases", font=("Segoe UI", 12, "bold"), background="#ffffff").pack(anchor=tk.W, pady=(0, 8))

        self.db_listbox = tk.Listbox(
            sidebar,
            selectmode=tk.SINGLE,
            exportselection=False,
            bd=1,
            relief="solid",
            highlightthickness=0,
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#1e293b",
            selectbackground="#2563eb",
            selectforeground="#ffffff"
        )
        self.db_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.db_listbox.bind("<<ListboxSelect>>", self._on_db_selected)

        ttk.Button(sidebar, text="+ Create Database", command=self._on_create_db_click).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar, text="Rename Selected", command=self._on_rename_db_click).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar, text="Refresh List", command=self.refresh_db_list).pack(fill=tk.X, pady=2)
        
        ttk.Button(
            sidebar, 
            text="🔌 Plugins Manager", 
            command=lambda: self.plugin_manager.show_plugins_dialog(self.root)
        ).pack(fill=tk.X, pady=(10, 2))

        # 2. Main Content Frame
        content_frame = ttk.Frame(main_container, padding=12, style="Card.TFrame")
        main_container.add(content_frame, weight=4)

        # Top Action Bar
        action_bar = ttk.Frame(content_frame, style="Card.TFrame")
        action_bar.pack(fill=tk.X, pady=(0, 12))

        # Right-side action controls
        ttk.Button(action_bar, text="Delete Row", command=self._on_delete_row_click).pack(side=tk.RIGHT, padx=2)
        ttk.Button(action_bar, text="+ Row", command=self._on_add_row_click).pack(side=tk.RIGHT, padx=2)
        ttk.Button(action_bar, text="+ Column", command=self._on_add_column_click).pack(side=tk.RIGHT, padx=2)

        # Plugins Button
        ttk.Button(action_bar, text="Plugins", command=lambda: self.plugin_manager.show_plugins_dialog(self.root)).pack(side=tk.RIGHT, padx=2)

        # "Open" Dropdown Menubutton
        open_mb = ttk.Menubutton(action_bar, text="Open ▾")
        open_menu = tk.Menu(open_mb, tearoff=0)
        open_menu.add_command(label="Open Last Opened", command=self._open_last_opened)
        open_menu.add_command(label="Open File...", command=self._open_external_file)
        open_mb["menu"] = open_menu
        open_mb.pack(side=tk.RIGHT, padx=2)

        # "New" Dropdown Menubutton
        new_mb = ttk.Menubutton(action_bar, text="New ▾")
        new_menu = tk.Menu(new_mb, tearoff=0)
        new_menu.add_command(label="New DB", command=self._on_create_db_click)
        new_mb["menu"] = new_menu
        new_mb.pack(side=tk.RIGHT, padx=2)

        # Left-side search elements
        ttk.Label(action_bar, text="Search:", background="#ffffff", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry = ttk.Entry(action_bar, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Label(action_bar, text="Column:", background="#ffffff", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.column_filter_var = tk.StringVar(value="All")
        self.column_filter_cb = ttk.Combobox(action_bar, textvariable=self.column_filter_var, state="readonly", width=12)
        self.column_filter_cb.pack(side=tk.LEFT, padx=(0, 10))
        self.column_filter_cb.bind("<<ComboboxSelected>>", lambda e: self._on_search_changed())

        # Data Treeview Container Frame
        grid_frame = ttk.Frame(content_frame, style="Card.TFrame")
        grid_frame.pack(fill=tk.BOTH, expand=True)

        self.tree_scroll_y = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL)
        self.tree_scroll_x = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL)

        self.tree = ttk.Treeview(
            grid_frame,
            yscrollcommand=self.tree_scroll_y.set,
            xscrollcommand=self.tree_scroll_x.set,
            selectmode="browse"
        )

        self.tree_scroll_y.config(command=self.tree.yview)
        self.tree_scroll_x.config(command=self.tree.xview)

        self.tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(content_frame, textvariable=self.status_var, relief=tk.FLAT, anchor=tk.W, font=("Segoe UI", 9), background="#e2e8f0", padding=(8, 4))
        self.status_bar.pack(fill=tk.X, pady=(8, 0))

    # -------------------------------------------------------------------
    # Open File Actions
    # -------------------------------------------------------------------

    def _open_last_opened(self):
        """Opens the last opened database if tracked."""
        if self.last_opened_db:
            if os.path.exists(self.last_opened_db):
                self.load_active_db_by_path(self.last_opened_db)
            else:
                messagebox.showerror("Error", f"Last opened file no longer exists: {self.last_opened_db}")
        else:
            messagebox.showinfo("Notice", "No previously opened database found in this session.")

    def _open_external_file(self):
        """Opens a file picker dialog to locate and open a JSON database file."""
        selected_file = filedialog.askopenfilename(
            title="Open JSON Database",
            initialdir=createDB.PROJECT_DIR,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if selected_file:
            self.load_active_db_by_path(selected_file)

    # -------------------------------------------------------------------
    # Database Selection & Loading
    # -------------------------------------------------------------------

    def refresh_db_list(self):
        """Refreshes available .json databases from createDB."""
        def task():
            return createDB.list_databases()

        def callback(db_list):
            self.db_listbox.delete(0, tk.END)
            for db in db_list:
                self.db_listbox.insert(tk.END, db)
            self.status_var.set(f"Loaded {len(db_list)} database(s).")

        self.run_in_background(task, callback)

    def _on_db_selected(self, event):
        selection = self.db_listbox.curselection()
        if not selection:
            return
        selected_db = self.db_listbox.get(selection[0])
        full_path = os.path.join(createDB.PROJECT_DIR, selected_db)
        self.load_active_db_by_path(full_path, db_name=selected_db)

    def load_active_db(self, db_name: str):
        """Loads selected database content by name."""
        full_path = os.path.join(createDB.PROJECT_DIR, db_name)
        self.load_active_db_by_path(full_path, db_name=db_name)

    def load_active_db_by_path(self, full_path: str, db_name: Optional[str] = None):
        """Loads database content given a full path."""
        display_name = db_name if db_name else os.path.basename(full_path)
        self.active_db = display_name
        self.last_opened_db = full_path
        self.status_var.set(f"Loading '{display_name}'...")

        def task():
            return flatDB.load_db(full_path)

        def callback(db_content):
            self.db_data = db_content
            self._update_column_filter_options()
            self._render_grid(db_content.get("data", []))
            self.status_var.set(f"Active DB: '{display_name}' | Rows: {len(db_content.get('data', []))}")

        self.run_in_background(task, callback)

    # -------------------------------------------------------------------
    # Database Actions (createDB integration)
    # -------------------------------------------------------------------

    def _on_create_db_click(self):
        db_name = simpledialog.askstring("New Database", "Enter database name:", parent=self.root)
        if not db_name:
            return

        def task():
            return createDB.create_database(db_name)

        def callback(created_file):
            messagebox.showinfo("Success", f"Database '{created_file}' created successfully.")
            self.refresh_db_list()

        self.run_in_background(task, callback)

    def _on_rename_db_click(self):
        if not self.active_db:
            messagebox.showwarning("Warning", "Select a database to rename.")
            return

        new_name = simpledialog.askstring("Rename Database", f"New name for '{self.active_db}':", parent=self.root)
        if not new_name:
            return

        old_name = self.active_db

        def task():
            return createDB.rename_database(old_name, new_name)

        def callback(renamed_file):
            messagebox.showinfo("Success", f"Renamed to '{renamed_file}'.")
            self.active_db = renamed_file
            self.refresh_db_list()

        self.run_in_background(task, callback)

    # -------------------------------------------------------------------
    # Schema Actions (flatDB integration)
    # -------------------------------------------------------------------

    def _on_add_column_click(self):
        if not self.active_db:
            messagebox.showwarning("Warning", "Load a database first.")
            return

        dialog = ColumnDialog(self.root)
        self.root.wait_window(dialog.top)

        if not dialog.result:
            return

        col_name, col_type, default_val = dialog.result
        full_path = self.last_opened_db or os.path.join(createDB.PROJECT_DIR, self.active_db)

        def task():
            return flatDB.add_column(full_path, col_name, col_type, default_val)

        def callback(updated_db):
            self.db_data = updated_db
            self._update_column_filter_options()
            self._render_grid(updated_db.get("data", []))
            self.status_var.set(f"Added column '{col_name}' ({col_type}).")

        self.run_in_background(task, callback)

    # -------------------------------------------------------------------
    # Row Actions (flatDB integration)
    # -------------------------------------------------------------------

    def _on_add_row_click(self):
        if not self.active_db or not self.db_data.get("schema"):
            messagebox.showwarning("Warning", "Please load a database with at least one column.")
            return

        dialog = RowDialog(self.root, self.db_data["schema"])
        self.root.wait_window(dialog.top)

        if dialog.result is None:
            return

        full_path = self.last_opened_db or os.path.join(createDB.PROJECT_DIR, self.active_db)
        row_payload = dialog.result

        def task():
            return flatDB.add_row(full_path, row_payload)

        def callback(updated_db):
            self.db_data = updated_db
            self._render_grid(updated_db.get("data", []))
            self.status_var.set("Row added successfully.")

        self.run_in_background(task, callback)

    def _on_delete_row_click(self):
        selected_item = self.tree.selection()
        if not selected_item or not self.active_db:
            messagebox.showwarning("Warning", "Select a row in the table to delete.")
            return

        item_values = self.tree.item(selected_item[0])["values"]
        if not item_values:
            return

        row_index = int(item_values[0]) - 1
        full_path = self.last_opened_db or os.path.join(createDB.PROJECT_DIR, self.active_db)

        def task():
            return flatDB.delete_row(full_path, row_index)

        def callback(updated_db):
            self.db_data = updated_db
            self._render_grid(updated_db.get("data", []))
            self.status_var.set(f"Deleted row {row_index + 1}.")

        self.run_in_background(task, callback)

    # -------------------------------------------------------------------
    # Thread-Safe Search Execution
    # -------------------------------------------------------------------

    def _on_search_changed(self, *args):
        if not self.active_db:
            return

        query = self.search_var.get()
        target_col = self.column_filter_var.get()
        records = self.db_data.get("data", [])

        with self.search_lock:
            self.search_sequence_id += 1
            current_id = self.search_sequence_id

        def task():
            filtered = search.search_records(records, query, target_col)
            return current_id, filtered

        def callback(result_payload):
            if result_payload is None:
                return
            res_id, filtered_records = result_payload
            with self.search_lock:
                if res_id != self.search_sequence_id:
                    return
            self._render_grid(filtered_records)
            self.status_var.set(f"Search results: {len(filtered_records)} row(s) matched.")

        self.run_in_background(task, callback)

    # -------------------------------------------------------------------
    # Grid & UI Rendering Helpers
    # -------------------------------------------------------------------

    def _update_column_filter_options(self):
        schema = list(self.db_data.get("schema", {}).keys())
        options = ["All"] + schema
        self.column_filter_cb["values"] = options
        if self.column_filter_var.get() not in options:
            self.column_filter_var.set("All")

    def _render_grid(self, records: List[Dict[str, Any]]):
        """Renders columns and rows into Tkinter Treeview."""
        self.displayed_records = records

        for item in self.tree.get_children():
            self.tree.delete(item)

        schema = list(self.db_data.get("schema", {}).keys())
        columns = ["#"] + schema

        self.tree["columns"] = columns
        self.tree["show"] = "headings"

        self.tree.heading("#", text="#")
        self.tree.column("#", width=50, anchor=tk.CENTER)

        for col in schema:
            col_type = self.db_data["schema"][col]
            self.tree.heading(col, text=f"{col} ({col_type})")
            self.tree.column(col, minwidth=100, width=150, anchor=tk.W)

        for index, row_data in enumerate(records, start=1):
            values = [index] + [row_data.get(col, "") for col in schema]
            self.tree.insert("", tk.END, values=values)


# -------------------------------------------------------------------
# Dialog Windows for Input Capture
# -------------------------------------------------------------------

class ColumnDialog:
    """Dialog popup for adding a new column with 4 restricted data types."""
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("Add Column")
        self.top.geometry("320x240")
        self.top.resizable(False, False)
        self.result = None

        ttk.Label(self.top, text="Column Name:").pack(anchor=tk.W, padx=15, pady=(15, 2))
        self.name_entry = ttk.Entry(self.top)
        self.name_entry.pack(fill=tk.X, padx=15)

        ttk.Label(self.top, text="Data Type:").pack(anchor=tk.W, padx=15, pady=(10, 2))
        self.type_var = tk.StringVar(value="varchar")
        types_cb = ttk.Combobox(
            self.top,
            textvariable=self.type_var,
            values=["varchar", "char", "alphanumeric", "boolean"],
            state="readonly"
        )
        types_cb.pack(fill=tk.X, padx=15)

        ttk.Label(self.top, text="Default Value (Optional):").pack(anchor=tk.W, padx=15, pady=(10, 2))
        self.default_entry = ttk.Entry(self.top)
        self.default_entry.pack(fill=tk.X, padx=15)

        ttk.Button(self.top, text="Add Column", command=self._on_submit).pack(pady=15)

    def _on_submit(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Column name is required.", parent=self.top)
            return
        col_type = self.type_var.get()
        default_val = self.default_entry.get().strip() or None
        self.result = (name, col_type, default_val)
        self.top.destroy()


class RowDialog:
    """Dynamically generates input fields based on schema columns for row creation."""
    def __init__(self, parent, schema: Dict[str, str]):
        self.top = tk.Toplevel(parent)
        self.top.title("Add Row Record")
        self.top.geometry("360x420")
        self.top.minsize(300, 250)
        self.schema = schema
        self.inputs: Dict[str, Any] = {}
        self.result = None

        container = ttk.Frame(self.top, padding=15)
        container.pack(fill=tk.BOTH, expand=True)

        for col_name, col_type in schema.items():
            ttk.Label(container, text=f"{col_name} ({col_type}):").pack(anchor=tk.W, pady=(5, 2))
            if col_type == "boolean":
                var = tk.StringVar(value="False")
                cb = ttk.Combobox(container, textvariable=var, values=["True", "False"], state="readonly")
                cb.pack(fill=tk.X)
                self.inputs[col_name] = var
            else:
                entry = ttk.Entry(container)
                entry.pack(fill=tk.X)
                self.inputs[col_name] = entry

        ttk.Button(container, text="Save Row", command=self._on_submit).pack(pady=15)

    def _on_submit(self):
        payload = {}
        for col_name, widget in self.inputs.items():
            val = widget.get().strip()
            payload[col_name] = val
        self.result = payload
        self.top.destroy()
