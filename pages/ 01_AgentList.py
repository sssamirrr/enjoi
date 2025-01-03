# pages/01_AgentList.py
import streamlit as st
import pandas as pd
from urllib.parse import urlencode

# Import from communication.py
from communication import OPENPHONE_API_KEY, rate_limited_request

def get_phone_numbers():
    """Fetch all phone numbers from OpenPhone."""
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # No 'Bearer ' prefix
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {}, request_type='get')
    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        results.append({
            "phoneNumberId": pn.get("id"),
            "phoneNumber": pn.get("phoneNumber") or "None",
        })
    return results

def main():
    st.title("1) Agent List Page")

    phone_numbers = get_phone_numbers()
    if not phone_numbers:
        st.warning("No phone numbers found in OpenPhone.")
        return

    # Build a table with clickable links to ?page=02_AgentDetail
    rows = []
    for item in phone_numbers:
        pid = item["phoneNumberId"]
        phone_str = item["phoneNumber"]

        # Build the query string for page=02_AgentDetail & phoneNumberId=pid
        link_params = {"page": "02_AgentDetail", "phoneNumberId": pid}
        link_html = f'<a href="?{urlencode(link_params)}" target="_self">View History</a>'

        rows.append({
            "Phone Number": phone_str,
            "Details": link_html
        })

    df = pd.DataFrame(rows)
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
