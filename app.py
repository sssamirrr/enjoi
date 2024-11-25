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
        # Define the scope and credentials
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )
        st.write("Credentials created successfully")
        
        gc = gspread.authorize(credentials)
        st.write("Authorization successful")
        
        # Open the spreadsheet by its key
        sheet_key = st.secrets["sheets"]["sheet_key"]
        st.write(f"Attempting to open sheet with key: {sheet_key}")
        
        spreadsheet = gc.open_by_key(sheet_key)
        st.write("Spreadsheet opened successfully")
        
        # List all worksheets
        worksheet_list = spreadsheet.worksheets()
        st.write(f"Available worksheets: {[ws.title for ws in worksheet_list]}")
        
        # Get the first worksheet
        worksheet = spreadsheet.get_worksheet(0)
        st.write(f"Accessed worksheet: {worksheet.title}")
        
        # Get all values
        data = worksheet.get_all_records()
        st.write(f"Retrieved {len(data)} records")
        
        return pd.DataFrame(data)
    
    except gspread.exceptions.APIError as e:
        st.error(f"API Error: {str(e)}")
        raise e
    except Exception as e:
        st.error(f"General Error: {str(e)}")
        raise e

# Load the data
try:
    df = get_google_sheet_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Title and description
st.title("🏨 Hotel Reservations Dashboard")
st.markdown("Real-time analysis of hotel reservations")

# Only proceed if we have data
if df is not None and not df.empty:
    # Create columns for filters
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_hotel = st.multiselect(
            "Select Hotel",
            options=sorted(df['Market'].unique()),
            default=sorted(df['Market'].unique())[0]
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

    # Filter data based on selections
    filtered_df = df.copy()

    if selected_hotel:
        filtered_df = filtered_df[filtered_df['Market'].isin(selected_hotel)]

    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date >= start_date) &
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date <= end_date)
        ]

    if selected_rate_codes:
        filtered_df = filtered_df[filtered_df['Rate Code Name'].isin(selected_rate_codes)]

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Reservations", len(filtered_df))
        
    with col2:
        avg_nights = filtered_df['# Nights'].mean()
        st.metric("Average Nights", f"{avg_nights:.1f}")
        
    with col3:
        total_nights = filtered_df['# Nights'].sum()
        st.metric("Total Room Nights", f"{total_nights:,.0f}")
        
    with col4:
        unique_guests = filtered_df['Name'].nunique()
        st.metric("Unique Guests", unique_guests)

    # Create two columns for charts
    col1, col2 = st.columns(2)

    with col1:
        # Reservations by Hotel
        fig_hotels = px.bar(
            filtered_df['Market'].value_counts().reset_index(),
            x='Market',
            y='count',
            title='Reservations by Hotel'
        )
        st.plotly_chart(fig_hotels, use_container_width=True)

    with col2:
        # Length of Stay Distribution
        fig_los = px.histogram(
            filtered_df,
            x='# Nights',
            title='Length of Stay Distribution'
        )
        st.plotly_chart(fig_los, use_container_width=True)

    # Additional charts
    col1, col2 = st.columns(2)

    with col1:
        # Rate Code Distribution
        fig_rate = px.pie(
            filtered_df,
            names='Rate Code Name',
            title='Rate Code Distribution'
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        # Arrivals by Date
        daily_arrivals = filtered_df['Arrival Date Short'].value_counts().sort_index()
        fig_arrivals = px.line(
            x=daily_arrivals.index,
            y=daily_arrivals.values,
            title='Arrivals by Date'
        )
        st.plotly_chart(fig_arrivals, use_container_width=True)

    # Show raw data
    with st.expander("Show Raw Data"):
        st.dataframe(filtered_df)
else:
    st.error("No data available to display")
