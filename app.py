import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import base64
from io import StringIO
import numpy as np

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for styling
st.markdown("""
    <style>
    .stDateInput {
        width: 100%;
    }
    div[data-baseweb="input"] {
        width: 100%;
    }
    .stDateInput > div {
        width: 100%;
    }
    div[data-baseweb="input"] > div {
        width: 100%;
    }
    .stDataFrame {
        width: 100%;
    }
    .dataframe-container {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

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
        return None

# Function to convert dataframe to CSV download link
def get_table_download_link(df, filename="data.csv", text="Download CSV"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Function to format phone numbers
def format_phone(phone):
    if pd.isna(phone):
        return ""
    phone_str = str(phone).replace("+1", "").replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if len(phone_str) == 10:
        return f"+1{phone_str}"
    return phone_str

# Load the data
df = get_google_sheet_data()

if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

# Create tabs
tab1, tab2 = st.tabs(["Dashboard", "Marketing"])

# Dashboard Tab
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")

    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_hotel = st.multiselect(
            "Select Hotel",
            options=sorted(df['Market'].unique()),
            default=[]
        )

    with col2:
        min_date = pd.to_datetime(df['Arrival Date Short']).min()
        max_date = pd.to_datetime(df['Arrival Date Short']).max()
        date_range = st.date_input(
            "Select Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    with col3:
        selected_rate_codes = st.multiselect(
            "Select Rate Codes",
            options=sorted(df['Rate Code Name'].unique()),
            default=[]
        )

    # Filter data
    filtered_df = df.copy()
    
    if selected_hotel:
        filtered_df = filtered_df[filtered_df['Market'].isin(selected_hotel)]
    
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date >= date_range[0]) &
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date <= date_range[1])
        ]
    
    if selected_rate_codes:
        filtered_df = filtered_df[filtered_df['Rate Code Name'].isin(selected_rate_codes)]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Reservations", len(filtered_df))
    with col2:
        st.metric("Average Nights", f"{filtered_df['# Nights'].mean():.1f}")
    with col3:
        st.metric("Total Room Nights", f"{filtered_df['# Nights'].sum():,.0f}")
    with col4:
        st.metric("Unique Guests", filtered_df['Name'].nunique())

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        fig_hotels = px.bar(
            filtered_df['Market'].value_counts().reset_index(),
            x='Market',
            y='count',
            title='Reservations by Hotel'
        )
        st.plotly_chart(fig_hotels, use_container_width=True)

    with col2:
        fig_los = px.histogram(
            filtered_df,
            x='# Nights',
            title='Length of Stay Distribution'
        )
        st.plotly_chart(fig_los, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig_rate = px.pie(
            filtered_df,
            names='Rate Code Name',
            title='Rate Code Distribution'
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        daily_arrivals = filtered_df['Arrival Date Short'].value_counts().sort_index()
        fig_arrivals = px.line(
            x=daily_arrivals.index,
            y=daily_arrivals.values,
            title='Arrivals by Date'
        )
        st.plotly_chart(fig_arrivals, use_container_width=True)

# Marketing Tab
with tab2:
    st.title("📊 Marketing Operations")
    st.markdown("Select guests for marketing campaigns")

    # Date range filters for check-in and check-out
    col1, col2 = st.columns(2)
    
    with col1:
        check_in_range = st.date_input(
            "Check-in Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="check_in_range"
        )
    
    with col2:
        check_out_range = st.date_input(
            "Check-out Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="check_out_range"
        )

    # Unpack date ranges
    check_in_start, check_in_end = check_in_range
    check_out_start, check_out_end = check_out_range

    # Resort filter
    selected_resorts = st.multiselect(
        "Select Hotels",
        options=sorted(df['Market'].unique()),
        default=sorted(df['Market'].unique())
    )

    # Filter by selected resorts
    resort_df = df[df['Market'].isin(selected_resorts)] if selected_resorts else df

    # Initialize select all in session state if not exists
    if 'select_all' not in st.session_state:
        st.session_state.select_all = False

    select_all = st.session_state.select_all

    try:
        display_df = resort_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
        
        # Convert phone numbers to strings
        display_df['Phone Number'] = display_df['Phone Number'].astype(str)
        
        # Convert dates with error handling
        display_df['Check In'] = pd.to_datetime(display_df['Check In'])
        display_df['Check Out'] = pd.to_datetime(display_df['Check Out'])
        
        # Apply filters with error handling
        mask = (
            (display_df['Check In'].dt.date >= check_in_start) &
            (display_df['Check In'].dt.date <= check_in_end) &
            (display_df['Check Out'].dt.date >= check_out_start) &
            (display_df['Check Out'].dt.date <= check_out_end)
        )
        display_df = display_df[mask]

        # Handle empty DataFrame
        if len(display_df) == 0:
            st.warning("No guests found for the selected date range.")
            display_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number'])
        else:
            # Add selection column at the beginning
            display_df.insert(0, 'Select', select_all)

        # Display table with error handling
        if not display_df.empty:
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select guest",
                        default=False,
                        width="small",
                    ),
                    "Guest Name": st.column_config.TextColumn(
                        "Guest Name",
                        help="Guest's full name",
                        width="medium",
                    ),
                    "Check In": st.column_config.DateColumn(
                        "Check In",
                        help="Check-in date",
                        width="medium",
                    ),
                    "Check Out": st.column_config.DateColumn(
                        "Check Out",
                        help="Check-out date",
                        width="medium",
                    ),
                    "Phone Number": st.column_config.TextColumn(
                        "Phone Number",
                        help="Guest's phone number",
                        width="medium",
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key="guest_editor"
            )

            # Display counter for selected guests
            selected_count = edited_df['Select'].sum()
            st.write(f"Selected Guests: {selected_count}")
            
            # Add Select/Deselect All button
            if st.button("Select/Deselect All"):
                # Toggle all selections
                current_state = edited_df['Select'].all()  # Check if all are currently selected
                edited_df['Select'] = not current_state  # Toggle to opposite state
                st.session_state.guest_editor = edited_df  # Update the session state
                st.rerun()  # Rerun the app to update the display

            # Export selected guests
            if st.button("Export Selected Guests"):
                selected_guests = edited_df[edited_df['Select']].copy()
                if len(selected_guests) > 0:
                    selected_guests['Phone Number'] = selected_guests['Phone Number'].apply(format_phone)
                    st.markdown(get_table_download_link(selected_guests.drop('Select', axis=1)), unsafe_allow_html=True)
                else:
                    st.warning("Please select at least one guest to export.")

        else:
            st.info("Please adjust the date filters to see guest data.")
            edited_df = display_df

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.stop()
