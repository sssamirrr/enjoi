import http.client
import urllib.parse
import json

# Hard-coded Zillow Working API credentials via RapidAPI.
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def get_zestimate(full_address: str):
    """
    Given a full address string (e.g., "438 Vitoria Rd, Davenport, FL 33837"),
    this function:
      1. Validates the address by splitting on commas and checking that
         at least the street and city parts are non-empty.
      2. URL-encodes the full address.
      3. Calls the Zillow Working API (/byaddress endpoint).
      4. Parses the JSON response and returns the "zestimate" value.
         If the address is invalid or no value is found, returns None.
    
    Examples:
      - "438 Vitoria Rd, Davenport, FL 33837" → Valid (returns zestimate)
      - "Davenport, FL 33837" → Valid by our simple check (but you might want to refine this)
      - ", Davenport, FL 33837" → Invalid (empty street part), returns None
      - "438 Vitoria Rd, , FL 33837" → Invalid (empty city part), returns None
    """
    # Split the address on commas and trim whitespace.
    parts = [part.strip() for part in full_address.split(',')]
    
    # Require at least two non-empty parts (street and city)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        # The address is considered invalid
        return None

    # URL-encode the full address.
    encoded_address = urllib.parse.quote(full_address)

    # Create an HTTPS connection to the Zillow Working API.
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }
    
    # Build the request path using the encoded address.
    endpoint = f"/byaddress?propertyaddress={encoded_address}"
    
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        response_str = data.decode("utf-8")
        response_json = json.loads(response_str)
        # Return the zestimate value from the response.
        return response_json.get("zestimate", None)
    except Exception as e:
        print(f"Error retrieving zestimate for address '{full_address}': {e}")
        return None
    finally:
        conn.close()

# Example usage:
if __name__ == "__main__":
    # Example valid address.
    address_valid = "438 Vitoria Rd, Davenport, FL 33837"
    zestimate_valid = get_zestimate(address_valid)
    print(f"For '{address_valid}' -> Zestimate: {zestimate_valid}")

    # Example invalid address with empty street.
    address_invalid1 = ", Davenport, FL 33837"
    zestimate_invalid1 = get_zestimate(address_invalid1)
    print(f"For '{address_invalid1}' -> Zestimate: {zestimate_invalid1}")

    # Example invalid address with empty city.
    address_invalid2 = "438 Vitoria Rd, , FL 33837"
    zestimate_invalid2 = get_zestimate(address_invalid2)
    print(f"For '{address_invalid2}' -> Zestimate: {zestimate_invalid2}")
