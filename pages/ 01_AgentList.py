# pages/01_AgentList.py
import streamlit as st
import pandas as pd
from communication import OPENPHONE_API_KEY, rate_limited_request

def get_phone_numbers():
    """Fetch phone-numbers from OpenPhone (up to however many you have)."""
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer '
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {}, request_type='get')
    if not data or "data" not in data:
        return []

    # Extract phoneNumberId & phoneNumber
    results = []
    for pn in data["data"]:
        results.append({
            "phoneNumberId": pn.get("id"),
            "phoneNumber": pn.get("phoneNumber") or "None"
        })
    return results

def main():
    st.title("Agent List Page")

    phone_numbers = get_phone_numbers()
    if not phone_numbers:
        st.warning("No phone numbers found in OpenPhone.")
        return

    rows = []
    for pn in phone_numbers:
        pid = pn["phoneNumberId"]
        phone_str = pn["phoneNumber"]

        # Build a link to page 2 with ?phoneNumberId=PID
        # Using relative link: "02_AgentDetail?phoneNumberId=PID"
        # target="_self" => open in same tab
        link_html = f'<a href="02_AgentDetail?phoneNumberId={pid}" target="_self">View History</a>'

        rows.append({
            "Phone Number": phone_str,
            "Details": link_html
        })

    df = pd.DataFrame(rows)
    # Render HTML with clickable <a>
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
