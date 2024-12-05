
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

# Initialize session state for dates
if 'check_in_start' not in st.session_state or st.session_state['check_in_start'] is None:
    st.session_state['check_in_start'] = datetime(2024, 11, 16).date()
if 'check_in_end' not in st.session_state or st.session_state['check_in_end'] is None:
    st.session_state['check_in_end'] = datetime(2024, 11, 22).date()
if 'check_out_start' not in st.session_state or st.session_state['check_out_start'] is None:
    st.session_state['check_out_start'] = datetime(2024, 11, 23).date()
if 'check_out_end' not in st.session_state or st.session_state['check_out_end'] is None:
    st.session_state['check_out_end'] = datetime(2024, 11, 27).date()

# Initialize session state for dates and select all state
if 'check_in_start' not in st.session_state or st.session_state['check_in_start'] is None:
    st.session_state['check_in_start'] = datetime(2024, 11, 16).date()
if 'check_in_end' not in st.session_state or st.session_state['check_in_end'] is None:
    st.session_state['check_in_end'] = datetime(2024, 11, 22).date()
if 'check_out_start' not in st.session_state or st.session_state['check_out_start'] is None:
    st.session_state['check_out_start'] = datetime(2024, 11, 23).date()
if 'check_out_end' not in st.session_state or st.session_state['check_out_end'] is None:
    st.session_state['check_out_end'] = datetime(2024, 11, 27).date()
if 'select_all_state' not in st.session_state:
    st.session_state['select_all_state'] = False


from datetime import datetime, timedelta

# Initialize session state for dates and select all state
if 'check_in_start' not in st.session_state:
    st.session_state['check_in_start'] = pd.to_datetime(df['Arrival Date Short']).min().date()
if 'check_in_end' not in st.session_state:
    st.session_state['check_in_end'] = pd.to_datetime(df['Arrival Date Short']).max().date()
if 'check_out_start' not in st.session_state:
    st.session_state['check_out_start'] = pd.to_datetime(df['Departure Date Short']).min().date()
if 'check_out_end' not in st.session_state:
    st.session_state['check_out_end'] = pd.to_datetime(df['Departure Date Short']).max().date()
if 'select_all_state' not in st.session_state:
    st.session_state['select_all_state'] = False

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Assuming df is your DataFrame that's already loaded
# df = pd.read_csv('your_data.csv')  # Uncomment and modify as needed

# Initialize session state for dates and select all state
if 'check_in_start' not in st.session_state:
    st.session_state['check_in_start'] = pd.to_datetime(df['Arrival Date Short']).min().date()
    st.session_state['check_in_start_input'] = st.session_state['check_in_start']
if 'check_in_end' not in st.session_state:
    st.session_state['check_in_end'] = pd.to_datetime(df['Arrival Date Short']).max().date()
    st.session_state['check_in_end_input'] = st.session_state['check_in_end']
if 'check_out_start' not in st.session_state:
    st.session_state['check_out_start'] = pd.to_datetime(df['Departure Date Short']).min().date()
    st.session_state['check_out_start_input'] = st.session_state['check_out_start']
if 'check_out_end' not in st.session_state:
    st.session_state['check_out_end'] = pd.to_datetime(df['Departure Date Short']).max().date()
    st.session_state['check_out_end_input'] = st.session_state['check_out_end']
if 'select_all_state' not in st.session_state:
    st.session_state['select_all_state'] = False

import requests

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
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])

    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            key='check_in_start_input',
            value=st.session_state.get('check_in_start', pd.to_datetime(df['Arrival Date Short']).min().date())
        )
        st.session_state['check_in_start'] = check_in_start

        check_in_end = st.date_input(
            "Check In Date (End)",
            key='check_in_end_input',
            value=st.session_state.get('check_in_end', pd.to_datetime(df['Arrival Date Short']).max().date())
        )
        st.session_state['check_in_end'] = check_in_end

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            key='check_out_start_input',
            value=st.session_state.get('check_out_start', pd.to_datetime(df['Departure Date Short']).min().date())
        )
        st.session_state['check_out_start'] = check_out_start

        check_out_end = st.date_input(
            "Check Out Date (End)",
            key='check_out_end_input',
            value=st.session_state.get('check_out_end', pd.to_datetime(df['Departure Date Short']).max().date())
        )
        st.session_state['check_out_end'] = check_out_end

    with col3:
        if st.button("Reset Dates"):
            # Reset date filters
            st.session_state['check_in_start'] = pd.to_datetime(df['Arrival Date Short']).min().date()
            st.session_state['check_in_end'] = pd.to_datetime(df['Arrival Date Short']).max().date()
            st.session_state['check_out_start'] = pd.to_datetime(df['Departure Date Short']).min().date()
            st.session_state['check_out_end'] = pd.to_datetime(df['Departure Date Short']).max().date()
            st.rerun()

    # Apply filters to the dataset
    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

    mask = (
        (resort_df['Check In'].dt.date >= check_in_start) & 
        (resort_df['Check In'].dt.date <= check_in_end) & 
        (resort_df['Check Out'].dt.date >= check_out_start) & 
        (resort_df['Check Out'].dt.date <= check_out_end)
    )
    filtered_df = resort_df[mask]

    # Handle empty DataFrame
    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        filtered_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number'])
    else:
        # Prepare display DataFrame
        display_df = filtered_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']

        # Ensure proper types
        display_df['Select'] = False
        display_df['Check In'] = pd.to_datetime(display_df['Check In'], errors='coerce')
        display_df['Check Out'] = pd.to_datetime(display_df['Check Out'], errors='coerce')
        display_df['Phone Number'] = display_df['Phone Number'].astype(str)

        # Interactive data editor
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select or deselect this guest",
                    default=False
                ),
                "Guest Name": st.column_config.TextColumn(
                    "Guest Name",
                    help="Guest's full name"
                ),
                "Check In": st.column_config.DateColumn(
                    "Check In",
                    help="Check-in date"
                ),
                "Check Out": st.column_config.DateColumn(
                    "Check Out",
                    help="Check-out date"
                ),
                "Phone Number": st.column_config.TextColumn(
                    "Phone Number",
                    help="Guest's phone number"
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="guest_editor"
        )

        # Text Templates Section
        st.markdown("---")
        st.subheader("Message Templates")

        message_templates = {
            "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
            "Check-in Follow-up": f"Hello, we hope you're enjoying your stay at {selected_resort}. Don't forget to collect your welcome gift at the concierge desk! 🎁",
            "Checkout Message": f"Thank you for staying with us at {selected_resort}! We hope you had a great stay. Please stop by the concierge desk before you leave for a special gift! 🎁"
        }

        selected_template = st.selectbox(
            "Choose a Message Template",
            options=list(message_templates.keys())
        )

        message_preview = message_templates[selected_template]
        st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

        # Add "Send SMS to Selected Guests" Button
        selected_guests = edited_df[edited_df['Select']]
        if not selected_guests.empty:
            if st.button("Send SMS to Selected Guests"):
                openphone_url = "https://api.openphone.com/v1/messages"
                headers = {
                    "Authorization": f"Bearer {st.secrets['openphone']['api_key']}",
                    "Content-Type": "application/json"
                }

                # Your OpenPhone number
                sender_phone_number = "+18438972426"  # Replace with your OpenPhone number

                # Helper function to format phone numbers
                def format_phone_number(phone):
                    if not phone.startswith("+"):
                        return f"+1{phone}"  # Assuming US numbers
                    return phone

                # Sending SMS to each selected guest
                for _, row in selected_guests.iterrows():
                    recipient_phone = "+14075206507"  # Hard-coded test number
                    payload = {
                        "content": message_preview,
                        "from": sender_phone_number,
                        "to": [recipient_phone]
                    }

                    response = requests.post(openphone_url, json=payload, headers=headers)

                    if response.status_code == 202:
                        st.success(f"Message sent to {row['Guest Name']} ({recipient_phone})")
                    else:
                        st.error(f"Failed to send message to {row['Guest Name']} ({recipient_phone})")
                        st.write("Response Status Code:", response.status_code)
                        st.write("Response Body:", response.json())



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
