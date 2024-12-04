
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for styling
st.markdown("""
    <style>
    .stDateInput {
        width: 100%;
    }
    .stTextInput, .stNumberInput {
        max-width: 200px;
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

# Create tabs
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

# Initialize session state for date filters
if 'check_in_start' not in st.session_state:
    st.session_state['check_in_start'] = None
if 'check_in_end' not in st.session_state:
    st.session_state['check_in_end'] = None
if 'check_out_start' not in st.session_state:
    st.session_state['check_out_start'] = None
if 'check_out_end' not in st.session_state:
    st.session_state['check_out_end'] = None
if 'refresh' not in st.session_state:
    st.session_state['refresh'] = False

with tab2:
    st.title("📊 Marketing Information by Resort")

    # Dynamically determine dataset date ranges
    dataset_min_date = pd.to_datetime(df['Arrival Date Short'], errors='coerce').min().date()
    dataset_max_date = pd.to_datetime(df['Departure Date Short'], errors='coerce').max().date()

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique()),
        key="selected_resort"
    )

    # Filter dataset for the selected resort
    resort_df = df[df['Market'] == selected_resort].copy()

    st.subheader(f"Guest Information for {selected_resort}")

    # Date filters with Reset button
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])

    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=st.session_state.get('check_in_start', dataset_min_date),
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_in_start"
        )
        check_in_end = st.date_input(
            "Check In Date (End)",
            value=st.session_state.get('check_in_end', dataset_max_date),
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_in_end"
        )
    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=st.session_state.get('check_out_start', dataset_min_date),
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_out_start"
        )
        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=st.session_state.get('check_out_end', dataset_max_date),
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_out_end"
        )
    with col3:
        if st.button("Reset Dates"):
            # Reset dates in session state
            st.session_state['check_in_start'] = dataset_min_date
            st.session_state['check_in_end'] = dataset_max_date
            st.session_state['check_out_start'] = dataset_min_date
            st.session_state['check_out_end'] = dataset_max_date
            st.session_state['refresh'] = True
            st.experimental_rerun()

    # Handle invalid date ranges
    if check_in_start > check_in_end:
        st.error("⚠️ Check-In Start Date cannot be after Check-In End Date.")
        st.stop()
    if check_out_start > check_out_end:
        st.error("⚠️ Check-Out Start Date cannot be after Check-Out End Date.")
        st.stop()

    # Apply filters to the dataset
    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

    if 'refresh' in st.session_state and st.session_state['refresh']:
        st.session_state['refresh'] = False
        filtered_df = resort_df[
            (resort_df['Check In'].dt.date >= dataset_min_date) &
            (resort_df['Check In'].dt.date <= dataset_max_date) &
            (resort_df['Check Out'].dt.date >= dataset_min_date) &
            (resort_df['Check Out'].dt.date <= dataset_max_date)
        ]
    else:
        filtered_df = resort_df[
            (resort_df['Check In'].dt.date >= check_in_start) &
            (resort_df['Check In'].dt.date <= check_in_end) &
            (resort_df['Check Out'].dt.date >= check_out_start) &
            (resort_df['Check Out'].dt.date <= check_out_end)
        ]

    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
    else:
        # Add the Select/Deselect All functionality
        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            select_all = st.checkbox(
                "Select/Deselect All",
                value=False,
                key="select_all"
            )

        # Prepare the display dataframe
        display_df = filtered_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
        display_df.rename(
            columns={
                'Name': 'Guest Name',
                'Arrival Date Short': 'Check In',
                'Departure Date Short': 'Check Out',
                'Phone Number': 'Phone Number'
            },
            inplace=True
        )

        # Add a Select column
        display_df.insert(0, 'Select', select_all)

        # Add a text message option column
        display_df['Send Text Message'] = False  # Default to False

        # Interactive data editor with the Select/Deselect and Text Message columns
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select or deselect this guest",
                    default=select_all,
                ),
                "Guest Name": st.column_config.TextColumn(
                    "Guest Name",
                    help="Guest's full name",
                ),
                "Check In": st.column_config.DateColumn(
                    "Check In",
                    help="Check-in date",
                ),
                "Check Out": st.column_config.DateColumn(
                    "Check Out",
                    help="Check-out date",
                ),
                "Phone Number": st.column_config.TextColumn(
                    "Phone Number",
                    help="Guest's phone number",
                ),
                "Send Text Message": st.column_config.CheckboxColumn(
                    "Send Text Message",
                    help="Send a text message to this guest",
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="data_editor"
        )

        # Display count of selected guests
        selected_count = edited_df['Select'].sum()
        st.write(f"Selected Guests: {selected_count}")

        # Display count of guests opted-in for text messages
        text_message_count = edited_df['Send Text Message'].sum()
        st.write(f"Guests Opted-In for Text Messages: {text_message_count}")


# Tour Prediction Tab
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    
    # Date range selection for tour prediction
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date for Tour Prediction", 
            value=pd.to_datetime(df['Arrival Date Short']).min().date()
        )
    with col2:
        end_date = st.date_input(
            "End Date for Tour Prediction", 
            value=pd.to_datetime(df['Arrival Date Short']).max().date()
        )

    # Prepare a DataFrame to collect all resort data
    all_resorts_tour_data = []
    
    for resort in df['Market'].unique():
        resort_df = df[df['Market'] == resort].copy()
        resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'])
        
        # Filter data within the selected date range
        filtered_resort_df = resort_df[
            (resort_df['Arrival Date Short'].dt.date >= start_date) & 
            (resort_df['Arrival Date Short'].dt.date <= end_date)
        ]
        
        # Daily Arrivals
        daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index()
        daily_arrivals.columns = ['Date', 'Arrivals']
        
        st.subheader(f"{resort}")
        
        # Conversion Rate Input
        conversion_rate = st.number_input(
            f"Conversion Rate for {resort} (%)", 
            min_value=0.0, 
            max_value=100.0, 
            value=10.0, 
            step=0.5,
            key=f"conversion_{resort}"
        ) / 100
        
        # Calculate Tours, rounded up using math.ceil
        daily_arrivals['Tours'] = daily_arrivals['Arrivals'].apply(
            lambda arrivals: math.floor(arrivals * conversion_rate)
        )
        
        st.dataframe(daily_arrivals)
        
        # Aggregate summaries for visualization later
        all_resorts_tour_data.append(daily_arrivals.assign(Market=resort))

    full_summary_df = pd.concat(all_resorts_tour_data)

    # Overall Summary
    st.markdown("---")
    st.subheader("Overall Tour Summary Across All Resorts")

    overall_summary = full_summary_df.groupby('Date').sum().reset_index()

    st.dataframe(overall_summary)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Arrivals for All Resorts", overall_summary['Arrivals'].sum())
    with col2:
        st.metric("Total Estimated Tours for All Resorts", overall_summary['Tours'].sum())

# Raw data viewer
with st.expander("Show Raw Data"):
    st.dataframe(df)
