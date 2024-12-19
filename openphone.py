import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account

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

        # Add communication columns
        df['status'] = "Not Updated"
        df['last_date'] = None
        df['total_messages'] = 0
        df['total_calls'] = 0

        # Add Links for Logs
        df['Logs Link'] = df['Phone Number'].apply(
            lambda x: f"/?phone={x}"
        )

        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Detailed Logs Page
def detailed_logs_page(phone_number):
    st.title(f"Communication Logs for {phone_number}")

    # Dummy data for messages and calls (replace with API calls as needed)
    messages = [{"id": "msg1", "content": "Hello", "createdAt": "2024-12-01T10:00:00Z"}]
    calls = [{"id": "call1", "direction": "Outbound", "duration": 120, "createdAt": "2024-12-01T11:00:00Z"}]

    if messages:
        st.subheader("Messages")
        messages_df = pd.DataFrame([
            {
                "Message ID": msg["id"],
                "Content": msg["content"],
                "Created At": datetime.fromisoformat(msg["createdAt"].replace('Z', '+00:00'))
            }
            for msg in messages
        ])
        st.dataframe(messages_df)

    if calls:
        st.subheader("Calls")
        calls_df = pd.DataFrame([
            {
                "Call ID": call["id"],
                "Direction": call["direction"],
                "Duration (s)": call["duration"],
                "Created At": datetime.fromisoformat(call["createdAt"].replace('Z', '+00:00'))
            }
            for call in calls
        ])
        st.dataframe(calls_df)

    if not messages and not calls:
        st.warning("No communication logs found.")

# Main App Function
def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        # Display data editor with native link column
        st.subheader("Owner Data")
        st.data_editor(
            owner_df,
            column_config={
                "Logs Link": st.column_config.LinkColumn("View Logs", label="Logs Link"),
            },
            use_container_width=True,
        )

        # Handle query parameters for phone number
        query_params = st.query_params
        phone_number = query_params.get("phone")
        if phone_number:
            detailed_logs_page(phone_number[0])
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
