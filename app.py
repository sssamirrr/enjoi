import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import pandas as pd

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Create a connection to Google Sheets
@st.cache_resource
def get_google_sheet_data():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )
        
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        raise e

# Load the data
try:
    df = get_google_sheet_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Let's check the column names
st.write("Available columns:", df.columns.tolist())

# Create tabs for Dashboard and Marketing
tab1, tab2 = st.tabs(["Dashboard", "Marketing"])

with tab1:
    # [Previous dashboard code remains the same until the Marketing tab]
    # ... [Keep all the dashboard code as is] ...

with tab2:
    st.title("📊 Marketing Information by Resort")
    
    # Select resort
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Filter data for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    
    # Display guest information
    st.subheader(f"Guest Information for {selected_resort}")
    
    # Create a clean display DataFrame with the actual column names from your sheet
    # Modify these column names to match your actual Google Sheet column names
    display_df = resort_df[[
        'Guest Name',  # Update this to match your actual column name for guest name
        'Check In',    # Update this to match your actual column name for check in
        'Check Out',   # Update this to match your actual column name for check out
        'Phone Number' # Update this to match your actual column name for phone
    ]].copy()
    
    # Sort by check-in date
    display_df['Check In'] = pd.to_datetime(display_df['Check In'])
    display_df = display_df.sort_values('Check In')
    
    # Display the table
    st.dataframe(
        display_df,
        column_config={
            "Guest Name": st.column_config.TextColumn("Guest Name"),
            "Check In": st.column_config.DateColumn("Check In"),
            "Check Out": st.column_config.DateColumn("Check Out"),
            "Phone Number": st.column_config.TextColumn("Phone Number"),
        },
        hide_index=True,
    )
    
    # Add export functionality
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Guest List",
        csv,
        f"{selected_resort}_guest_list.csv",
        "text/csv",
        key='download-csv'
    )

# Show raw data at the bottom of both tabs
with st.expander("Show Raw Data"):
    st.dataframe(df
