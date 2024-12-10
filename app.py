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
    .stButton > button {
        width: 100%;
    }
    </style>
""",
    unsafe_allow_html=True,
)

################################################### 
# Hard-coded OpenPhone Credentials
###################################################

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_NUMBER = "+18438972426"

################################################### 
# Connect to Google Sheets
###################################################

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
    st.stop()

############################################
# OpenPhone API Functions
############################################

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
    return [pn.get("id") for pn in response_data.get("data", [])] if response_data else []

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
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [phone_number],
            "maxResults": 50,
        }
        messages_response = rate_limited_request(messages_url, headers, params)
        if messages_response and "data" in messages_response:
            for message in messages_response["data"]:
                msg_time = datetime.fromisoformat(message["createdAt"].replace("Z", "+00:00"))
                if not latest_datetime or msg_time > latest_datetime:
                    latest_datetime = msg_time
                    latest_type = "Message"
                    latest_direction = message.get("direction", "unknown")

        calls_response = rate_limited_request(calls_url, headers, params)
        if calls_response and "data" in calls_response:
            for call in calls_response["data"]:
                call_time = datetime.fromisoformat(call["createdAt"].replace("Z", "+00:00"))
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time
                    latest_type = "Call"
                    latest_direction = call.get("direction", "unknown")

    if not latest_datetime:
        return "No Communications", None

    return f"{latest_type} - {latest_direction}", latest_datetime.strftime("%Y-%m-%d %H:%M:%S")

def fetch_communication_info(df, headers):
    """
    Fetch communication statuses and dates for all guests in the DataFrame.
    """
    if "Phone Number" not in df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        st.write("Available columns:", df.columns.tolist())
        return ["No Status"] * len(df), [None] * len(df)

    df["Phone Number"] = format_phone_numbers(df["Phone Number"])
    statuses = []
    dates = []
    for idx, row in df.iterrows():
        phone = row["Phone Number"]
        if pd.notna(phone):
            status, dte = get_last_communication_info(phone, headers)
            statuses.append(status)
            dates.append(dte)
        else:
            statuses.append("No Phone Number")
            dates.append(None)
    return statuses, dates

def format_phone_number(phone):
    phone = "".join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith("1"):
        return f"+{phone}"
    else:
        return phone  # Return as is if it doesn't match expected patterns

def format_phone_numbers(series):
    return [format_phone_number(ph) for ph in series]

############################################
# Create Tabs
############################################

tab1, tab2, tab3 = st.tabs(["🌟 Dashboard", "📊 Marketing", "🔮 Tour Prediction"])

############################################
# Dashboard Tab
############################################

with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time Analysis of Hotel Reservations")

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_market = st.multiselect("Select Market", 
                                         options=sorted(df["Market"].unique()), 
                                         default=[df["Market"].iloc[0]])
    with col2:
        min_date = pd.to_datetime(df["Arrival Date Short"]).min()
        max_date = pd.to_datetime(df["Arrival Date Short"]).max()
        date_range = st.date_input("Select Date Range", 
                                   value=(min_date.date(), max_date.date()),
                                   min_value=min_date.date(),
                                   max_value=max_date.date(),
                                   key="date_range")
    with col3:
        selected_rate_codes = st.multiselect("Select Rate Codes", 
                                             options=sorted(df["Rate Code"].unique()),
                                             default=[df["Rate Code"].iloc[0]])

    filtered_df = df.copy()
    
    if selected_market:
        filtered_df = filtered_df[filtered_df["Market"].isin(selected_market)]

    if len(date_range) == 2:
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df["Arrival Date Short"]).dt.date >= date_range[0])
            & (pd.to_datetime(filtered_df["Arrival Date Short"]).dt.date <= date_range[1])
        ]

    if selected_rate_codes:
        filtered_df = filtered_df[filtered_df["Rate Code"].isin(selected_rate_codes)]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Reservations", len(filtered_df))
    with col2:
        average_nights = filtered_df["# Nights"].mean()
        st.metric("Average Nights", f"{average_nights:.1f}" if not math.isnan(average_nights) else "0")
    with col3:
        total_room_nights = filtered_df["# Nights"].sum()
        st.metric("Total Room Nights", f"{total_room_nights:,.0f}")
    with col4:
        unique_guests = filtered_df["Name"].nunique()
        st.metric("Unique Guests", unique_guests)

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        if not filtered_df.empty:
            market_distribution = filtered_df["Market"].value_counts().reset_index()
            market_distribution.columns = ["Market", "Reservations"]

            fig_market = px.bar(market_distribution, x="Market", y="Reservations", 
                                labels={"Reservations": "Number of Reservations"}, 
                                title="Reservations by Market")
            st.plotly_chart(fig_market, use_container_width=True)
        else:
            st.warning("No reservations to show, no chart can be displayed.")

    with col2:
        # Length of Stay Distribution
        fig_los = px.histogram(filtered_df, x="# Nights", 
                               nbins=20, 
                               title="Length of Stay Distribution")
        st.plotly_chart(fig_los, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        # Rate Code Distribution
        if not filtered_df.empty:
            fig_rate = px.histogram(filtered_df, x="Rate Code", 
                                    title="Rate Code Distribution")
            st.plotly_chart(fig_rate, use_container_width=True)
        else:
            st.warning("No rate codes to display in chart.")

    with col2:
        # Arrivals by Date
        if not filtered_df.empty:
            arrivals_by_date = filtered_df["Arrival Date Short"].value_counts().sort_index()
            
            daily_arrivals = arrivals_by_date.reset_index()
            daily_arrivals.columns = ["Date", "Arrivals"]

            fig_arrivals = px.line(daily_arrivals, x="Date", y="Arrivals",
                                   labels={"Arrivals": "Number of Arrivals"},
                                   title="Arrivals by Date")
            st.plotly_chart(fig_arrivals, use_container_width=True)
        else:
            st.warning("No arrivals data available for visualization.")

############################################
# Marketing Tab
############################################

with tab2:
    st.title("📊 Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox("Select Resort", options=sorted(df["Market"].unique()))

    # Display button to fetch all numbers' status at once
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

    if st.button("Load Status for All Numbers"):
        if 'display_df' in locals() and not display_df.empty:
            statuses, dates = fetch_communication_info(display_df, headers)
            display_df["Communication Status"] = statuses
            display_df["Last Communication Date"] = dates

    resort_df = df[df["Market"] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    if "default_dates" not in st.session_state:
        st.session_state["default_dates"] = {}

    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df["Arrival Date Short"], errors="coerce")
        departure_dates = pd.to_datetime(resort_df["Departure Date Short"], errors="coerce")

        arrival_dates = arrival_dates.dropna()
        departure_dates = departure_dates.dropna()

        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else pd.to_datetime("today").date()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else pd.to_datetime("today").date()

        st.session_state["default_dates"] = {
            "check_in_start": min_check_in,
            "check_in_end": max_check_out,
            "check_out_start": min_check_in,
            "check_out_end": max_check_out,
        }

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

    def reset_filters():
        for key in ["check_in_start", "check_in_end", "check_out_start", "check_out_end"]:
            st.session_state[key] = st.session_state["default_dates"][key]
        if 'edited_df' in st.session_state and not edited_df.empty:
            edited_df = (display_df.copy())
            st.experimental_set_query_params(**{key: str(value) for key, value in st.session_state.items() if key != 'edited_df'})

    # Apply filters to the dataset
    resort_df["Check In"] = pd.to_datetime(resort_df["Arrival Date Short"], errors="coerce").dt.date
    resort_df["Check Out"] = pd.to_datetime(resort_df["Departure Date Short"], errors="coerce").dt.date
    resort_df = resort_df.dropna(subset=["Check In", "Check Out"])

    filtered_df = resort_df[
        (resort_df["Check In"] >= check_in_start) & 
        (resort_df["Check In"] <= check_in_end) & 
        (resort_df["Check Out"] >= check_out_start) & 
        (resort_df["Check Out"] <= check_out_end)
    ]

    # Handle empty DataFrame
    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        display_df = pd.DataFrame(
            columns=["Select", "Guest Name", "Check In", "Check Out", "Phone Number", "Communication Status", "Last Communication Date"]
        )
    else:
        # Prepare display DataFrame
        display_df = filtered_df[["Name", "Check In", "Check Out", "Phone Number"]].copy()
        display_df.columns = ["Guest Name", "Check In", "Check Out", "Phone Number"]

        # Add "Select All" checkbox
        select_all = st.checkbox("Select All")
        display_df["Select"] = select_all

        # Initial values for status and date
        display_df["Communication Status"] = "Load Status"
        display_df["Last Communication Date"] = "Not Loaded"

        # Function to fetch individual status
        def fetch_individual_status(index, headers):
            global edited_df, st
            if index in edited_df.index:
                row = edited_df.loc[index]
                status, dte = get_last_communication_info(row["Phone Number"], headers)
                edited_df.at[index, "Communication Status"] = status
                edited_df.at[index, "Last Communication Date"] = dte
                st.experimental_rerun()  # Rerun the app to show the updated data

        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select or deselect this guest"),
                "Guest Name": st.column_config.TextColumn("Guest Name", help="Guest's full name", disabled=True),
                "Check In": st.column_config.DateColumn("Check In", help="Check-in date", disabled=True),
                "Check Out": st.column_config.DateColumn("Check Out", help="Check-out date", disabled=True),
                "Phone Number": st.column_config.TextColumn("Phone Number", help="Guest's phone number", disabled=True),
                "Communication Status": st.column_config.ButtonColumn(
                    "Load Status",
                    help="Click to load communication status for this guest",
                    on_click=lambda index: fetch_individual_status(index, headers),
                ),
                "Last Communication Date": st.column_config.TextColumn("Last Communication Date", help="Date and time of the last communication with the guest", disabled=True)
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

    selected_template = st.selectbox("Choose a Message Template", options=list(message_templates.keys()))

    message_preview = message_templates[selected_template]
    st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

    ############################################
    # Send SMS to Selected Guests
    ############################################
    if not edited_df.empty:
        selected_guests = edited_df[edited_df["Select"]]
        num_selected = len(selected_guests)
        if not selected_guests.empty:
            button_label = f"Send SMS to {num_selected} Guest{'s' if num_selected != 1 else ''}"
            if st.button(button_label):
                openphone_url = "https://api.openphone.com/v1/messages"
                headers_sms = {
                    "Authorization": OPENPHONE_API_KEY,
                    "Content-Type": "application/json",
                }
                sender_phone_number = OPENPHONE_NUMBER

                for idx, row in selected_guests.iterrows():
                    recipient_phone = row["Phone Number"]
                    payload = {
                        "content": message_preview,
                        "from": sender_phone_number,
                        "to": [recipient_phone],
                    }

                    try:
                        response = requests.post(openphone_url, json=payload, headers=headers_sms)
                        if response.status_code == 202:
                            st.success(f"Message sent to {row['Guest Name']} ({recipient_phone})")
                        else:
                            st.error(f"Failed to send message to {row['Guest Name']} ({recipient_phone})")
                            st.write("Response Status Code:", response.status_code)
                            try:
                                st.write("Response Body:", response.json())
                            except:
                                st.write("Response Body:", response.text)
                    except Exception as e:
                        st.error(f"Exception while sending message to {row['Guest Name']} ({recipient_phone}): {str(e)}")

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
        start_date = st.date_input("Start Date for Tour Prediction", value=df["Arrival Date Short"].min())
    with col2:
        end_date = st.date_input("End Date for Tour Prediction", value=df["Arrival Date Short"].max())

    if start_date > end_date:
        st.error("Start Date cannot be after End Date.")
    else:
        all_tour_data = pd.DataFrame()

        for market in df["Market"].unique():
            market_df = df[df["Market"] == market].copy()
            market_df["Arrival Date"] = pd.to_datetime(market_df["Arrival Date Short"])
            market_df = market_df[(market_df["Arrival Date"] >= pd.Timestamp(start_date)) & (market_df["Arrival Date"] <= pd.Timestamp(end_date))]

            daily_tour_data = market_df.groupby(market_df["Arrival Date"].dt.date).size().reset_index(name="Arrivals")
            daily_tour_data["Tours"] = daily_tour_data["Arrivals"] * 0.10  # 10% conversion rate
            daily_tour_data["Market"] = market

            all_tour_data = pd.concat([all_tour_data, daily_tour_data], ignore_index=True)

        if not all_tour_data.empty:
            all_tour_data["Arrivals"] = all_tour_data["Arrivals"].astype(int)
            all_tour_data["Tours"] = all_tour_data["Tours"].astype(int)

        # Display data for each market
        for market in all_tour_data["Market"].unique():
            st.subheader(f"{market}")
            
            # Conversion Rate Input; keep as a Streamlit selectbox for consistency with the UI
            conversion_rate = st.slider(f"Set Conversion Rate for {market} (%)", min_value=0, max_value=50, value=10) / 100 
            market_data = all_tour_data[all_tour_data["Market"] == market].copy()
            market_data["Predicted Tours"] = (market_data["Arrivals"] * conversion_rate).astype(int)
            st.dataframe(market_data.rename(columns={"Predicted Tours": "Tours"}).set_index("Arrival Date")[["Arrivals", "Tours"]])

        # Show overall summaries only if there is data
        if not all_tour_data.empty:
            overall_summary = all_tour_data.groupby("Arrival Date")[["Arrivals", "Tours"]].sum().reset_index()
            st.markdown("---")
            st.subheader("Overall Tour Summary Across All Markets")
            st.dataframe(overall_summary.set_index("Arrival Date"))
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Arrivals", overall_summary["Arrivals"].sum())
            with col2:
                st.metric("Total Predicted Tours", overall_summary["Tours"].sum())
            with col3:
                overall_conversion_rate = (overall_summary["Tours"].sum() / overall_summary["Arrivals"].sum()) * 100
                st.metric("Overall Conversion Rate (%)", f"{overall_conversion_rate:.2f}%")

############################################
# Raw Data Viewer
############################################
with st.expander("Show Raw Data"):  
    st.dataframe(df)
