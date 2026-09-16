import sys
import tkinter as tk
from tkinter import messagebox
from gui import FlatDBGUI


def main():
    """Entry point and initializer for the Virtual Flat JSON Database Application."""
    try:
        root = tk.Tk()
        
        # Initialize the Tkinter GUI interface
        app = FlatDBGUI(root)
        
        # Start the Tkinter main event loop on the main thread
        root.mainloop()
    except Exception as e:
        print(f"Fatal Startup Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
