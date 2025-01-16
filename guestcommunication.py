import streamlit as st
import pandas as pd
from datetime import datetime

def load_guest_communication_data():
    """
    Example function that returns a static Pandas DataFrame 
    representing some 'guest communication' data.
    
    In a real application, you might load this from a CSV, database, 
    or an API call.
    """
    data = {
        "Guest Name": ["Alice Johnson", "Bob Smith", "Charlie Davis"],
        "Room #": [101, 202, 303],
        "Phone": ["+14155550101", "+14155550202", "+14155550303"],
        "Email": ["alice@example.com", "bob@example.com", "charlie@example.com"],
        "Status": ["Confirmed", "Potential", "Follow-up Needed"],
        "Last Contact": [
            datetime(2025, 1, 10, 14, 30).strftime("%Y-%m-%d %H:%M"),
            datetime(2025, 1, 12, 9, 15).strftime("%Y-%m-%d %H:%M"),
            datetime(2025, 1, 15, 18, 0).strftime("%Y-%m-%d %H:%M")
        ],
    }
    df = pd.DataFrame(data)
    return df


def run_guest_status_tab():
    """
    Renders the 'Add Guest Status' tab in your main app.
    """
    st.subheader("Manage Guest Communication & Status")
    
    # Some instructions to the user
    st.write("""
        Below is an example guest communication table. 
        You can expand this functionality to load real data, 
        update statuses, or filter by last contact date.
    """)

    # Load or generate your data
    guest_df = load_guest_communication_data()

    # Display the data
    st.dataframe(guest_df)

    st.write("---")
    st.write("**Update or Edit Guest Status**")
    # Provide a simple way to pick a guest and change status
    guest_names = guest_df["Guest Name"].unique().tolist()
    selected_guest = st.selectbox("Select Guest", guest_names)

    new_status = st.text_input("New Status for Selected Guest", "")
    if st.button("Update Status"):
        # In a real application, you'd do something like 
        # a database write or an API call here.
        st.success(f"Status for **{selected_guest}** updated to **{new_status}** (simulation).")
