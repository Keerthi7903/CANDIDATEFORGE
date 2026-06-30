import logging
from dateutil import parser as date_parser

def normalize_date(date_str: str | None) -> str | None:
    """
    Parses various date formats to YYYY-MM.
    Returns None if date represents current/present or is invalid.
    """
    if not date_str:
        return None
        
    cleaned = date_str.strip().lower()
    if cleaned in ("present", "current", "now", "ongoing"):
        return None
        
    try:
        parsed = date_parser.parse(date_str)
        return parsed.strftime("%Y-%m")
    except Exception as e:
        logging.warning(f"Failed to parse date '{date_str}': {e}")
        return None
