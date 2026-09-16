import re
import concurrent.futures
from typing import List, Dict, Any, Optional


def match_query(val: Any, query: str, case_sensitive: bool = False) -> bool:
    """
    Core string matching logic using standard Python string operations.
    Converts inputs safely to strings and performs substring checks with robust fallbacks.
    """
    try:
        if val is None or query is None:
            return False

        str_val = str(val)
        str_query = str(query)

        if not case_sensitive:
            str_val = str_val.lower()
            str_query = str_query.lower()

        return str_query in str_val
    except Exception:
        # Fallback for unexpected conversion errors
        try:
            return str(query).lower() in str(val).lower()
        except Exception:
            return False


def filter_by_type(val: Any, target_val: Any, data_type: str) -> bool:
    """
    Type-aware equality and pattern checking with safe fallbacks.
    """
    try:
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
            try:
                clean_val = re.sub(r'[^a-zA-Z0-9]', '', str_val)
                clean_target = re.sub(r'[^a-zA-Z0-9]', '', str_target)
            except Exception:
                clean_val = ''.join(c for c in str_val if c.isalnum())
                clean_target = ''.join(c for c in str_target if c.isalnum())
            return clean_target.lower() in clean_val.lower()

        # Default Varchar / Fallback
        return str_target.lower() in str_val.lower()
    except Exception:
        # Universal fallback for type filtering errors
        try:
            return str(target_val).lower() in str(val).lower()
        except Exception:
            return False


def search_records(
    records: List[Dict[str, Any]],
    query: str,
    target_column: Optional[str] = None,
    case_sensitive: bool = False
) -> List[Dict[str, Any]]:
    """
    Main search entry point. Filters rows based on substring match across
    a specific column or all available columns in each record.
    
    Includes multi-threaded execution for large datasets with a safe synchronous fallback.
    """
    if not records:
        return []
    if not query or not query.strip():
        return records

    clean_query = query.strip()

    def process_chunk(chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunk_results = []
        for record in chunk:
            if not isinstance(record, dict):
                continue
            if target_column and target_column != "All":
                field_val = record.get(target_column)
                if match_query(field_val, clean_query, case_sensitive):
                    chunk_results.append(record)
            else:
                for col_val in record.values():
                    if match_query(col_val, clean_query, case_sensitive):
                        chunk_results.append(record)
                        break
        return chunk_results

    # Multi-threading Strategy with Fallback
    try:
        if len(records) > 500:
            num_workers = min(4, len(records) // 100 + 1)
            chunk_size = max(1, len(records) // num_workers)
            chunks = [records[i:i + chunk_size] for i in range(0, len(records), chunk_size)]
            
            filtered_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_chunk, chunk) for chunk in chunks]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        filtered_results.extend(future.result())
                    except Exception:
                        pass
            return filtered_results
    except Exception:
        pass

    # Synchronous Fallback Execution
    filtered_results = []
    for record in records:
        if not isinstance(record, dict):
            continue

        if target_column and target_column != "All":
            field_val = record.get(target_column)
            if match_query(field_val, clean_query, case_sensitive):
                filtered_results.append(record)
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
    
    Includes multi-threaded execution for large datasets with a safe synchronous fallback.
    """
    if not records:
        return []
    if not column_name or value is None:
        return records

    def process_type_chunk(chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunk_matches = []
        for record in chunk:
            if column_name in record:
                row_val = record[column_name]
                if filter_by_type(row_val, value, data_type):
                    chunk_matches.append(record)
        return chunk_matches

    # Multi-threading Strategy with Fallback
    try:
        if len(records) > 500:
            num_workers = min(4, len(records) // 100 + 1)
            chunk_size = max(1, len(records) // num_workers)
            chunks = [records[i:i + chunk_size] for i in range(0, len(records), chunk_size)]
            
            matching_rows = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_type_chunk, chunk) for chunk in chunks]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        matching_rows.extend(future.result())
                    except Exception:
                        pass
            return matching_rows
    except Exception:
        pass

    # Synchronous Fallback
    matching_rows = []
    for record in records:
        if column_name in record:
            row_val = record[column_name]
            if filter_by_type(row_val, value, data_type):
                matching_rows.append(record)

    return matching_rows
