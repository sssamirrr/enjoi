import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math
import requests
import time


# Set page configuration
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for optional styling (can be customized or removed)
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

############################################
# Hard-coded OpenPhone Credentials
############################################

# Replace with your actual OpenPhone API key and number
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_NUMBER = "+18438972426"

############################################
# Connect to Google Sheets
############################################


@st.cache_resource
def get_google_sheet_data():
    try:
        # Retrieve Google Sheets credentials from st.secrets
        service_account_info = st.secrets["gcp_service_account"]

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None


# Load the data
df = get_google_sheet_data()
if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()  # Ensure the program stops execution if the data is not loaded


############################################
# OpenPhone API Functions
############################################

import time
import requests
import streamlit as st
from datetime import datetime
import pandas as pd

# In your main app
if 'current_df' not in st.session_state:
    st.session_state.current_df = guest_df.copy()

# Display the communication interface and update the DataFrame
st.session_state.current_df = display_communication_interface(
    st.session_state.current_df, 
    headers
)

# Display the current state of the DataFrame
st.dataframe(st.session_state.current_df)


def rate_limited_request(url, headers, params, request_type="get"):
    """
    Make an API request while respecting rate limits.
    """
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        st.write(f"Making API call to {url} with params: {params}")
        start_time = time.time()
        response = (
            requests.get(url, headers=headers, params=params)
            if request_type == "get"
            else None
        )
        elapsed_time = time.time() - start_time
        st.write(f"API call completed in {elapsed_time:.2f} seconds")

        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

def get_all_phone_number_ids(headers):
    """
    Retrieve all phoneNumberIds associated with your OpenPhone account.
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    return (
        [pn.get("id") for pn in response_data.get("data", [])] if response_data else []
    )

def get_last_communication_info(phone_number, headers):
    """
    For a given phone number, retrieve the last communication status (message or call)
    and the date of that communication across all OpenPhone numbers.
    """
    phone_number_ids = get_all_phone_number_ids(headers)
    if not phone_number_ids:
        st.error("No OpenPhone numbers found in the account.")
        return "No Communications", None

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    latest_type = None
    latest_direction = None

    for phone_number_id in phone_number_ids:
        # Fetch messages
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [phone_number],
            "maxResults": 50,
        }
        messages_response = rate_limited_request(messages_url, headers, params)
        if messages_response and "data" in messages_response:
            for message in messages_response["data"]:
                msg_time = datetime.fromisoformat(
                    message["createdAt"].replace("Z", "+00:00")
                )
                if not latest_datetime or msg_time > latest_datetime:
                    latest_datetime = msg_time
                    latest_type = "Message"
                    latest_direction = message.get("direction", "unknown")

        # Fetch calls
        calls_response = rate_limited_request(calls_url, headers, params)
        if calls_response and "data" in calls_response:
            for call in calls_response["data"]:
                call_time = datetime.fromisoformat(
                    call["createdAt"].replace("Z", "+00:00")
                )
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time
                    latest_type = "Call"
                    latest_direction = call.get("direction", "unknown")

    if not latest_datetime:
        return "No Communications", None

    return f"{latest_type} - {latest_direction}", latest_datetime.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def fetch_selected_communication_info(guest_df, headers, selected_indices=None):
    """
    Fetch communication statuses and dates for selected guests in the DataFrame.
    If no indices are provided, process all rows.
    """
    if "Phone Number" not in guest_df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        return guest_df

    # Create a copy of the DataFrame to avoid modifying the original
    result_df = guest_df.copy()
    
    # Initialize status columns if they don't exist
    if 'Communication Status' not in result_df.columns:
        result_df['Communication Status'] = "Not Checked"
    if 'Last Communication Date' not in result_df.columns:
        result_df['Last Communication Date'] = None

    # Determine which rows to process
    rows_to_process = selected_indices if selected_indices is not None else result_df.index

    # Clean and validate phone numbers for selected rows
    result_df.loc[rows_to_process, "Phone Number"] = result_df.loc[rows_to_process, "Phone Number"].astype(str).str.strip()
    result_df.loc[rows_to_process, "Phone Number"] = result_df.loc[rows_to_process, "Phone Number"].apply(format_phone_number)

    with st.spinner('Fetching communication statuses...'):
        for idx in rows_to_process:
            phone = result_df.loc[idx, 'Phone Number']
            st.write(f"Processing phone number: {phone}")

            if pd.notna(phone) and phone:
                try:
                    status, last_date = get_last_communication_info(phone, headers)
                    result_df.loc[idx, 'Communication Status'] = status
                    result_df.loc[idx, 'Last Communication Date'] = last_date
                except Exception as e:
                    st.error(f"Error fetching communication info for {phone}: {str(e)}")
                    result_df.loc[idx, 'Communication Status'] = "Error"
                    result_df.loc[idx, 'Last Communication Date'] = None
            else:
                result_df.loc[idx, 'Communication Status'] = "Invalid Number"
                result_df.loc[idx, 'Last Communication Date'] = None

    return result_df

def display_communication_interface(guest_df, headers):
    """
    Display the interface for loading communication statuses.
    """
    st.subheader("Communication Status Controls")
    
    # Create columns for buttons
    col1, col2 = st.columns(2)
    
    # Button to load all statuses
    if col1.button("Load All Communication Statuses"):
        return fetch_selected_communication_info(guest_df, headers)
    
    # Multi-select for individual numbers
    if not guest_df.empty:
        selected_rows = st.multiselect(
            "Select specific phone numbers to check:",
            options=guest_df.index,
            format_func=lambda x: f"{guest_df.loc[x, 'Phone Number']} - {guest_df.loc[x, 'Name'] if 'Name' in guest_df.columns else 'Unknown'}"
        )
        
        # Button to load selected statuses
        if col2.button("Load Selected Communication Statuses") and selected_rows:
            return fetch_selected_communication_info(guest_df, headers, selected_rows)
    
    return guest_df

# In your main app
if 'current_df' not in st.session_state:
    st.session_state.current_df = guest_df.copy()

# Display the communication interface and update the DataFrame
st.session_state.current_df = display_communication_interface(
    st.session_state.current_df, 
    headers
)

# Display the current state of the DataFrame
st.dataframe(st.session_state.current_df)
############################################
# Create Tabs
############################################
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

############################################
# Dashboard Tab
############################################
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_hotel = st.multiselect(
            "Select Hotel", options=sorted(df["Market"].unique()), default=[]
        )

    with col2:
        min_date = pd.to_datetime(df["Arrival Date Short"]).min()
        max_date = pd.to_datetime(df["Arrival Date Short"]).max()
        date_range = st.date_input(
            "Select Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    with col3:
        selected_rate_codes = st.multiselect(
            "Select Rate Codes",
            options=sorted(df["Rate Code Name"].unique()),
            default=[],
        )

    # Filter data
    filtered_df = df.copy()

    if selected_hotel:
        filtered_df = filtered_df[filtered_df["Market"].isin(selected_hotel)]

    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df["Arrival Date Short"]).dt.date >= date_range[0])
            & (
                pd.to_datetime(filtered_df["Arrival Date Short"]).dt.date
                <= date_range[1]
            )
        ]

    if selected_rate_codes:
        filtered_df = filtered_df[
            filtered_df["Rate Code Name"].isin(selected_rate_codes)
        ]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Reservations", len(filtered_df))
    with col2:
        average_nights = filtered_df["# Nights"].mean()
        st.metric(
            "Average Nights",
            f"{average_nights:.1f}" if not math.isnan(average_nights) else "0",
        )
    with col3:
        total_room_nights = filtered_df["# Nights"].sum()
        st.metric("Total Room Nights", f"{total_room_nights:,.0f}")
    with col4:
        unique_guests = filtered_df["Name"].nunique()
        st.metric("Unique Guests", unique_guests)

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Reservations by Hotel using groupby
        reservations_by_hotel = (
            filtered_df.groupby("Market").size().reset_index(name="Reservations")
        )
        reservations_by_hotel = reservations_by_hotel.rename(
            columns={"Market": "Hotel"}
        )

        # Conditional Plotting
        if reservations_by_hotel.empty:
            st.warning("No reservation data available for the selected filters.")
        else:
            fig_hotels = px.bar(
                reservations_by_hotel,
                x="Hotel",
                y="Reservations",
                labels={"Hotel": "Hotel", "Reservations": "Reservations"},
                title="Reservations by Hotel",
            )
            st.plotly_chart(fig_hotels, use_container_width=True)

    with col2:
        # Length of Stay Distribution
        fig_los = px.histogram(
            filtered_df, x="# Nights", title="Length of Stay Distribution"
        )
        st.plotly_chart(fig_los, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        # Rate Code Distribution
        fig_rate = px.pie(
            filtered_df, names="Rate Code Name", title="Rate Code Distribution"
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        # Arrivals by Date
        daily_arrivals = filtered_df["Arrival Date Short"].value_counts().sort_index()

        if daily_arrivals.empty:
            st.warning("No arrival data available for the selected filters.")
        else:
            fig_arrivals = px.line(
                x=daily_arrivals.index,
                y=daily_arrivals.values,
                labels={"x": "Date", "y": "Arrivals"},
                title="Arrivals by Date",
            )
            st.plotly_chart(fig_arrivals, use_container_width=True)


# Function to reset filters to defaults
def reset_filters():
    default_dates = st.session_state["default_dates"]
    for key, value in default_dates.items():
        if key in st.session_state:
            del st.session_state[
                key
            ]  # Delete the existing key to allow widget reinitialization
    st.session_state.update(default_dates)  # Update with the default values


import pandas as pd
import requests
import time
import json

############################################
# Marketing Tab
############################################
with tab2:
    st.title("📊 Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort", options=sorted(df["Market"].unique())
    )

    # Filter for selected resort
    resort_df = df[df["Market"] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Initialize or check session state variables
    if "default_dates" not in st.session_state:
        st.session_state["default_dates"] = {}

    # Set default dates to the earliest check-in and latest check-out
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df["Arrival Date Short"], errors="coerce")
        departure_dates = pd.to_datetime(
            resort_df["Departure Date Short"], errors="coerce"
        )

        arrival_dates = arrival_dates.dropna()
        departure_dates = departure_dates.dropna()

        min_check_in = (
            arrival_dates.min().date()
            if not arrival_dates.empty
            else pd.to_datetime("today").date()
        )
        max_check_out = (
            departure_dates.max().date()
            if not departure_dates.empty
            else pd.to_datetime("today").date()
        )

        st.session_state["default_dates"] = {
            "check_in_start": min_check_in,
            "check_in_end": max_check_out,
            "check_out_start": min_check_in,
            "check_out_end": max_check_out,
        }

        # Function to reset filters (move this definition outside the if block)
        def reset_filters():
            # Retrieve default dates from session state
            default_dates = st.session_state["default_dates"]

            # Clear the date input widgets by removing their keys from session state
            keys_to_remove = [
                "check_in_start",
                "check_in_end",
                "check_out_start",
                "check_out_end",
            ]
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]

            # Reset to default dates
            st.session_state.update(default_dates)

            # Force a rerun of the app
            st.rerun()

    # Date filters
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=st.session_state.get("check_in_start", min_check_in),
            key="check_in_start",
        )

        check_in_end = st.date_input(
            "Check In Date (End)",
            value=st.session_state.get("check_in_end", max_check_out),
            key="check_in_end",
        )

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=st.session_state.get("check_out_start", min_check_in),
            key="check_out_start",
        )

        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=st.session_state.get("check_out_end", max_check_out),
            key="check_out_end",
        )

    with col3:
        if st.button("Reset Dates"):
            reset_filters()

    # Apply filters to the dataset
    resort_df["Check In"] = pd.to_datetime(
        resort_df["Arrival Date Short"], errors="coerce"
    ).dt.date
    resort_df["Check Out"] = pd.to_datetime(
        resort_df["Departure Date Short"], errors="coerce"
    ).dt.date
    resort_df = resort_df.dropna(subset=["Check In", "Check Out"])

    mask = (
        (resort_df["Check In"] >= st.session_state["check_in_start"])
        & (resort_df["Check In"] <= st.session_state["check_in_end"])
        & (resort_df["Check Out"] >= st.session_state["check_out_start"])
        & (resort_df["Check Out"] <= st.session_state["check_out_end"])
    )
    filtered_df = resort_df[mask]

    # Handle empty DataFrame
    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        display_df = pd.DataFrame(
            columns=[
                "Select",
                "Guest Name",
                "Check In",
                "Check Out",
                "Phone Number",
                "Communication Status",
                "Last Communication Date",
            ]
        )
    else:
        # Prepare display DataFrame
        display_df = filtered_df[
            ["Name", "Check In", "Check Out", "Phone Number"]
        ].copy()
        display_df.columns = ["Guest Name", "Check In", "Check Out", "Phone Number"]

        # Function to format phone numbers
        def format_phone_number(phone):
            phone = "".join(filter(str.isdigit, str(phone)))
            if len(phone) == 10:
                return f"+1{phone}"
            elif len(phone) == 11 and phone.startswith("1"):
                return f"+{phone}"
            else:
                return phone  # Return as is if it doesn't match expected patterns

        # Apply phone number formatting
        display_df["Phone Number"] = display_df["Phone Number"].apply(
            format_phone_number
        )
        display_df["Communication Status"] = "Checking..."
        display_df["Last Communication Date"] = None  # Initialize the new column

        # Add "Select All" checkbox
        select_all = st.checkbox("Select All")
        display_df["Select"] = select_all

        ## Prepare headers for API calls
        headers = {
            "Authorization": OPENPHONE_API_KEY,
            "Content-Type": "application/json",
        }

        # Fetch communication statuses and dates
        statuses, dates = fetch_communication_info(display_df, headers)
        display_df["Communication Status"] = statuses
        display_df["Last Communication Date"] = dates

        # Reorder columns to have "Select" as the leftmost column
        display_df = display_df[
            [
                "Select",
                "Guest Name",
                "Check In",
                "Check Out",
                "Phone Number",
                "Communication Status",
                "Last Communication Date",
            ]
        ]

        # Interactive data editor
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select", help="Select or deselect this guest", default=select_all
                ),
                "Guest Name": st.column_config.TextColumn(
                    "Guest Name", help="Guest's full name"
                ),
                "Check In": st.column_config.DateColumn(
                    "Check In", help="Check-in date"
                ),
                "Check Out": st.column_config.DateColumn(
                    "Check Out", help="Check-out date"
                ),
                "Phone Number": st.column_config.TextColumn(
                    "Phone Number", help="Guest's phone number"
                ),
                "Communication Status": st.column_config.TextColumn(
                    "Communication Status",
                    help="Last communication status with the guest",
                    disabled=True,
                ),
                "Last Communication Date": st.column_config.TextColumn(
                    "Last Communication Date",
                    help="Date and time of the last communication with the guest",
                    disabled=True,
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="guest_editor",
        )

    ############################################
    # Message Templates Section
    ############################################
    st.markdown("---")
    st.subheader("Message Templates")

    message_templates = {
        "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
        "Check-in Follow-up": f"Hello, we hope you're enjoying your stay at {selected_resort}. Don't forget to collect your welcome gift at the concierge desk! 🎁",
        "Checkout Message": f"Thank you for staying with us at {selected_resort}! We hope you had a great stay. Please stop by the concierge desk before you leave for a special gift! 🎁",
    }

    selected_template = st.selectbox(
        "Choose a Message Template", options=list(message_templates.keys())
    )

    message_preview = message_templates[selected_template]
    st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

    ############################################
    # Send SMS to Selected Guests
    ############################################
    if "edited_df" in locals() and not edited_df.empty:
        selected_guests = edited_df[edited_df["Select"]]
        num_selected = len(selected_guests)
        if not selected_guests.empty:
            button_label = (
                f"Send SMS to {num_selected} Guest{'s' if num_selected!= 1 else ''}"
            )
            if st.button(button_label):
                openphone_url = "https://api.openphone.com/v1/messages"
                headers_sms = {
                    "Authorization": OPENPHONE_API_KEY,
                    "Content-Type": "application/json",
                }
                sender_phone_number = OPENPHONE_NUMBER  # Your OpenPhone number

                for idx, row in selected_guests.iterrows():
                    recipient_phone = row[
                        "Phone Number"
                    ]  # Use actual guest's phone number
                    payload = {
                        "content": message_preview,
                        "from": sender_phone_number,
                        "to": [recipient_phone],
                    }

                    try:
                        response = requests.post(
                            openphone_url, json=payload, headers=headers_sms
                        )
                        if response.status_code == 202:
                            st.success(
                                f"Message sent to {row['Guest Name']} ({recipient_phone})"
                            )
                        else:
                            st.error(
                                f"Failed to send message to {row['Guest Name']} ({recipient_phone})"
                            )
                            st.write("Response Status Code:", response.status_code)
                            try:
                                st.write("Response Body:", response.json())
                            except:
                                st.write("Response Body:", response.text)
                    except Exception as e:
                        st.error(
                            f"Exception while sending message to {row['Guest Name']} ({recipient_phone}): {str(e)}"
                        )

                    time.sleep(0.2)  # Respect rate limits
        else:
            st.info("No guests selected to send SMS.")
    else:
        st.info("No guest data available to send SMS.")


############################################
# Tour Prediction Tab
############################################
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date for Tour Prediction",
            value=pd.to_datetime(df["Arrival Date Short"]).min().date(),
        )
    with col2:
        end_date = st.date_input(
            "End Date for Tour Prediction",
            value=pd.to_datetime(df["Arrival Date Short"]).max().date(),
        )

    # Validate date range
    if start_date > end_date:
        st.error("Start Date cannot be after End Date.")
    else:
        # Prepare a DataFrame to collect all resort data
        all_resorts_tour_data = []

        for resort in sorted(df["Market"].unique()):
            resort_df = df[df["Market"] == resort].copy()
            resort_df["Arrival Date Short"] = pd.to_datetime(
                resort_df["Arrival Date Short"], errors="coerce"
            )
            filtered_resort_df = resort_df[
                (resort_df["Arrival Date Short"].dt.date >= start_date)
                & (resort_df["Arrival Date Short"].dt.date <= end_date)
            ]

            # Daily Arrivals
            daily_arrivals = (
                filtered_resort_df.groupby(
                    filtered_resort_df["Arrival Date Short"].dt.date
                )
                .size()
                .reset_index(name="Arrivals")
            )
            daily_arrivals = daily_arrivals.rename(
                columns={"Arrival Date Short": "Date"}
            )  # Rename for consistency

            st.subheader(f"{resort}")

            # Conversion Rate Input
            conversion_rate = (
                st.number_input(
                    f"Conversion Rate for {resort} (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=10.0,
                    step=0.5,
                    key=f"conversion_{resort}",
                )
                / 100
            )

            # Calculate Tours, rounded down using math.floor
            daily_arrivals["Tours"] = daily_arrivals["Arrivals"].apply(
                lambda a: math.floor(a * conversion_rate)
            )

            st.dataframe(daily_arrivals)

            # Aggregate summaries for visualization later
            all_resorts_tour_data.append(daily_arrivals.assign(Market=resort))

        # Concatenate all resort data
        if all_resorts_tour_data:
            full_summary_df = pd.concat(all_resorts_tour_data, ignore_index=True)

            # Check if 'Date' column exists
            if "Date" not in full_summary_df.columns:
                st.error("The 'Date' column is missing from the tour summary data.")
            else:
                # Overall Summary
                st.markdown("---")
                st.subheader("Overall Tour Summary Across All Resorts")

                # Handle empty DataFrame
                if full_summary_df.empty:
                    st.warning("No tour data available for the selected date range.")
                else:
                    overall_summary = (
                        full_summary_df.groupby("Date").sum().reset_index()
                    )

                    # Check if 'Date' column exists
                    if "Date" not in overall_summary.columns:
                        st.error(
                            "The 'Date' column is missing from the overall summary data."
                        )
                    else:
                        st.dataframe(overall_summary)

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(
                                "Total Arrivals for All Resorts",
                                overall_summary["Arrivals"].sum(),
                            )
                        with col2:
                            st.metric(
                                "Total Estimated Tours for All Resorts",
                                overall_summary["Tours"].sum(),
                            )
        else:
            st.info("No tour data available for the selected date range.")

############################################
# Raw Data Viewer
############################################
with st.expander("Show Raw Data"):
    st.dataframe(df)
