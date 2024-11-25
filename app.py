import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Create a connection to Google Sheets
@st.cache_resource
def get_google_sheet_data():
    try:
        # Use your Google Sheets credentials
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
        return None

# Load the data
df = get_google_sheet_data()

if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

# Create tabs
tab1, tab2 = st.tabs(["Dashboard", "Marketing"])

# Marketing Tab
with tab2:
    st.title("📊 Marketing Information by Resort")
    
    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    
    st.subheader(f"Guest Information for {selected_resort}")

    # Container for date filters
    date_filter_container = st.container()
    with date_filter_container:
        col1, col2 = st.columns(2)
        with col1:
            check_in_filter = st.date_input(
                "Filter by Check In Date",
                value=(datetime(2024, 11, 16), datetime(2024, 11, 22)),
                key="check_in_filter"
            )
        with col2:
            check_out_filter = st.date_input(
                "Filter by Check Out Date",
                value=(datetime(2024, 11, 23), datetime(2024, 11, 27)),
                key="check_out_filter"
            )

    # Add some spacing
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Create display DataFrame from the Google Sheets data
    display_df = resort_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
    display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
    
    # Convert dates
    display_df['Check In'] = pd.to_datetime(display_df['Check In'])
    display_df['Check Out'] = pd.to_datetime(display_df['Check Out'])
    
    # Apply filters
    mask = (
        (display_df['Check In'].dt.date >= check_in_filter[0]) &
        (display_df['Check In'].dt.date <= check_in_filter[1]) &
        (display_df['Check Out'].dt.date >= check_out_filter[0]) &
        (display_df['Check Out'].dt.date <= check_out_filter[1])
    )
    display_df = display_df[mask]

    # Initialize session state for selections
    if 'selected_guests' not in st.session_state:
        st.session_state.selected_guests = set()

    # Select/Deselect All button
    if st.button('Select/Deselect All'):
        if len(st.session_state.selected_guests) < len(display_df):
            st.session_state.selected_guests = set(range(len(display_df)))
        else:
            st.session_state.selected_guests = set()

    # Add selection column with current selections
    display_df['Select'] = [i in st.session_state.selected_guests for i in range(len(display_df))]

    # Custom CSS for table width
    st.markdown("""
        <style>
        .stDataFrame {
            max-width: 1000px !important;
            margin: auto;
        }
        </style>
    """, unsafe_allow_html=True)

    # Display table
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select guest",
                default=False,
                width="small"
            ),
            "Guest Name": st.column_config.TextColumn("Guest Name", width=200),
            "Check In": st.column_config.DateColumn("Check In", width=150),
            "Check Out": st.column_config.DateColumn("Check Out", width=150),
            "Phone Number": st.column_config.TextColumn("Phone Number", width=150),
        },
        hide_index=True,
        use_container_width=False
    )

    # Update selected guests based on checkbox changes
    st.session_state.selected_guests = set([i for i, row in edited_df.iterrows() if row['Select']])

    # Message section
    st.markdown("---")
    st.subheader("Message Templates")
    
    message_options = {
        "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
        "Check-in Follow-up": "We noticed you checked in last night. Please visit our concierge desk for your welcome gift! 🎁",
        "Checkout Message": "We hope you enjoyed your stay! Please visit our concierge desk before departure for a special gift! 🎁"
    }
    
    col1, col2 = st.columns([0.4, 0.6])
    with col1:
        selected_message = st.selectbox(
            "Choose Message Template",
            options=list(message_options.keys())
        )
    
    with col2:
        st.text_area(
            "Message Preview", 
            value=message_options[selected_message],
            height=100,
            disabled=True
        )
    
    # Export functionality
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Selected Guest List",
        csv,
        f"{selected_resort}_guest_list.csv",
        "text/csv",
        key='download-csv'
    )

# Dashboard Tab
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    # Add your dashboard content here using the loaded df

