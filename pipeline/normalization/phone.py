import logging
import phonenumbers

def normalize_phone(phone_str: str, default_region: str = "IN") -> tuple[str | None, bool]:
    """
    Normalizes a phone number to E.164.
    Returns (normalized_number, is_assumed_region)
    """
    if not phone_str:
        return None, False
        
    cleaned = phone_str.strip()
    has_plus = cleaned.startswith('+')
    
    try:
        parsed = phonenumbers.parse(cleaned, default_region if not has_plus else None)
        if phonenumbers.is_valid_number(parsed):
            normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            is_assumed = not has_plus
            return normalized, is_assumed
    except Exception as e:
        logging.warning(f"Phone parsing failed for '{phone_str}': {e}")
        
    # Prepend '+' and try again
    if not has_plus:
        try:
            parsed = phonenumbers.parse("+" + cleaned, None)
            if phonenumbers.is_valid_number(parsed):
                normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                return normalized, False
        except Exception:
            pass
            
    logging.warning(f"Unable to normalize phone number to E.164: '{phone_str}'")
    return None, False
