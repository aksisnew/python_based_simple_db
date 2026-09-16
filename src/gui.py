import os
import json
import queue
import shutil
import csv
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Callable, Any, Dict, List, Optional

import createDB
import flatDB
import search
import plugins_interact


class DBQueryPanel(tk.Toplevel):
    """Secure database query panel using strictly whitelisted predefined commands and GUI controls."""
    def __init__(self, master, db_path: Optional[str], db_data: Dict[str, Any]):
        super().__init__(master)
        self.title("Database Query & Performance Panel")
        self.geometry("750x520")
        self.db_path = db_path
        self.db_data = db_data

        # Top Info Frame
        info_frame = ttk.Frame(self, padding=10, style="Card.TFrame")
        info_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        db_label = os.path.basename(db_path) if db_path else "No DB Loaded"
        ttk.Label(info_frame, text=f"Secure Query Panel - {db_label}", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        self.speed_label = ttk.Label(info_frame, text="Execution Time: Ready", font=("Segoe UI", 9, "italic"), foreground="#2563eb")
        self.speed_label.pack(anchor=tk.W)

        # Main Body Layout
        body_frame = ttk.Frame(self, padding=10, style="Card.TFrame")
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Strict Predefined Command Controls (No arbitrary text inputs allowed)
        btn_frame = ttk.LabelFrame(body_frame, text=" Predefined Safe Operations ", padding=10)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Show Schema", command=lambda: self.execute_safe_command("SHOW_SCHEMA")).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Count Rows", command=lambda: self.execute_safe_command("COUNT_ROWS")).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="List All Records", command=lambda: self.execute_safe_command("SELECT_ALL")).pack(side=tk.LEFT, padx=3)
        
        # Safe Search Widget Section
        search_subframe = ttk.Frame(body_frame)
        search_subframe.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_subframe, text="Safe Keyword Search:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.query_entry = ttk.Entry(search_subframe, font=("Segoe UI", 9))
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.query_entry.bind("<Return>", lambda e: self.execute_safe_command("SEARCH"))

        ttk.Button(search_subframe, text="Run Search", command=lambda: self.execute_safe_command("SEARCH")).pack(side=tk.RIGHT)

        # Output Text Console (Read-only view)
        console_frame = ttk.Frame(body_frame)
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        scroll_y = ttk.Scrollbar(console_frame, orient=tk.VERTICAL)
        self.output_text = tk.Text(console_frame, wrap="word", font=("Consolas", 10), yscrollcommand=scroll_y.set, bg="#0f172a", fg="#f8fafc", state=tk.NORMAL)
        scroll_y.config(command=self.output_text.yview)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.log_output("Security Notice: Arbitrary CLI commands are disabled. Use buttons or controlled inputs above.\n")

    def log_output(self, message: str):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

    def execute_safe_command(self, action_type: str):
        start_time = time.perf_counter()
        result_output = ""

        try:
            if action_type == "SHOW_SCHEMA":
                schema = self.db_data.get("schema", {})
                result_output = json.dumps(schema, indent=2)
                action_desc = "SHOW SCHEMA"
            elif action_type == "COUNT_ROWS":
                count = len(self.db_data.get("data", []))
                result_output = f"Total Row Count: {count}"
                action_desc = "COUNT ROWS"
            elif action_type == "SELECT_ALL":
                data = self.db_data.get("data", [])
                result_output = json.dumps(data, indent=2)
                action_desc = "LIST ALL"
            elif action_type == "SEARCH":
                keyword = self.query_entry.get().strip()
                if not keyword:
                    messagebox.showwarning("Validation Warning", "Please enter a search keyword.", parent=self)
                    return
                records = self.db_data.get("data", [])
                filtered = search.search_records(records, keyword, "All")
                result_output = json.dumps(filtered, indent=2)
                action_desc = f"SEARCH '{keyword}'"
            else:
                raise ValueError("Unauthorized or unrecognized operation request.")
        except Exception as e:
            result_output = f"Execution Error: {e}"
            action_desc = action_type

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        self.speed_label.config(text=f"Execution Time: {elapsed_ms:.2f} ms")
        self.log_output(f"> Action: {action_desc}")
        self.log_output(result_output)
        self.log_output("-" * 40)


class VisualDBViewer(tk.Toplevel):
    """Read-only visual table viewer window with highlighted headers."""
    def __init__(self, master, db_name: str, db_data: Dict[str, Any]):
        super().__init__(master)
        self.title(f"Visual Viewer - {db_name}")
        self.geometry("850x500")

        info_frame = ttk.Frame(self, padding=10, style="Card.TFrame")
        info_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        schema_keys = list(db_data.get("schema", {}).keys())
        total_rows = len(db_data.get("data", []))

        ttk.Label(info_frame, text=f"Database: {db_name}", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Read-Only View | Columns: {len(schema_keys)} | Total Records: {total_rows}", font=("Segoe UI", 9)).pack(anchor=tk.W)

        table_frame = ttk.Frame(self, padding=10, style="Card.TFrame")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)

        viewer_style = ttk.Style(self)
        viewer_style.configure(
            "Viewer.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#1e293b",
            foreground="#ffffff",
            padding=(6, 6)
        )

        self.tree = ttk.Treeview(
            table_frame,
            style="Viewer.Treeview",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            selectmode="none"
        )

        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        columns = ["#"] + schema_keys
        self.tree["columns"] = columns
        self.tree["show"] = "headings"

        self.tree.heading("#", text="#")
        self.tree.column("#", width=50, anchor=tk.CENTER)

        for col in schema_keys:
            col_type = db_data["schema"][col]
            self.tree.heading(col, text=f"{col.upper()} [{col_type}]")
            self.tree.column(col, minwidth=120, width=160, anchor=tk.W)

        for idx, row in enumerate(db_data.get("data", []), start=1):
            vals = [idx] + [row.get(col, "") for col in schema_keys]
            self.tree.insert("", tk.END, values=vals)


class JSONEditorPopup(tk.Toplevel):
    """About & Full JSON Database Editor/Maker Popup Window."""
    def __init__(self, master):
        super().__init__(master)
        self.title("About & JSON Database Editor")
        self.geometry("900x600")
        
        self.clipboard: Dict[str, Optional[str]] = {"action": None, "path": None}
        self.current_file: Optional[str] = None
        self.base_dir = createDB.PROJECT_DIR

        self.bind("<Button-1>", self._dismiss_context_menu)
        self.setup_ui()
        self.populate_sidebar("")

    def _dismiss_context_menu(self, event=None):
        if hasattr(self, 'item_menu'):
            self.item_menu.unpost()
        if hasattr(self, 'empty_menu'):
            self.empty_menu.unpost()

    def setup_ui(self):
        about_frame = ttk.Frame(self, padding=10, style="Card.TFrame")
        about_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(about_frame, text="Virtual Flat JSON Database Engine", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(about_frame, text="Schema-Driven Flat-File Database System & Visual JSON Manager", font=("Segoe UI", 9)).pack(anchor=tk.W)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.sidebar_frame = ttk.Frame(paned, padding=5, style="Card.TFrame")
        paned.add(self.sidebar_frame, weight=1)

        ttk.Label(self.sidebar_frame, text="Database Files", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        self.tree = ttk.Treeview(self.sidebar_frame, show="tree", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<<TreeviewSelect>>", self.on_item_select)

        self.editor_frame = ttk.Frame(paned, padding=5, style="Card.TFrame")
        paned.add(self.editor_frame, weight=3)

        self.editor_label = ttk.Label(self.editor_frame, text="No file selected", font=("Segoe UI", 10, "bold"))
        self.editor_label.pack(anchor=tk.W, pady=(0, 5))

        self.text_editor = tk.Text(self.editor_frame, wrap="none", font=("Consolas", 10), undo=True)
        self.text_editor.pack(fill=tk.BOTH, expand=True)

        btn_bar = ttk.Frame(self.editor_frame)
        btn_bar.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_bar, text="New JSON File", command=self.create_new_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="Save Changes", command=self.save_file).pack(side=tk.RIGHT, padx=2)

        self.item_menu = tk.Menu(self, tearoff=0)
        self.item_menu.add_command(label="Rename", command=self.rename_item)
        self.item_menu.add_command(label="Cut", command=lambda: self.set_clipboard("cut"))
        self.item_menu.add_command(label="Copy", command=lambda: self.set_clipboard("copy"))
        self.item_menu.add_command(label="Paste", command=self.paste_item)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="Delete", command=self.delete_item)

        self.empty_menu = tk.Menu(self, tearoff=0)
        self.empty_menu.add_command(label="New Folder", command=self.create_new_folder)
        self.empty_menu.add_command(label="New JSON File", command=self.create_new_file)
        self.empty_menu.add_command(label="Paste", command=self.paste_item)

    def get_full_path(self, item_id: str) -> str:
        path_parts = []
        while item_id:
            path_parts.insert(0, self.tree.item(item_id, "text"))
            item_id = self.tree.parent(item_id)
        return os.path.join(self.base_dir, *path_parts)

    def populate_sidebar(self, parent: str, path: Optional[str] = None):
        if path is None:
            path = self.base_dir

        self.tree.delete(*self.tree.get_children(parent))
        try:
            items = os.listdir(path)
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for item in items:
                full_path = os.path.join(path, item)
                node = self.tree.insert(parent, "end", text=item, open=False)
                if os.path.isdir(full_path):
                    self.populate_sidebar(node, full_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read directory: {e}", parent=self)

    def refresh_sidebar(self):
        self.populate_sidebar("")

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            self.item_menu.post(event.x_root, event.y_root)
        else:
            self.tree.selection_remove(self.tree.selection())
            self.empty_menu.post(event.x_root, event.y_root)

    def on_item_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        
        path = self.get_full_path(selected[0])
        if os.path.isfile(path) and path.endswith(".json"):
            self.current_file = path
            self.editor_label.config(text=f"Editing: {os.path.basename(path)}")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_editor.delete("1.0", tk.END)
                self.text_editor.insert(tk.END, content)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read JSON file: {e}", parent=self)

    def save_file(self):
        if not self.current_file:
            messagebox.showwarning("Warning", "No active JSON file selected.", parent=self)
            return

        raw_content = self.text_editor.get("1.0", tk.END).strip()
        try:
            json.loads(raw_content)
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(raw_content)
            messagebox.showinfo("Saved", "JSON file saved successfully.", parent=self)
        except json.JSONDecodeError as err:
            messagebox.showerror("JSON Syntax Error", f"Cannot save invalid JSON:\n{err}", parent=self)

    def get_selected_folder(self) -> str:
        selected = self.tree.selection()
        if selected:
            path = self.get_full_path(selected[0])
            if os.path.isdir(path):
                return path
            return os.path.dirname(path)
        return self.base_dir

    def create_new_file(self):
        target_dir = self.get_selected_folder()
        new_name = simpledialog.askstring("New JSON File", "Enter file name:", parent=self)
        if new_name:
            if not new_name.endswith(".json"):
                new_name += ".json"
            new_path = os.path.join(target_dir, new_name)
            if not os.path.exists(new_path):
                default_structure = {"schema": {}, "data": []}
                with open(new_path, "w", encoding="utf-8") as f:
                    json.dump(default_structure, f, indent=2)
                self.refresh_sidebar()
            else:
                messagebox.showerror("Error", "File already exists.", parent=self)

    def create_new_folder(self):
        target_dir = self.get_selected_folder()
        folder_name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self)
        if folder_name:
            new_path = os.path.join(target_dir, folder_name)
            if not os.path.exists(new_path):
                os.makedirs(new_path)
                self.refresh_sidebar()
            else:
                messagebox.showerror("Error", "Folder already exists.", parent=self)

    def rename_item(self):
        selected = self.tree.selection()
        if not selected:
            return

        old_path = self.get_full_path(selected[0])
        old_name = os.path.basename(old_path)
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=old_name, parent=self)

        if new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                self.refresh_sidebar()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename: {e}", parent=self)

    def delete_item(self):
        selected = self.tree.selection()
        if not selected:
            return

        path = self.get_full_path(selected[0])
        if messagebox.askyesno("Confirm Delete", f"Delete '{os.path.basename(path)}'?", parent=self):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.refresh_sidebar()
                self.text_editor.delete("1.0", tk.END)
                self.editor_label.config(text="No file selected")
                self.current_file = None
            except Exception as e:
                messagebox.showerror("Error", f"Deletion failed: {e}", parent=self)

    def set_clipboard(self, action: str):
        selected = self.tree.selection()
        if selected:
            self.clipboard["action"] = action
            self.clipboard["path"] = self.get_full_path(selected[0])

    def paste_item(self):
        src_path = self.clipboard.get("path")
        if not src_path or not os.path.exists(src_path):
            messagebox.showinfo("Info", "Nothing to paste.", parent=self)
            return

        target_dir = self.get_selected_folder()
        dest_path = os.path.join(target_dir, os.path.basename(src_path))

        if src_path == dest_path:
            return

        try:
            if self.clipboard["action"] == "copy":
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path)
                else:
                    shutil.copy2(src_path, dest_path)
            elif self.clipboard["action"] == "cut":
                shutil.move(src_path, dest_path)
                self.clipboard = {"action": None, "path": None}
            self.refresh_sidebar()
        except Exception as e:
            messagebox.showerror("Error", f"Paste failed: {e}", parent=self)


class FlatDBGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Virtual Flat JSON Database Engine")

        self.last_opened_db: Optional[str] = None
        self.clipboard: Dict[str, Optional[str]] = {"action": None, "path": None}

        self.root.bind("<Button-1>", self._dismiss_context_menu)

        self._apply_custom_styles()
        self._apply_responsive_window_size()

        self.active_db: Optional[str] = None
        self.db_data: Dict[str, Any] = {"schema": {}, "data": []}
        self.displayed_records: List[Dict[str, Any]] = []

        self.search_sequence_id: int = 0
        self.search_lock = threading.Lock()
        self.ui_queue: queue.Queue = queue.Queue()

        self.plugin_manager = plugins_interact.PluginManager(self)

        self._setup_menu()
        self._setup_ui()
        self._check_ui_queue()
        self.refresh_db_list()

        self.plugin_manager.load_all_plugins()

    def _dismiss_context_menu(self, event=None):
        if hasattr(self, 'sidebar_item_menu'):
            self.sidebar_item_menu.unpost()
        if hasattr(self, 'sidebar_empty_menu'):
            self.sidebar_empty_menu.unpost()

    def _apply_custom_styles(self):
        self.style = ttk.Style()
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        bg_color = "#f5f6f8"
        card_color = "#ffffff"
        primary_color = "#2563eb"
        text_color = "#1e293b"

        self.root.configure(bg=bg_color)
        self.style.configure(".", background=bg_color, foreground=text_color, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("Card.TFrame", background=card_color, relief="flat")
        self.style.configure("TButton", padding=(10, 5), font=("Segoe UI", 9, "bold"))
        self.style.configure("TMenubutton", padding=(10, 5), font=("Segoe UI", 9, "bold"))

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
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        self.root.minsize(min(900, screen_width), min(550, screen_height))

        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def _setup_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Database", command=self._on_create_db_click)
        file_menu.add_command(label="Open Last Opened", command=self._open_last_opened)
        file_menu.add_command(label="Open File...", command=self._open_external_file)
        file_menu.add_command(label="Visual Table Viewer", command=self._open_visual_viewer)
        file_menu.add_command(label="Query Panel...", command=self._open_query_panel)
        file_menu.add_command(label="Export to CSV", command=self._export_to_csv)
        file_menu.add_separator()
        file_menu.add_command(label="About & Database Maker", command=self._open_about_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

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

    def run_in_background(self, task_func: Callable, callback: Callable, *args: Any):
        def worker():
            try:
                result = task_func(*args)
                self.ui_queue.put((callback, result, None))
            except Exception as e:
                self.ui_queue.put((callback, None, e))

        threading.Thread(target=worker, daemon=True).start()

    def _check_ui_queue(self):
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

    def _setup_ui(self):
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        sidebar = ttk.Frame(main_container, padding=12, style="Card.TFrame")
        main_container.add(sidebar, weight=1)

        ttk.Label(sidebar, text="Databases", font=("Segoe UI", 12, "bold"), background="#ffffff").pack(anchor=tk.W, pady=(0, 8))

        self.sidebar_tree = ttk.Treeview(sidebar, show="tree", selectmode="browse")
        self.sidebar_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.sidebar_tree.bind("<Button-3>", self._show_sidebar_context_menu)
        self.sidebar_tree.bind("<<TreeviewSelect>>", self._on_sidebar_tree_select)

        self.sidebar_item_menu = tk.Menu(self.root, tearoff=0)
        self.sidebar_item_menu.add_command(label="Rename", command=self._rename_sidebar_item)
        self.sidebar_item_menu.add_command(label="Cut", command=lambda: self._set_sidebar_clipboard("cut"))
        self.sidebar_item_menu.add_command(label="Copy", command=lambda: self._set_sidebar_clipboard("copy"))
        self.sidebar_item_menu.add_command(label="Paste", command=self._paste_sidebar_item)
        self.sidebar_item_menu.add_separator()
        self.sidebar_item_menu.add_command(label="Delete", command=self._delete_sidebar_item)

        self.sidebar_empty_menu = tk.Menu(self.root, tearoff=0)
        self.sidebar_empty_menu.add_command(label="New Folder", command=self._create_sidebar_folder)
        self.sidebar_empty_menu.add_command(label="New DB", command=self._on_create_db_click)
        self.sidebar_empty_menu.add_command(label="Paste", command=self._paste_sidebar_item)

        ttk.Button(sidebar, text="+ Create Database", command=self._on_create_db_click).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar, text="Refresh List", command=self.refresh_db_list).pack(fill=tk.X, pady=2)
        ttk.Button(
            sidebar, 
            text="🔌 Plugins Manager", 
            command=lambda: self.plugin_manager.show_plugins_dialog(self.root)
        ).pack(fill=tk.X, pady=(10, 2))

        content_frame = ttk.Frame(main_container, padding=12, style="Card.TFrame")
        main_container.add(content_frame, weight=4)

        action_bar = ttk.Frame(content_frame, style="Card.TFrame")
        action_bar.pack(fill=tk.X, pady=(0, 12))

        ttk.Button(action_bar, text="Delete Row", command=self._on_delete_row_click).pack(side=tk.RIGHT, padx=2)
        ttk.Button(action_bar, text="+ Row", command=self._on_add_row_click).pack(side=tk.RIGHT, padx=2)
        ttk.Button(action_bar, text="+ Column", command=self._on_add_column_click).pack(side=tk.RIGHT, padx=2)
        ttk.Button(action_bar, text="Query Panel", command=self._open_query_panel).pack(side=tk.RIGHT, padx=2)

        open_mb = ttk.Menubutton(action_bar, text="Open ▾")
        open_menu = tk.Menu(open_mb, tearoff=0)
        open_menu.add_command(label="Open Last Opened", command=self._open_last_opened)
        open_menu.add_command(label="Open File...", command=self._open_external_file)
        open_mb["menu"] = open_menu
        open_mb.pack(side=tk.RIGHT, padx=2)

        file_mb = ttk.Menubutton(action_bar, text="File ▾")
        file_menu_btn = tk.Menu(file_mb, tearoff=0)
        file_menu_btn.add_command(label="New DB", command=self._on_create_db_click)
        file_menu_btn.add_command(label="Visual DB Viewer", command=self._open_visual_viewer)
        file_menu_btn.add_command(label="Query Panel...", command=self._open_query_panel)
        file_menu_btn.add_command(label="Export to CSV", command=self._export_to_csv)
        file_menu_btn.add_separator()
        file_menu_btn.add_command(label="About & Database Maker", command=self._open_about_dialog)
        file_mb["menu"] = file_menu_btn
        file_mb.pack(side=tk.RIGHT, padx=2)

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

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(content_frame, textvariable=self.status_var, relief=tk.FLAT, anchor=tk.W, font=("Segoe UI", 9), background="#e2e8f0", padding=(8, 4))
        self.status_bar.pack(fill=tk.X, pady=(8, 0))

    def _get_sidebar_path(self, item_id: str) -> str:
        path_parts = []
        while item_id:
            path_parts.insert(0, self.sidebar_tree.item(item_id, "text"))
            item_id = self.sidebar_tree.parent(item_id)
        return os.path.join(createDB.PROJECT_DIR, *path_parts)

    def _populate_sidebar_tree(self, parent: str, path: str):
        self.sidebar_tree.delete(*self.sidebar_tree.get_children(parent))
        try:
            items = os.listdir(path)
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for item in items:
                full_path = os.path.join(path, item)
                node = self.sidebar_tree.insert(parent, "end", text=item, open=False)
                if os.path.isdir(full_path):
                    self._populate_sidebar_tree(node, full_path)
        except Exception:
            pass

    def refresh_db_list(self):
        self._populate_sidebar_tree("", createDB.PROJECT_DIR)
        self.status_var.set("Refreshed database folder structure.")

    def _show_sidebar_context_menu(self, event):
        item_id = self.sidebar_tree.identify_row(event.y)
        if item_id:
            self.sidebar_tree.selection_set(item_id)
            self.sidebar_item_menu.post(event.x_root, event.y_root)
        else:
            self.sidebar_tree.selection_remove(self.sidebar_tree.selection())
            self.sidebar_empty_menu.post(event.x_root, event.y_root)

    def _on_sidebar_tree_select(self, event):
        selected = self.sidebar_tree.selection()
        if not selected:
            return
        full_path = self._get_sidebar_path(selected[0])
        if os.path.isfile(full_path) and full_path.endswith(".json"):
            self.load_active_db_by_path(full_path)

    def _get_sidebar_selected_folder(self) -> str:
        selected = self.sidebar_tree.selection()
        if selected:
            path = self._get_sidebar_path(selected[0])
            if os.path.isdir(path):
                return path
            return os.path.dirname(path)
        return createDB.PROJECT_DIR

    def _create_sidebar_folder(self):
        target_dir = self._get_sidebar_selected_folder()
        folder_name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self.root)
        if folder_name:
            new_path = os.path.join(target_dir, folder_name)
            if not os.path.exists(new_path):
                os.makedirs(new_path)
                self.refresh_db_list()

    def _rename_sidebar_item(self):
        selected = self.sidebar_tree.selection()
        if not selected:
            return
        old_path = self._get_sidebar_path(selected[0])
        old_name = os.path.basename(old_path)
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=old_name, parent=self.root)

        if new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                self.refresh_db_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename: {e}")

    def _delete_sidebar_item(self):
        selected = self.sidebar_tree.selection()
        if not selected:
            return
        path = self._get_sidebar_path(selected[0])
        if messagebox.askyesno("Confirm Delete", f"Delete '{os.path.basename(path)}'?", parent=self.root):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.refresh_db_list()
            except Exception as e:
                messagebox.showerror("Error", f"Delete failed: {e}")

    def _set_sidebar_clipboard(self, action: str):
        selected = self.sidebar_tree.selection()
        if selected:
            self.clipboard["action"] = action
            self.clipboard["path"] = self._get_sidebar_path(selected[0])

    def _paste_sidebar_item(self):
        src_path = self.clipboard.get("path")
        if not src_path or not os.path.exists(src_path):
            messagebox.showinfo("Info", "Nothing to paste.")
            return

        target_dir = self._get_sidebar_selected_folder()
        dest_path = os.path.join(target_dir, os.path.basename(src_path))

        if src_path == dest_path:
            return

        try:
            if self.clipboard["action"] == "copy":
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path)
                else:
                    shutil.copy2(src_path, dest_path)
            elif self.clipboard["action"] == "cut":
                shutil.move(src_path, dest_path)
                self.clipboard = {"action": None, "path": None}
            self.refresh_db_list()
        except Exception as e:
            messagebox.showerror("Error", f"Paste failed: {e}")

    def _open_about_dialog(self):
        popup = JSONEditorPopup(self.root)
        popup.focus()

    def _open_visual_viewer(self):
        if not self.active_db:
            messagebox.showwarning("Warning", "Load a database first.")
            return
        viewer = VisualDBViewer(self.root, self.active_db, self.db_data)
        viewer.focus()

    def _open_query_panel(self):
        if not self.active_db:
            messagebox.showwarning("Warning", "Load a database first.")
            return
        full_path = self.last_opened_db or os.path.join(createDB.PROJECT_DIR, self.active_db)
        panel = DBQueryPanel(self.root, full_path, self.db_data)
        panel.focus()

    def _export_to_csv(self):
        if not self.active_db or not self.db_data.get("data"):
            messagebox.showwarning("Warning", "No database loaded to export.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Export Database to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not save_path:
            return

        schema = list(self.db_data.get("schema", {}).keys())
        records = self.db_data.get("data", [])

        try:
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=schema)
                writer.writeheader()
                writer.writerows(records)
            messagebox.showinfo("Export Successful", f"Database exported to {save_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write CSV: {e}")

    def _open_last_opened(self):
        if self.last_opened_db and os.path.exists(self.last_opened_db):
            self.load_active_db_by_path(self.last_opened_db)
        else:
            messagebox.showinfo("Notice", "No previously opened database found in this session.")

    def _open_external_file(self):
        selected_file = filedialog.askopenfilename(
            title="Open JSON Database",
            initialdir=createDB.PROJECT_DIR,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if selected_file:
            self.load_active_db_by_path(selected_file)

    def load_active_db_by_path(self, full_path: str):
        display_name = os.path.basename(full_path)
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

    def _on_add_row_click(self):
        if not self.active_db or not self.db_data.get("schema"):
            messagebox.showwarning("Warning", "Please load a database with at least one column.")
            return

        dialog = RowDialog(self.root, self.db_data["schema"])
        self.root.wait_window(dialog.top)

        if dialog.result is None:
            return

        full_path = self.last_opened_db or os.path.join(createDB.PROJECT_DIR, self.active_db)

        def task():
            return flatDB.add_row(full_path, dialog.result)

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

    def _update_column_filter_options(self):
        schema = list(self.db_data.get("schema", {}).keys())
        options = ["All"] + schema
        self.column_filter_cb["values"] = options
        if self.column_filter_var.get() not in options:
            self.column_filter_var.set("All")

    def _render_grid(self, records: List[Dict[str, Any]]):
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


class ColumnDialog:
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
