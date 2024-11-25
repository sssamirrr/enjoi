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
    st.title("📊 Marketing Information by Resort")
    
    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    
    st.subheader(f"Guest Information for {selected_resort}")

    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        check_in_filter = st.date_input(
            "Filter by Check In Date",
            value=(pd.to_datetime(resort_df['Arrival Date Short']).min().date(),
                  pd.to_datetime(resort_df['Arrival Date Short']).max().date()),
            key="check_in_filter"
        )
    with col2:
        check_out_filter = st.date_input(
            "Filter by Check Out Date",
            value=(pd.to_datetime(resort_df['Departure Date Short']).min().date(),
                  pd.to_datetime(resort_df['Departure Date Short']).max().date()),
            key="check_out_filter"
        )
    
    # Create display DataFrame
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
    if 'selected_rows' not in st.session_state:
        st.session_state.selected_rows = set()

    # Select/Deselect All button
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if st.button('Select/Deselect All'):
            if len(st.session_state.selected_rows) < len(display_df):
                st.session_state.selected_rows = set(display_df.index)
            else:
                st.session_state.selected_rows = set()

    # Add selection column
    display_df['Select'] = False

    # Style the table
    st.markdown("""
        <style>
        .stDataFrame {
            width: 100%;
        }
        .dataframe-container {
            margin-top: 1rem;
            margin-bottom: 1rem;
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
            ),
            "Guest Name": st.column_config.TextColumn("Guest Name", width="medium"),
            "Check In": st.column_config.DateColumn("Check In", width="medium"),
            "Check Out": st.column_config.DateColumn("Check Out", width="medium"),
            "Phone Number": st.column_config.TextColumn("Phone Number", width="medium"),
        },
        hide_index=True,
        width=None
    )

    # Update selections
    st.session_state.selected_rows = set(edited_df[edited_df['Select']].index)

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
    
    # Send button and selection info
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        if st.button('Send Messages to Selected Guests'):
            selected_guests = edited_df[edited_df['Select']]
            if len(selected_guests) > 0:
                st.success(f"Messages would be sent to {len(selected_guests)} guests")
            else:
                st.warning("Please select at least one guest")
    
    with col2:
        selected_count = len(edited_df[edited_df['Select']])
        st.info(f"Selected guests: {selected_count}")
    
    # Export functionality
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Guest List",
        csv,
        f"{selected_resort}_guest_list.csv",
        "text/csv",
        key='download-csv'
    )

# Raw data viewer
with st.expander("Show Raw Data"):
    st.dataframe(df)
