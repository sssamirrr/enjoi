import http.client
import urllib.parse
import json
import time

# Hard-coded Zillow Working API credentials (via RapidAPI)
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def get_zestimate(full_address: str, max_retries: int = 3, sleep_sec: float = 0.20):
    """
    Given a full address string (e.g., "2823 NE 9th St, Gainesville, 32609"),
    this function:
      1. Validates the address by ensuring that:
         - The street portion (the text before the first comma) is not empty.
         - There is at least one additional non-empty part (city or zip code).
      2. URL-encodes the full address.
      3. Calls the Zillow Working API (/byaddress endpoint).
      4. Parses the JSON response and returns the "zestimate" value.
         If the address is invalid or no value is found, returns None.
      5. Retries up to 'max_retries' times if no zestimate is found
         or if an exception occurs.

    Debugging enhancements:
      - Prints the request endpoint and response status.
      - Prints the raw response from the API.
      - Adds a simple retry mechanism to reduce transient empty returns.
    """
    # 1) Input Validation
    parts = [part.strip() for part in full_address.split(',')]
    # The street portion (first part) is not empty.
    if not parts[0]:
        print(f"[DEBUG] Address validation failed: street is empty. ({full_address})")
        return None
    # There must be at least one additional non-empty part (city or zip).
    if len(parts) < 2 or not any(parts[1:]):
        print(f"[DEBUG] Address validation failed: no city/zip. ({full_address})")
        return None
    
    # 2) URL-encode the full address
    encoded_address = urllib.parse.quote(full_address)
    endpoint = f"/byaddress?propertyaddress={encoded_address}"
    
    # 3) Make up to 'max_retries' attempts
    for attempt in range(1, max_retries + 1):
        try:
            # Sleep to respect rate limit
            time.sleep(sleep_sec)
            
            print(f"[DEBUG] Attempt {attempt}/{max_retries} -> Requesting: {endpoint}")
            
            # Create connection
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
            headers = {
                'x-rapidapi-key': RAPIDAPI_KEY,
                'x-rapidapi-host': RAPIDAPI_HOST
            }
            
            conn.request("GET", endpoint, headers=headers)
            res = conn.getresponse()
            status_code = res.status
            
            # 4) Check response status code
            print(f"[DEBUG] HTTP Response Status: {status_code}")
            data = res.read()
            response_str = data.decode("utf-8")
            
            # Print the raw response for debugging
            print(f"[DEBUG] Raw API response: {response_str[:500]}...")  # truncate if very long
            
            # Close the connection
            conn.close()
            
            # 5) Parse JSON and retrieve "zestimate"
            if status_code == 200:
                response_json = json.loads(response_str)
                zestimate_value = response_json.get("zestimate", None)
                
                # If we found a zestimate, return it
                if zestimate_value is not None:
                    print(f"[DEBUG] Found zestimate: {zestimate_value}")
                    return zestimate_value
                else:
                    print("[DEBUG] No 'zestimate' key found in JSON. Will retry." if attempt < max_retries else "[DEBUG] No 'zestimate' key found. No more retries.")
            else:
                print(f"[DEBUG] Non-200 status ({status_code}). Will retry." if attempt < max_retries else "[DEBUG] Non-200 status. No more retries.")
            
        except Exception as e:
            # Print exception and maybe retry
            print(f"[DEBUG] Exception occurred: {e}")
            if attempt < max_retries:
                print("[DEBUG] Will retry...")
            else:
                print("[DEBUG] No more retries left.")
    
    # If all attempts fail or we never got a zestimate
    return None

# Example usage:
if __name__ == "__main__":
    # Test address known to have a valid zestimate
    test_address = "2823 NE 9th St, Gainesville, 32609"
    zestimate = get_zestimate(test_address)
    print(f"[RESULT] For address: '{test_address}' -> Zestimate: {zestimate}")
