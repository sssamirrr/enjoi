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


def fetch_communication_info(guest_df, headers):
    """
    Fetch communication statuses and dates for all guests in the DataFrame.
    """
    # Check if "Phone Number" column exists
    if "Phone Number" not in guest_df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        st.write("Available columns:", guest_df.columns.tolist())
        return ["No Status"] * len(guest_df), [None] * len(guest_df)

    # Clean and validate phone numbers
    guest_df["Phone Number"] = guest_df["Phone Number"].astype(str).str.strip()
    guest_df["Phone Number"] = guest_df["Phone Number"].apply(format_phone_number)
    st.write("Cleaned phone numbers:", guest_df["Phone Number"].tolist())

    # Initialize results lists
    statuses = ["No Status"] * len(guest_df)
    dates = [None] * len(guest_df)

    # Use enumerate for positional indexing
    for pos_idx, (idx, row) in enumerate(guest_df.iterrows()):
        phone = row["Phone Number"]
        st.write(f"Processing phone number: {phone}")

        if pd.notna(phone) and phone:  # Ensure phone number is valid
            try:
                # Fetch communication info
                status, last_date = get_last_communication_info(phone, headers)
                statuses[pos_idx] = status  # Use positional index
                dates[pos_idx] = last_date
            except Exception as e:
                st.error(f"Error fetching communication info for {phone}: {str(e)}")
                statuses[pos_idx] = "Error"
                dates[pos_idx] = None
        else:
            statuses[pos_idx] = "Invalid Number"
            dates[pos_idx] = None

    # Output results for debugging
    st.write("Statuses:", statuses)
    st.write("Dates:", dates)
    return statuses, dates


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

eyError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/home/adminuser/venv/lib/python3.12/site-packages/streamlit/runtime/scriptrunner/exec_code.py", line 88, in exec_func_with_error_handling
    result = func()
             ^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/streamlit/runtime/scriptrunner/script_runner.py", line 579, in code_to_exec
    exec(code, module.__dict__)
File "/mount/src/enjoi/app.py", line 527, in <module>
    current_status = display_df.at[idx, 'Communication Status']
                     ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/indexing.py", line 2575, in __getitem__
    return super().__getitem__(key)
           ^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/indexing.py", line 2527, in __getitem__
    return self.obj._get_value(*key, takeable=self._takeable)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/frame.py", line 4221, in _get_value
    row = self.index.get_loc(index)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/indexes/base.py", line 3812, in get_loc
    raise KeyError(key) from err
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
