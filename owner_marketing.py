import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import pgeocode  # For geocoding ZIP codes to latitude and longitude
import requests

# Define DEMO Mode
DEMO_MODE = True  # Set to False to enable live functionality

# Fetch Google Sheets Data
def get_owner_sheet_data():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )
        client = gspread.authorize(credentials)
        sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
        sheet = client.open_by_key(sheet_key)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()

        if not data:
            st.warning("The Google Sheet is empty.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Clean Data
        for col in ['Sale Date', 'Maturity Date']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Select'] = False  # Selection column
        df = df[['Select'] + [col for col in df.columns if col != 'Select']]  # Move Select to first column
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Fetch OpenPhone Data
def fetch_openphone_data(phone_number):
    OPENPHONE_API_KEY = st.secrets["openphone_api_key"]
    headers = {"Authorization": f"Bearer {OPENPHONE_API_KEY}"}
    url = "https://api.openphone.co/v1/calls"

    try:
        response = requests.get(url, headers=headers, params={"participants": [phone_number], "maxResults": 50})
        if response.status_code == 200:
            data = response.json().get("data", [])
            last_date = max([d.get('createdAt') for d in data], default="N/A")
            total_calls = sum(1 for d in data if d.get("type") == "call")
            total_messages = sum(1 for d in data if d.get("type") == "message")
            return {"Last Communication Date": last_date, "Total Calls": total_calls, "Total Messages": total_messages}
    except:
        return {"Last Communication Date": "Error", "Total Calls": 0, "Total Messages": 0}

# Display Map
def display_map(df):
    nomi = pgeocode.Nominatim('us')
    valid_zips = df['Zip Code'].dropna().unique()
    zip_data = nomi.query_postal_code(valid_zips)
    map_data = pd.DataFrame({'lat': zip_data['latitude'], 'lon': zip_data['longitude']}).dropna()
    if not map_data.empty:
        st.map(map_data)
    else:
        st.warning("No valid ZIP codes for visualization.")

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_states = st.multiselect("Select States", owner_df['State'].dropna().unique())
    with col2:
        date_range = st.date_input("Sale Date Range", [owner_df['Sale Date'].min(), owner_df['Sale Date'].max()])
    with col3:
        fico_range = st.slider("FICO Score", int(owner_df['Primary FICO'].min()), int(owner_df['Primary FICO'].max()), 
                               (int(owner_df['Primary FICO'].min()), int(owner_df['Primary FICO'].max())))

    # Apply Filters
    filtered_df = owner_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) &
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]
    filtered_df = filtered_df[(filtered_df['Primary FICO'] >= fico_range[0]) & (filtered_df['Primary FICO'] <= fico_range[1])]

    # Display Table with Checkboxes (Checkmarks on the Left)
    st.subheader("Owner Data")
    edited_df = st.data_editor(filtered_df, use_container_width=True, column_config={
        "Select": st.column_config.CheckboxColumn("Select")
    })

    # Show/Hide Map Toggle
    if st.toggle("Show/Hide Owner Locations Map"):
        display_map(filtered_df)

    # Update Communication Info
    selected_rows = edited_df[edited_df['Select']].index.tolist()
    if st.button("Update Communication Info"):
        if not selected_rows:
            st.warning("No rows selected!")
        else:
            with st.spinner("Fetching communication info..."):
                for idx in selected_rows:
                    phone_number = filtered_df.at[idx, "Phone Number"]
                    comm_data = fetch_openphone_data(phone_number)
                    for key, value in comm_data.items():
                        filtered_df.at[idx, key] = value
            st.success("Communication info updated!")
            st.dataframe(filtered_df)

    # Campaign Management
    st.subheader("Campaign Management")
    campaign_type = st.radio("Select Campaign Type", ["Text", "Email"])
    if campaign_type == "Text":
        message = st.text_area("Enter Text Message", "Welcome to our premium ownership program!")
    else:
        subject = st.text_input("Email Subject", "Welcome to Our Program")
        email_body = st.text_area("Email Body", "Dear Owner,\n\nWelcome to our exclusive community!")

    # Send Campaign
    if st.button("Send Campaign"):
        if not selected_rows:
            st.warning("No rows selected!")
        else:
            for idx in selected_rows:
                if campaign_type == "Text":
                    phone = filtered_df.at[idx, "Phone Number"]
                    st.write(f"Sent Text: '{message}' to {phone}")
                else:
                    email = filtered_df.at[idx, "Email"]
                    st.write(f"Sent Email: '{subject}' to {email}")
            st.success("Campaign Sent Successfully!")

# Run Minimal App
def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
