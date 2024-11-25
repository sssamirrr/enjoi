import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

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

# Load the data
df = get_google_sheet_data()

if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])


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
    st.title("📊 Marketing Information by Resort")
    
    # Initialize session state for dates
    if 'check_in_start' not in st.session_state:
        st.session_state.check_in_start = datetime(2024, 11, 16).date()
    if 'check_in_end' not in st.session_state:
        st.session_state.check_in_end = datetime(2024, 11, 22).date()
    if 'check_out_start' not in st.session_state:
        st.session_state.check_out_start = datetime(2024, 11, 23).date()
    if 'check_out_end' not in st.session_state:
        st.session_state.check_out_end = datetime(2024, 11, 27).date()
    
    # Initialize session state for select all
    if 'select_all_state' not in st.session_state:
        st.session_state.select_all_state = False

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    
    st.subheader(f"Guest Information for {selected_resort}")

    # Date filters container
    date_filter_container = st.container()
    with date_filter_container:
        col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
        
        with col1:
            check_in_start = st.date_input(
                "Check In Date (Start)",
                value=st.session_state.check_in_start,
                key="check_in_start_input"
            )
            check_in_end = st.date_input(
                "Check In Date (End)",
                value=st.session_state.check_in_end,
                key="check_in_end_input"
            )
        
        with col2:
            check_out_start = st.date_input(
                "Check Out Date (Start)",
                value=st.session_state.check_out_start,
                key="check_out_start_input"
            )
            check_out_end = st.date_input(
                "Check Out Date (End)",
                value=st.session_state.check_out_end,
                key="check_out_end_input"
            )
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button('Reset Dates'):
                # Reset date session states
                st.session_state.check_in_start = datetime(2024, 11, 16).date()
                st.session_state.check_in_end = datetime(2024, 11, 22).date()
                st.session_state.check_out_start = datetime(2024, 11, 23).date()
                st.session_state.check_out_end = datetime(2024, 11, 27).date()
                st.rerun()

    try:
        # Prepare display dataframe
        display_df = resort_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
        
        # Data type conversions and error handling
        display_df['Phone Number'] = display_df['Phone Number'].astype(str)
        display_df['Check In'] = pd.to_datetime(display_df['Check In'], errors='coerce')
        display_df['Check Out'] = pd.to_datetime(display_df['Check Out'], errors='coerce')
        
        # Drop rows with invalid dates
        display_df = display_df.dropna(subset=['Check In', 'Check Out'])
        
        # Apply date filters
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
        
        # Add Select column with current select all state
        display_df.insert(0, 'Select', st.session_state.select_all_state)

        # Display table
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

            # Select/Deselect All button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Select All", key="select_all"):
                    st.session_state.select_all_state = True
                    st.rerun()
            
            with col2:
                if st.button("Deselect All", key="deselect_all"):
                    st.session_state.select_all_state = False
                    st.rerun()

        else:
            st.info("Please adjust the date filters to see guest data.")
            edited_df = display_df

    except Exception as e:
        st.error("An error occurred while processing the data.")
        st.exception(e)
        edited_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number'])

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
    if not edited_df.empty:
        # Filter only selected guests
        selected_guests = edited_df[edited_df['Select']]
        
        if not selected_guests.empty:
            csv = selected_guests.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Selected Guest List",
                csv,
                f"{selected_resort}_guest_list.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning("No guests selected for download.")

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

# (Keep all your previous imports and initial setup)

# Create tabs
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

# (Keep your existing Dashboard and Marketing tabs)

# Tour Prediction Tab
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    
    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.to_datetime(df['Arrival Date Short']).min().date())
    with col2:
        end_date = st.date_input("End Date", value=pd.to_datetime(df['Arrival Date Short']).max().date())
    
    # Filter data for selected resort and date range
    resort_df = df[df['Market'] == selected_resort].copy()
    resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'])
    filtered_resort_df = resort_df[
        (resort_df['Arrival Date Short'].dt.date >= start_date) & 
        (resort_df['Arrival Date Short'].dt.date <= end_date)
    ]
    
    # Daily Arrivals
    daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index()
    daily_arrivals.columns = ['Date', 'Arrivals']
    
    # Conversion Rate Input
    conversion_rate = st.number_input(
        f"Conversion Rate for {selected_resort} (%)", 
        min_value=0.0, 
        max_value=100.0, 
        value=10.0, 
        step=0.5
    ) / 100
    
    # Calculate Tours
    daily_arrivals['Tours'] = (daily_arrivals['Arrivals'] * conversion_rate).apply(lambda x: round(x))
    
    # Display Daily Arrivals and Tours
    st.subheader(f"Arrivals and Tours for {selected_resort}")
    results_df = daily_arrivals.copy()
    results_df['Date'] = results_df['Date'].astype(str)
    
    # Editable data editor for manual tour adjustments
    edited_results = st.data_editor(
        results_df, 
        column_config={
            "Date": st.column_config.TextColumn("Date"),
            "Arrivals": st.column_config.NumberColumn("Arrivals", disabled=True),
            "Tours": st.column_config.NumberColumn("Tours", help="Calculated or manually adjusted tours")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Arrivals", filtered_resort_df.shape[0])
    with col2:
        st.metric("Estimated Tours", edited_results['Tours'].sum())
    with col3:
        st.metric("Average Daily Tours", edited_results['Tours'].mean())
    
    # Visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Arrivals Chart
        fig_arrivals = px.bar(
            edited_results, 
            x='Date', 
            y='Arrivals', 
            title=f'Daily Arrivals - {selected_resort}'
        )
        st.plotly_chart(fig_arrivals, use_container_width=True)
    
    with col2:
        # Tours Chart
        fig_tours = px.bar(
            edited_results, 
            x='Date', 
            y='Tours', 
            title=f'Estimated Tours - {selected_resort}'
        )
        st.plotly_chart(fig_tours, use_container_width=True)
    
    # Comprehensive Resort and Overall Tour Summary
    st.markdown("---")
    st.subheader("Resort and Overall Tour Summary")
    
    # Prepare summary for all resorts
    all_resort_summary = []
    
    for resort in sorted(df['Market'].unique()):
        # Filter data for each resort
        resort_data = df[df['Market'] == resort].copy()
        resort_data['Arrival Date Short'] = pd.to_datetime(resort_data['Arrival Date Short'])
        filtered_data = resort_data[
            (resort_data['Arrival Date Short'].dt.date >= start_date) & 
            (resort_data['Arrival Date Short'].dt.date <= end_date)
        ]
        
        # Calculate resort-specific summary
        daily_resort_arrivals = filtered_data.groupby(filtered_data['Arrival Date Short'].dt.date).size().reset_index()
        daily_resort_arrivals.columns = ['Date', 'Arrivals']
        
        # Use a default conversion rate if not specified (you might want to store this in a configuration)
        resort_conversion_rate = 0.1  # 10% default
        
        daily_resort_arrivals['Tours'] = (daily_resort_arrivals['Arrivals'] * resort_conversion_rate).apply(lambda x: round(x))
        
        resort_summary = {
            'Resort': resort,
            'Total Arrivals': filtered_data.shape[0],
            'Total Tours': daily_resort_arrivals['Tours'].sum(),
            'Average Daily Tours': daily_resort_arrivals['Tours'].mean()
        }
        
        all_resort_summary.append(resort_summary)
    
    # Convert summary to DataFrame and display
    summary_df = pd.DataFrame(all_resort_summary)
    st.dataframe(summary_df, use_container_width=True)
    
    # Overall Totals
    st.subheader("Overall Totals")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Arrivals Across Resorts", summary_df['Total Arrivals'].sum())
    with col2:
        st.metric("Total Estimated Tours", summary_df['Total Tours'].sum())
    with col3:
        st.metric("Average Daily Tours Across Resorts", summary_df['Average Daily Tours'].mean())

# Raw data viewer
with st.expander("Show Raw Data"):
    st.dataframe(df)


# Raw data viewer (removed duplicate expander)
with st.expander("Show Raw Data"):
    st.dataframe(df)
