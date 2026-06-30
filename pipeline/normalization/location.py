from .country import normalize_country

def parse_location(loc_str: str | None) -> dict:
    """
    Parses location string to {city, region, country}
    """
    result = {"city": None, "region": None, "country": None}
    if not loc_str:
        return result
        
    parts = [p.strip() for p in loc_str.split(",") if p.strip()]
    if not parts:
        return result
        
    # Check if last part is a valid country
    country_code = normalize_country(parts[-1])
    if country_code:
        result["country"] = country_code
        parts.pop()
        
    if len(parts) >= 2:
        result["city"] = parts[0]
        result["region"] = parts[-1]
    elif len(parts) == 1:
        result["city"] = parts[0]
        
    # Infer country if missing
    if not result["country"]:
        if result["region"]:
            try:
                import pycountry
                subdivs = pycountry.subdivisions.search_fuzzy(result["region"])
                if subdivs:
                    result["country"] = subdivs[0].country_code
            except Exception:
                pass
        if not result["country"] and result["city"]:
            city_lower = result["city"].lower()
            if city_lower in ("chennai", "bangalore", "mumbai", "delhi", "hyderabad", "pune", "kolkata"):
                result["country"] = "IN"
                
    return result
