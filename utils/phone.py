import phonenumbers
from phonenumbers import NumberParseException

def normalize_to_e164(number, default_region='BR'):
    """
    Normalize a phone number to E.164 format.
    
    Args:
        number: Phone number string
        default_region: Default region code (e.g., 'BR' for Brazil)
    
    Returns:
        String with only digits including country code (e.g., '5511999999999')
    
    Raises:
        ValueError: If the number is invalid
    """
    if not number:
        raise ValueError("Phone number cannot be empty")
    
    # Remove common formatting characters
    number = number.strip()
    
    # If number doesn't start with +, try to parse with default region
    if not number.startswith('+'):
        try:
            parsed = phonenumbers.parse(number, default_region)
        except NumberParseException:
            # Try with + prefix
            try:
                parsed = phonenumbers.parse('+' + number, None)
            except NumberParseException as e:
                raise ValueError(f"Invalid phone number: {e}")
    else:
        try:
            parsed = phonenumbers.parse(number, None)
        except NumberParseException as e:
            raise ValueError(f"Invalid phone number: {e}")
    
    # Validate the number
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"Invalid phone number for region: {number}")
    
    # Format to E.164 and remove the '+' prefix
    e164_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return e164_number.lstrip('+')

def format_for_display(number, default_region='BR'):
    """
    Format a phone number for display.
    
    Args:
        number: Phone number string (E.164 or local format)
        default_region: Default region code
    
    Returns:
        Formatted phone number string for display
    """
    try:
        # Add '+' if it's E.164 without it
        if number and number[0].isdigit() and len(number) > 10:
            number = '+' + number
        
        parsed = phonenumbers.parse(number, default_region)
        
        # Use international format for display
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except (NumberParseException, AttributeError):
        return number  # Return original if parsing fails