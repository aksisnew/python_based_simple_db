import re
from typing import List, Dict, Any, Optional


def match_query(val: Any, query: str, case_sensitive: bool = False) -> bool:
    """
    Core string matching logic using standard Python string operations.
    Converts inputs safely to strings and performs substring checks.
    """
    if val is None or query is None:
        return False

    str_val = str(val)
    str_query = str(query)

    if not case_sensitive:
        str_val = str_val.lower()
        str_query = str_query.lower()

    return str_query in str_val


def filter_by_type(val: Any, target_val: Any, data_type: str) -> bool:
    """
    Type-aware equality and pattern checking with safe fallbacks.
    """
    if val is None:
        return False

    # 1. BOOLEAN MATCHING
    if data_type == "boolean":
        bool_val = bool(val)
        if isinstance(target_val, bool):
            return bool_val == target_val
        if isinstance(target_val, str):
            clean_target = target_val.strip().lower()
            if clean_target in ("true", "1", "yes"):
                return bool_val is True
            if clean_target in ("false", "0", "no"):
                return bool_val is False
        return False

    # 2. CHAR / ALPHANUMERIC / VARCHAR MATCHING
    str_val = str(val)
    str_target = str(target_val)

    if data_type == "char":
        return str_val == str_target

    if data_type == "alphanumeric":
        clean_val = re.sub(r'[^a-zA-Z0-9]', '', str_val)
        clean_target = re.sub(r'[^a-zA-Z0-9]', '', str_target)
        return clean_target.lower() in clean_val.lower()

    # Default Varchar / Fallback
    return str_target.lower() in str_val.lower()


def search_records(
    records: List[Dict[str, Any]],
    query: str,
    target_column: Optional[str] = None,
    case_sensitive: bool = False
) -> List[Dict[str, Any]]:
    """
    Main search entry point. Filters rows based on substring match across
    a specific column or all available columns in each record.
    
    Safe Fallback: Handles missing key fields or non-string inputs cleanly without crashing.
    """
    if not query or not query.strip():
        return records

    clean_query = query.strip()
    filtered_results = []

    for record in records:
        if not isinstance(record, dict):
            continue

        # Targeted Column Search
        if target_column and target_column != "All":
            field_val = record.get(target_column)
            if match_query(field_val, clean_query, case_sensitive):
                filtered_results.append(record)
        # Search Across All Columns
        else:
            for col_val in record.values():
                if match_query(col_val, clean_query, case_sensitive):
                    filtered_results.append(record)
                    break

    return filtered_results


def advanced_type_search(
    records: List[Dict[str, Any]],
    column_name: str,
    value: Any,
    data_type: str
) -> List[Dict[str, Any]]:
    """
    Filters database records using strict type matching for specific schema types.
    """
    if not column_name or value is None:
        return records

    matching_rows = []
    for record in records:
        if column_name in record:
            row_val = record[column_name]
            if filter_by_type(row_val, value, data_type):
                matching_rows.append(record)

    return matching_rows
