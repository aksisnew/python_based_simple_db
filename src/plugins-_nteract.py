import importlib.util
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any


PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


def ensure_plugins_dir() -> str:
    """Ensures the ./plugins directory exists."""
    if not os.path.exists(PLUGINS_DIR):
        os.makedirs(PLUGINS_DIR, exist_ok=True)
    return PLUGINS_DIR


def discover_plugins() -> Dict[str, str]:
    """Scans ./plugins directory and returns a dictionary of {filename: absolute_path}."""
    ensure_plugins_dir()
    discovered = {}
    
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if fname.endswith(".py") and not fname.startswith("__"):
            abs_path = os.path.join(PLUGINS_DIR, fname)
            discovered[fname] = abs_path
            
    return discovered


class PluginManager:
    """Handles loading and initializing plugins into the main application."""
    
    def __init__(self, main_app: Any):
        self.main_app = main_app
        self.loaded_plugins: Dict[str, Any] = {}
        ensure_plugins_dir()

    def load_all_plugins(self):
        """Discovers and loads all valid plugin .py files."""
        plugins_map = discover_plugins()
        
        for fname, filepath in plugins_map.items():
            if fname in self.loaded_plugins:
                continue  # Skip already loaded
            
            try:
                module_name = f"plugins.{fname[:-3]}"
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Look for initialize() hook inside the plugin
                    if hasattr(module, "initialize"):
                        module.initialize(self.main_app)
                        self.loaded_plugins[fname] = module
                    else:
                        print(f"[Plugin Warning] '{fname}' has no initialize(app) function.")

            except Exception as e:
                print(f"[Plugin Error] Failed to load '{fname}': {e}")

    def show_plugins_dialog(self, parent_widget: tk.Tk):
        """Displays a modal dialog listing all recognized plugins from ./plugins."""
        dialog = tk.Toplevel(parent_widget)
        dialog.title("Plugin Manager")
        dialog.geometry("450x300")
        dialog.transient(parent_widget)
        dialog.grab_set()

        ttk.Label(dialog, text="Recognized Plugins in ./plugins:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))

        tree = ttk.Treeview(dialog, columns=("Status",), show="tree headings")
        tree.heading("#0", text="Plugin File")
        tree.heading("Status", text="Status")
        tree.column("#0", width=250)
        tree.column("Status", width=120)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Populate tree with plugin files found
        all_plugins = discover_plugins()
        if not all_plugins:
            tree.insert("", tk.END, text="No plugins found", values=("N/A",))
        else:
            for fname in all_plugins.keys():
                status = "Loaded" if fname in self.loaded_plugins else "Recognized"
                tree.insert("", tk.END, text=fname, values=(status,))

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def refresh():
            self.load_all_plugins()
            dialog.destroy()
            self.show_plugins_dialog(parent_widget)

        ttk.Button(btn_frame, text="Reload Plugins", command=refresh).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
