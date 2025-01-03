def fetch_calls_for_last_100_contacts(phone_number_id):
    all_calls = []
    unique_contacts = set()
    next_page = None
    
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request("https://api.openphone.com/v1/calls",
                                    get_headers(), 
                                    params, 
                                    request_type='get')
        if not data or "data" not in data:
            break
        
        chunk = data["data"]
        for call_record in chunk:
            # Extract contact numbers
            contact_nums = get_contact_numbers_from_call(call_record)
            # Update our set of unique contacts
            unique_contacts.update(contact_nums)
            # Keep the call in our list
            all_calls.append(call_record)
            
            # If we've reached 100 unique contacts, we can stop
            if len(unique_contacts) >= 100:
                break
        
        if len(unique_contacts) >= 100:
            break
        
        next_page = data.get("nextPageToken")
        if not next_page:
            break
    
    return all_calls, unique_contacts
