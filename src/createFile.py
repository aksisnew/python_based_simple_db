import os
import re
import shutil
import json
import threading
from typing import List, Dict, Any, Union

# Lock authority strictly to the directory where the project is booted
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_FILE_LOCKS: Dict[str, threading.RLock] = {}
_GLOBAL_LOCK = threading.RLock()


def _get_path_lock(target_path: str) -> threading.RLock:
    """Retrieves or creates a thread-safe lock for a specific path with robust fallback."""
    try:
        abs_path = os.path.abspath(target_path)
    except Exception:
        abs_path = target_path
    
    with _GLOBAL_LOCK:
        try:
            if abs_path not in _FILE_LOCKS:
                _FILE_LOCKS[abs_path] = threading.RLock()
            return _FILE_LOCKS[abs_path]
        except Exception:
            return threading.RLock()


def _resolve_safe_path(relative_or_abs_path: str) -> str:
    """
    Enforces the boot-directory boundary.
    Prevents path traversal attacks (e.g. '../') outside the project root directory.
    """
    try:
        if not relative_or_abs_path:
            return PROJECT_ROOT

        clean_path = str(relative_or_abs_path).strip().lstrip('/\\')
        full_path = os.path.abspath(os.path.join(PROJECT_ROOT, clean_path))

        if not full_path.startswith(PROJECT_ROOT):
            raise PermissionError("Access denied: File operations restricted to the project root directory.")

        return full_path
    except PermissionError:
        raise
    except Exception:
        return PROJECT_ROOT


def _sanitize_name(name: str) -> str:
    """Removes invalid filename characters with robust fallback."""
    try:
        clean_name = str(name).strip()
        return re.sub(r'[\\/:*?"<>|]', '', clean_name)
    except Exception:
        try:
            clean_name = str(name).strip()
            forbidden = set('\\/:*?"<>|')
            return ''.join(c for c in clean_name if c not in forbidden)
        except Exception:
            return "unnamed_item"


# -------------------------------------------------------------------
# Sidebar Explorer / Directory Tree APIs
# -------------------------------------------------------------------

def list_directory_contents(rel_path: str = "") -> List[Dict[str, Any]]:
    """
    Recursively scans and lists files and folders within the project root.
    Returns a tree structure suitable for rendering in the GUI sidebar with robust fallbacks.
    """
    try:
        target_dir = _resolve_safe_path(rel_path)
    except Exception:
        return []

    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return []

    tree = []
    
    # Primary Method: os.scandir
    try:
        entries = sorted(os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            try:
                if entry.name.startswith('.') or entry.name == '__pycache__' or entry.name.endswith('.tmp'):
                    continue

                rel_item_path = os.path.relpath(entry.path, PROJECT_ROOT)

                if entry.is_dir():
                    tree.append({
                        "name": entry.name,
                        "rel_path": rel_item_path,
                        "type": "folder",
                        "children": list_directory_contents(rel_item_path)
                    })
                elif entry.is_file() and entry.name.lower().endswith('.json'):
                    tree.append({
                        "name": entry.name,
                        "rel_path": rel_item_path,
                        "type": "file"
                    })
            except Exception:
                continue
        return tree
    except Exception:
        pass

    # Fallback Method: os.listdir
    try:
        filenames = sorted(os.listdir(target_dir))
        for filename in filenames:
            try:
                if filename.startswith('.') or filename == '__pycache__' or filename.endswith('.tmp'):
                    continue
                
                full_item_path = os.path.join(target_dir, filename)
                rel_item_path = os.path.relpath(full_item_path, PROJECT_ROOT)

                if os.path.isdir(full_item_path):
                    tree.append({
                        "name": filename,
                        "rel_path": rel_item_path,
                        "type": "folder",
                        "children": list_directory_contents(rel_item_path)
                    })
                elif os.path.isfile(full_item_path) and filename.lower().endswith('.json'):
                    tree.append({
                        "name": filename,
                        "rel_path": rel_item_path,
                        "type": "file"
                    })
            except Exception:
                continue
        return tree
    except Exception:
        return []


# -------------------------------------------------------------------
# File & Folder Creation APIs
# -------------------------------------------------------------------

def create_file(file_name: str, parent_folder: str = "") -> str:
    """
    Creates a new JSON file in parent_folder (or root if parent_folder is empty).
    Initializes the file with an empty JSON object `{}` atomically using exclusive creation mode ('x') with fallbacks.
    """
    sanitized_name = _sanitize_name(file_name)
    if not sanitized_name.lower().endswith('.json'):
        sanitized_name += '.json'

    try:
        parent_path = _resolve_safe_path(parent_folder)
        target_filepath = os.path.join(parent_path, sanitized_name)
        _resolve_safe_path(target_filepath)
    except Exception as e:
        raise IOError(f"Invalid path configuration for file '{file_name}': {e}")

    lock = _get_path_lock(target_filepath)
    with lock:
        if os.path.exists(target_filepath):
            raise FileExistsError(f"File '{sanitized_name}' already exists.")

        # Primary Method: Atomic 'x' mode
        try:
            with open(target_filepath, 'x', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            return os.path.relpath(target_filepath, PROJECT_ROOT)
        except FileExistsError:
            raise FileExistsError(f"File '{sanitized_name}' already exists.")
        except Exception:
            pass

        # Fallback Method: 'w' mode with existence verification
        try:
            if os.path.exists(target_filepath):
                raise FileExistsError(f"File '{sanitized_name}' already exists.")
            with open(target_filepath, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            return os.path.relpath(target_filepath, PROJECT_ROOT)
        except Exception as e:
            if os.path.exists(target_filepath):
                try:
                    os.remove(target_filepath)
                except OSError:
                    pass
            raise IOError(f"Failed to create file '{sanitized_name}': {e}")


def create_folder(folder_name: str, parent_folder: str = "") -> str:
    """Creates a new subfolder within the project root scope with robust conflict and exception handling."""
    sanitized_name = _sanitize_name(folder_name)
    if not sanitized_name:
        raise ValueError("Folder name cannot be empty.")

    try:
        parent_path = _resolve_safe_path(parent_folder)
        target_folderpath = os.path.join(parent_path, sanitized_name)
        _resolve_safe_path(target_folderpath)
    except Exception as e:
        raise IOError(f"Invalid path configuration for folder '{folder_name}': {e}")

    lock = _get_path_lock(target_folderpath)
    with lock:
        if os.path.exists(target_folderpath):
            if os.path.isdir(target_folderpath):
                raise FileExistsError(f"Folder '{sanitized_name}' already exists.")
            else:
                raise FileExistsError(f"A file with the name '{sanitized_name}' already exists.")

        try:
            os.makedirs(target_folderpath, exist_ok=True)
            if not os.path.exists(target_folderpath):
                raise IOError("Directory creation verification failed.")
            return os.path.relpath(target_folderpath, PROJECT_ROOT)
        except Exception as e:
            raise IOError(f"Failed to create folder '{sanitized_name}': {e}")


# -------------------------------------------------------------------
# File & Folder Operations (Rename, Delete, Cut/Copy/Paste)
# -------------------------------------------------------------------

def rename_item(rel_path: str, new_name: str) -> str:
    """Renames a file or folder safely within the project scope with enhanced fallbacks and conflict checks."""
    try:
        old_path = _resolve_safe_path(rel_path)
    except Exception as e:
        raise FileNotFoundError(f"Source path could not be resolved: {e}")

    if not os.path.exists(old_path):
        raise FileNotFoundError("Target file or folder does not exist.")

    sanitized_name = _sanitize_name(new_name)
    if not sanitized_name:
        raise ValueError("New name cannot be empty.")

    if os.path.isfile(old_path) and not sanitized_name.lower().endswith('.json'):
        sanitized_name += '.json'

    parent_dir = os.path.dirname(old_path)
    new_path = os.path.join(parent_dir, sanitized_name)
    
    try:
        _resolve_safe_path(new_path)
    except Exception as e:
        raise PermissionError(f"Invalid target path: {e}")

    if os.path.exists(new_path) and old_path.lower() != new_path.lower():
        raise FileExistsError(f"An item named '{sanitized_name}' already exists in this folder.")

    lock = _get_path_lock(old_path)
    with lock:
        # Primary Rename Attempt: os.rename
        try:
            os.rename(old_path, new_path)
            if os.path.exists(new_path):
                return os.path.relpath(new_path, PROJECT_ROOT)
        except OSError:
            pass

        # Fallback 1: os.replace
        try:
            os.replace(old_path, new_path)
            if os.path.exists(new_path):
                return os.path.relpath(new_path, PROJECT_ROOT)
        except OSError:
            pass

        # Fallback 2: Copy and Delete (handles cross-device or persistent file locks)
        try:
            if os.path.isdir(old_path):
                shutil.copytree(old_path, new_path, dirs_exist_ok=True)
                shutil.rmtree(old_path)
            else:
                shutil.copy2(old_path, new_path)
                if os.path.exists(new_path) and os.path.getsize(new_path) == os.path.getsize(old_path):
                    os.remove(old_path)
                else:
                    raise IOError("Copy validation failed during fallback rename.")
            return os.path.relpath(new_path, PROJECT_ROOT)
        except Exception as e:
            if os.path.exists(new_path) and not os.path.exists(old_path):
                return os.path.relpath(new_path, PROJECT_ROOT)
            raise IOError(f"Could not rename '{rel_path}' to '{new_name}': {e}")


def delete_item(rel_path: str) -> None:
    """Deletes a file or directory recursively with robust exception handling and validation."""
    try:
        target_path = _resolve_safe_path(rel_path)
    except Exception as e:
        raise FileNotFoundError(f"Target path could not be resolved: {e}")

    if not os.path.exists(target_path):
        raise FileNotFoundError("Target does not exist.")

    if target_path == PROJECT_ROOT:
        raise PermissionError("Cannot delete the root project directory.")

    lock = _get_path_lock(target_path)
    with lock:
        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path, ignore_errors=False)
            else:
                os.remove(target_path)
            
            if os.path.exists(target_path):
                raise IOError("Deletion verification failed; target still exists.")
        except Exception as e:
            # Secondary retry attempt for deletion safety
            try:
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path, ignore_errors=True)
                else:
                    os.remove(target_path)
            except Exception:
                pass
            if os.path.exists(target_path):
                raise IOError(f"Failed to delete '{rel_path}': {e}")


def clipboard_operation(source_rel_path: str, target_folder_rel_path: str, action: str = "copy") -> str:
    """
    Handles Cut/Copy/Paste operations across folders in the project directory.
    action: "copy" or "cut"
    Includes robust error recovery, collision checks, and fallback mechanisms.
    """
    try:
        src_path = _resolve_safe_path(source_rel_path)
        dest_dir = _resolve_safe_path(target_folder_rel_path)
    except Exception as e:
        raise FileNotFoundError(f"Source or destination path could not be resolved: {e}")

    if not os.path.exists(src_path):
        raise FileNotFoundError("Source item does not exist.")
    if not os.path.isdir(dest_dir):
        raise NotADirectoryError("Destination must be a valid directory.")

    item_name = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, item_name)
    
    try:
        _resolve_safe_path(dest_path)
    except Exception as e:
        raise PermissionError(f"Invalid destination path: {e}")

    if os.path.exists(dest_path):
        if src_path.lower() == dest_path.lower():
            raise ValueError("Source and destination paths cannot be identical.")
        raise FileExistsError(f"An item named '{item_name}' already exists in the destination folder.")

    lock = _get_path_lock(src_path)
    with lock:
        try:
            if action == "copy":
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_path)
            elif action == "cut":
                try:
                    shutil.move(src_path, dest_path)
                except Exception:
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                        shutil.rmtree(src_path)
                    else:
                        shutil.copy2(src_path, dest_path)
                        os.remove(src_path)
            else:
                raise ValueError("Invalid action. Must be 'copy' or 'cut'.")

            if not os.path.exists(dest_path):
                raise IOError(f"Clipboard operation {action} failed to produce destination item.")

            return os.path.relpath(dest_path, PROJECT_ROOT)
        except Exception as e:
            if action == "copy" and os.path.exists(dest_path) and not os.path.isdir(dest_path) and os.path.getsize(dest_path) == 0:
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
            raise IOError(f"Failed to execute {action} operation: {e}")
