
import json
import os
import re
import shutil
import threading
from typing import Any, Dict, List, Tuple, Optional

# Thread locking per database file to prevent race conditions across background threads
_DB_LOCKS: Dict[str, threading.RLock] = {}
_GLOBAL_LOCK = threading.RLock()


def _get_db_lock(db_path: str) -> threading.RLock:
    """Retrieves or creates a thread-safe RLock for a specific database path."""
    abs_path = os.path.abspath(db_path)
    with _GLOBAL_LOCK:
        if abs_path not in _DB_LOCKS:
            _DB_LOCKS[abs_path] = threading.RLock()
        return _DB_LOCKS[abs_path]


# -------------------------------------------------------------------
# Type Validation & Sanitization Fallbacks
# -------------------------------------------------------------------

ALLOWED_TYPES = {"varchar", "char", "alphanumeric", "boolean"}


def validate_and_coerce_field(value: Any, data_type: str) -> Tuple[bool, Any]:
    """
    Validates a value against one of the 4 supported data types.
    Includes fallback sanitization/coercion if validation fails.
    
    Returns: (is_valid, final_value)
    """
    if data_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported data type: '{data_type}'. Must be one of {ALLOWED_TYPES}")

    if value is None:
        return True, None

    # 1. BOOLEAN
    if data_type == "boolean":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in ("true", "1", "yes", "y"):
                return True, True
            if val_lower in ("false", "0", "no", "n"):
                return True, False
        if isinstance(value, (int, float)):
            return True, bool(value)
        return False, False

    # Convert remaining string-based types to string first
    str_val = str(value)

    # 2. CHAR (Single character)
    if data_type == "char":
        if len(str_val) == 1:
            return True, str_val
        # Fallback coercion: truncate to first character if longer
        if len(str_val) > 1:
            return True, str_val[0]
        return False, ""

    # 3. ALPHANUMERIC (Letters and numbers only, no special chars or spaces)
    if data_type == "alphanumeric":
        if str_val.isalnum():
            return True, str_val
        # Fallback coercion: strip out non-alphanumeric characters
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', str_val)
        return False, sanitized

    # 4. VARCHAR (Any string)
    if data_type == "varchar":
        return True, str_val

    return False, str_val


# -------------------------------------------------------------------
# File I/O & Recovery Operations
# -------------------------------------------------------------------

def load_db(db_path: str) -> Dict[str, Any]:
    """
    Loads database file into memory using thread lock.
    Includes backup recovery fallback if original JSON is corrupted.
    """
    lock = _get_db_lock(db_path)
    with lock:
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file '{db_path}' does not exist.")

        backup_path = f"{db_path}.bak"

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _ensure_structure(data)
                return data
        except (json.JSONDecodeError, OSError) as primary_err:
            # Fallback Recovery: Attempt to read from .bak file if primary file is corrupted
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, 'r', encoding='utf-8') as bf:
                        backup_data = json.load(bf)
                        _ensure_structure(backup_data)
                        # Restore corrupted primary file from backup
                        save_db(db_path, backup_data)
                        return backup_data
                except Exception:
                    pass
            
            # If both fail or no backup exists, return empty safe state structure
            safe_default = {"schema": {}, "data": []}
            return safe_default


def save_db(db_path: str, data: Dict[str, Any]) -> None:
    """
    Saves database content atomically using a temporary file + atomic replace.
    Also manages a local .bak copy to prevent corruption on power/process failures.
    """
    lock = _get_db_lock(db_path)
    with lock:
        _ensure_structure(data)
        
        # Create a backup of the current database file before replacing
        backup_path = f"{db_path}.bak"
        if os.path.exists(db_path):
            try:
                shutil.copy2(db_path, backup_path)
            except OSError:
                pass

        # Atomic Write Pattern: Write to .tmp file first
        tmp_path = f"{db_path}.tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Force disk write
            
            # Atomic swap replacing target file
            os.replace(tmp_path, db_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise IOError(f"Failed to save database atomically: {e}")


def _ensure_structure(data: Dict[str, Any]) -> None:
    """Helper to verify data dictionary has valid schema and row list structure."""
    if not isinstance(data, dict):
        raise ValueError("Invalid database format: Root must be a JSON object.")
    if "schema" not in data or not isinstance(data["schema"], dict):
        data["schema"] = {}
    if "data" not in data or not isinstance(data["data"], list):
        data["data"] = []


# -------------------------------------------------------------------
# Schema & Column Manipulation APIs
# -------------------------------------------------------------------

def add_column(db_path: str, column_name: str, data_type: str, default_value: Any = None) -> Dict[str, Any]:
    """Adds a new column to the schema and updates all existing rows with default_value."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)
        column_name = column_name.strip()

        if not column_name:
            raise ValueError("Column name cannot be empty.")
        if column_name in db["schema"]:
            raise ValueError(f"Column '{column_name}' already exists.")
        if data_type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid data type '{data_type}'. Allowed: {ALLOWED_TYPES}")

        # Validate/coerce default value against type
        if default_value is not None:
            _, default_value = validate_and_coerce_field(default_value, data_type)

        # Update schema
        db["schema"][column_name] = data_type

        # Update existing rows
        for row in db["data"]:
            row[column_name] = default_value

        save_db(db_path, db)
        return db


def rename_column(db_path: str, old_column_name: str, new_column_name: str) -> Dict[str, Any]:
    """Renames an existing column across schema and all stored row entries."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)
        old_column_name = old_column_name.strip()
        new_column_name = new_column_name.strip()

        if old_column_name not in db["schema"]:
            raise ValueError(f"Column '{old_column_name}' does not exist.")
        if not new_column_name:
            raise ValueError("New column name cannot be empty.")
        if new_column_name in db["schema"] and new_column_name != old_column_name:
            raise ValueError(f"Column '{new_column_name}' already exists.")

        # Update schema key order
        data_type = db["schema"].pop(old_column_name)
        db["schema"][new_column_name] = data_type

        # Rename field across all rows
        for row in db["data"]:
            if old_column_name in row:
                row[new_column_name] = row.pop(old_column_name)

        save_db(db_path, db)
        return db


def delete_column(db_path: str, column_name: str) -> Dict[str, Any]:
    """Removes a column from the schema and deletes its values from all rows."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)
        column_name = column_name.strip()

        if column_name not in db["schema"]:
            raise ValueError(f"Column '{column_name}' does not exist.")

        del db["schema"][column_name]

        for row in db["data"]:
            row.pop(column_name, None)

        save_db(db_path, db)
        return db


# -------------------------------------------------------------------
# Row Manipulation APIs
# -------------------------------------------------------------------

def add_row(db_path: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and appends a new row record to the database."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)
        validated_row = {}

        # Ensure values for all defined schema columns
        for col_name, col_type in db["schema"].items():
            raw_val = row_data.get(col_name)
            _, final_val = validate_and_coerce_field(raw_val, col_type)
            validated_row[col_name] = final_val

        db["data"].append(validated_row)
        save_db(db_path, db)
        return db


def update_row(db_path: str, row_index: int, updated_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates fields of an existing row by row_index after validating input types."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)

        if row_index < 0 or row_index >= len(db["data"]):
            raise IndexError(f"Row index {row_index} is out of bounds.")

        target_row = db["data"][row_index]

        for col_name, col_type in db["schema"].items():
            if col_name in updated_data:
                raw_val = updated_data[col_name]
                _, final_val = validate_and_coerce_field(raw_val, col_type)
                target_row[col_name] = final_val

        save_db(db_path, db)
        return db


def delete_row(db_path: str, row_index: int) -> Dict[str, Any]:
    """Deletes a row record by its numerical index."""
    lock = _get_db_lock(db_path)
    with lock:
        db = load_db(db_path)

        if row_index < 0 or row_index >= len(db["data"]):
            raise IndexError(f"Row index {row_index} is out of bounds.")

        db["data"].pop(row_index)
        save_db(db_path, db)
        return db
