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

# Create tabs for Dashboard and Marketing
tab1, tab2 = st.tabs(["Dashboard", "Marketing"])

with tab1:
    # Title and description
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")

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

    # Date filters in columns
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
    
    # Create a clean display DataFrame with the correct column names
    display_df = resort_df[[
        'Name',
        'Arrival Date Short',
        'Departure Date Short',
        'Phone Number'
    ]].copy()
    
    # Rename columns for display
    display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
    
    # Convert dates to datetime
    display_df['Check In'] = pd.to_datetime(display_df['Check In'])
    display_df['Check Out'] = pd.to_datetime(display_df['Check Out'])
    
    # Apply date filters
    mask = (
        (display_df['Check In'].dt.date >= check_in_filter[0]) &
        (display_df['Check In'].dt.date <= check_in_filter[1]) &
        (display_df['Check Out'].dt.date >= check_out_filter[0]) &
        (display_df['Check Out'].dt.date <= check_out_filter[1])
    )
    display_df = display_df[mask]

    # Add a selection column
    if 'selected_rows' not in st.session_state:
        st.session_state.selected_rows = set()

    # Select/Deselect All button
    if st.button('Select/Deselect All'):
        if len(st.session_state.selected_rows) < len(display_df):
            st.session_state.selected_rows = set(display_df.index)
        else:
            st.session_state.selected_rows = set()

    # Display the table with checkboxes
    st.write("Select guests to send messages:")
    
    # Create a wider display using custom CSS
    st.markdown("""
        <style>
        .stDataFrame {
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    # Display each row with a checkbox
    for idx, row in display_df.iterrows():
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            if st.checkbox('', key=f'check_{idx}', 
                          value=idx in st.session_state.selected_rows):
                st.session_state.selected_rows.add(idx)
            else:
                st.session_state.selected_rows.discard(idx)
        with col2:
            st.write(f"{row['Guest Name']} | Check In: {row['Check In'].date()} | "
                    f"Check Out: {row['Check Out'].date()} | {row['Phone Number']}")

    # Message selection and send button
    st.markdown("---")
    st.subheader("Send Message to Selected Guests")
    
    message_options = {
        "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
        "Check-in Follow-up": "We noticed you checked in last night. Please visit our concierge desk for your welcome gift! 🎁",
        "Checkout Message": "We hope you enjoyed your stay! Please visit our concierge desk before departure for a special gift! 🎁"
    }
    
    selected_message = st.selectbox(
        "Choose Message Template",
        options=list(message_options.keys())
    )
    
    if st.button('Send Messages to Selected Guests'):
        selected_guests = display_df.loc[list(st.session_state.selected_rows)]
        st.write(f"Message that would be sent to {len(selected_guests)} guests:")
        st.info(message_options[selected_message])
        # Here you would implement actual SMS sending logic
        st.success(f"Messages would be sent to {len(selected_guests)} guests")
        
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
    st.dataframe(df)
