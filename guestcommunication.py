def rate_limited_request(url, headers, params, request_type='get', max_retries=5):
    """
    Makes an API request with rate-limiting and exponential backoff on rate limit errors.
    """
    retries = 0
    delay = 1  # Initial delay in seconds

    while retries < max_retries:
        try:
            if request_type == 'get':
                response = requests.get(url, headers=headers, params=params)
            else:
                response = None

            # Check if the response is successful
            if response and response.status_code == 200:
                return response.json()

            # If rate limit is hit (status code 429), wait and retry
            if response and response.status_code == 429:
                st.warning(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay *= 2  # Exponential backoff
                continue

            # For other non-200 errors, display the error and stop
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
            break
        except Exception as e:
            st.warning(f"Exception during request: {str(e)}")
            break

    # Return None if all retries fail
    return None
