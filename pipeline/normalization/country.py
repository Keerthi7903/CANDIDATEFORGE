import logging
import pycountry

def normalize_country(country_str: str | None) -> str | None:
    if not country_str:
        return None
        
    cleaned = country_str.strip()
    if len(cleaned) == 2:
        try:
            c = pycountry.countries.get(alpha_2=cleaned.upper())
            if c:
                return c.alpha_2
        except Exception:
            pass
            
    try:
        results = pycountry.countries.search_fuzzy(cleaned)
        if results:
            return results[0].alpha_2
    except Exception as e:
        logging.warning(f"Country search failed for '{country_str}': {e}")
        
    return None
