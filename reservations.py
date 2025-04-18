# reservations.py

import streamlit as st
import pandas as pd
import math
import time
import requests
from datetime import datetime
import owner_marketing

##############################
# Helper Functions
##############################
def cleanup_phone_number(phone):
    """Clean up phone number format"""
    if pd.isna(phone):
        return 'No Data'
    # Remove spaces and non-numeric characters
    phone = ''.join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith('1'):
        return f"+{phone}"
    return 'No Data'

def truncate_text(text, max_length=30):
    """Truncate text to a maximum length with ellipsis"""
    if isinstance(text, str) and len(text) > max_length:
        return text[:max_length] + "..."
    return text

def reset_filters(selected_resort, min_check_in, max_check_out, total_price_min, total_price_max):
    """
    Reset filter-related session state variables based on the provided resort and date range.
    """
    try:
        st.session_state['reset_trigger'] = True
        st.session_state[f'default_check_in_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_in_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_check_out_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_out_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_total_price_{selected_resort}'] = (
            float(total_price_min), 
            float(total_price_max)
        )
        st.session_state[f'default_rate_code_{selected_resort}'] = "All"
    except Exception as e:
        st.error(f"Error resetting filters: {e}")

def run_reservations_tab(
    df,
    OPENPHONE_API_KEY,
    OPENPHONE_NUMBER,
    fetch_communication_info_func,
    owner_marketing_module=None
):
    """
    Displays the Marketing (Reservations) tab content.
    
    Parameters
    ----------
    df : pd.DataFrame
        The main DataFrame containing all reservation data.
    OPENPHONE_API_KEY : str
        Your OpenPhone API key.
    OPENPHONE_NUMBER : str
        Your OpenPhone number (e.g. '+1XXXXXXXXXX').
    fetch_communication_info_func : Callable
        A function that fetches communication info given a DataFrame and HTTP headers.
    owner_marketing_module : module or None
        Reference to your `owner_marketing` module if needed.
    """

    st.title("📊 Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )

    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Determine default date range
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce').dropna()
        departure_dates = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce').dropna()
        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else pd.to_datetime('today').date()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else pd.to_datetime('today').date()
    else:
        today = pd.to_datetime('today').date()
        min_check_in, max_check_out = today, today

    # Date filters
    col1, col2, col3 = st.columns([0.3, 0.3, 0.4])
    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=min_check_in,
            key=f'check_in_start_input_{selected_resort}'
        )
        check_in_end = st.date_input(
            "Check In Date (End)",
            value=max_check_out,
            key=f'check_in_end_input_{selected_resort}'
        )

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=min_check_in,
            key=f'check_out_start_input_{selected_resort}'
        )
        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=max_check_out,
            key=f'check_out_end_input_{selected_resort}'
        )

    # Price and Rate Code filters
    with col3:
        # Price slider
        if 'Total Price' in resort_df.columns and not resort_df['Total Price'].isnull().all():
            total_price_min = resort_df['Total Price'].min()
            total_price_max = resort_df['Total Price'].max()
            if total_price_min == total_price_max:
                total_price_min -= 1
                total_price_max += 1
            total_price_range = st.slider(
                "Total Price Range",
                min_value=float(total_price_min),
                max_value=float(total_price_max),
                value=(float(total_price_min), float(total_price_max)),
                key=f'total_price_slider_{selected_resort}'
            )
        else:
            st.warning("No valid Total Price data available for filtering.")
            total_price_range = (0, 0)

        # Rate Code dropdown
        rate_code_options = []
        if 'Rate Code Name' in resort_df.columns:
            rate_code_options = sorted(resort_df['Rate Code Name'].dropna().unique())
        selected_rate_code = st.selectbox(
            "Select Rate Code",
            options=["All"] + list(rate_code_options),
            key=f'rate_code_filter_{selected_resort}'
        )

    # Reset Filters
    with st.container():
        if st.button("Reset Filters"):
            reset_filters(selected_resort, min_check_in, max_check_out, total_price_min, total_price_max)

    # Apply filters
    if not resort_df.empty:
        resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        resort_df['Departure Date Short'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        filtered_df = resort_df[
            (resort_df['Arrival Date Short'].dt.date >= check_in_start) &
            (resort_df['Arrival Date Short'].dt.date <= check_in_end) &
            (resort_df['Departure Date Short'].dt.date >= check_out_start) &
            (resort_df['Departure Date Short'].dt.date <= check_out_end)
        ]

        if 'Total Price' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['Total Price'] >= total_price_range[0]) &
                (filtered_df['Total Price'] <= total_price_range[1])
            ]

        if selected_rate_code != "All" and 'Rate Code Name' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Rate Code Name'] == selected_rate_code]

        # De-duplicate by Phone Number
        display_df = filtered_df.drop_duplicates(subset=['Phone Number']).reset_index(drop=True)
        if display_df['Phone Number'].duplicated().any():
            st.error("Duplicate phone numbers found. Please ensure each guest has a unique phone number.")
            return

        if not display_df.empty:
            # Rename columns
            display_df = display_df.rename(columns={
                'Name': 'Guest Name',
                'Arrival Date Short': 'Check In',
                'Departure Date Short': 'Check Out',
                'Rate Code Name': 'Rate Code',
                'Total Price': 'Price'
            })

            # Ensure necessary columns exist
            required_columns = [
                'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Rate Code', 'Price',
                'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name',
                'Total Messages', 'Total Calls', 'Answered Calls', 'Missed Calls', 'Call Attempts',
                'Pre-Arrival Calls', 'Pre-Arrival Texts', 'Post-Arrival Calls', 'Post-Arrival Texts', 'Calls Under 40 sec'
            ]
            for col in required_columns:
                if col not in display_df.columns:
                    display_df[col] = None

            # Format phone numbers
            display_df['Phone Number'] = display_df['Phone Number'].apply(cleanup_phone_number)
            # Truncate long text fields
            display_df['Guest Name'] = display_df['Guest Name'].apply(lambda x: truncate_text(x, 30))
            display_df['Agent Name'] = display_df['Agent Name'].apply(lambda x: truncate_text(x, 30))

            # Select All checkbox
            select_all = st.checkbox("Select All Guests", key=f'select_all_{selected_resort}')
            display_df['Select'] = select_all

            # Use session state
            if 'communication_data' not in st.session_state:
                st.session_state['communication_data'] = {}
            if selected_resort not in st.session_state['communication_data']:
                st.session_state['communication_data'][selected_resort] = {}

            # Apply existing comm data from session state
            for idx, row in display_df.iterrows():
                phone = row['Phone Number']
                if phone in st.session_state['communication_data'][selected_resort]:
                    comm_data = st.session_state['communication_data'][selected_resort][phone]
                    display_df.at[idx, 'Communication Status'] = comm_data.get('status', 'Not Checked')
                    display_df.at[idx, 'Last Communication Date'] = comm_data.get('date')
                    display_df.at[idx, 'Call Duration (seconds)'] = comm_data.get('duration')
                    display_df.at[idx, 'Agent Name'] = comm_data.get('agent', 'Unknown')
                    display_df.at[idx, 'Total Messages'] = comm_data.get('total_messages', 0)
                    display_df.at[idx, 'Total Calls'] = comm_data.get('total_calls', 0)
                    display_df.at[idx, 'Answered Calls'] = comm_data.get('answered_calls', 0)
                    display_df.at[idx, 'Missed Calls'] = comm_data.get('missed_calls', 0)
                    display_df.at[idx, 'Call Attempts'] = comm_data.get('call_attempts', 0)
                    display_df.at[idx, 'Pre-Arrival Calls'] = comm_data.get('pre_arrival_calls', 0)
                    display_df.at[idx, 'Pre-Arrival Texts'] = comm_data.get('pre_arrival_texts', 0)
                    display_df.at[idx, 'Post-Arrival Calls'] = comm_data.get('post_arrival_calls', 0)
                    display_df.at[idx, 'Post-Arrival Texts'] = comm_data.get('post_arrival_texts', 0)
                    display_df.at[idx, 'Calls Under 40 sec'] = comm_data.get('calls_under_40sec', 0)

            # Data editor
            display_df = display_df[
                [
                    'Select', 'Guest Name', 'Check In', 'Check Out',
                    'Phone Number', 'Rate Code', 'Price',
                    'Communication Status', 'Last Communication Date',
                    'Call Duration (seconds)', 'Agent Name',
                    'Total Messages', 'Total Calls', 'Answered Calls', 'Missed Calls', 'Call Attempts',
                    'Pre-Arrival Calls', 'Pre-Arrival Texts', 'Post-Arrival Calls', 'Post-Arrival Texts', 
                    'Calls Under 40 sec'
                ]
            ]

            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select or deselect this guest",
                        default=False,
                        width="60px"
                    ),
                    "Guest Name": st.column_config.TextColumn(
                        "Guest Name",
                        width="200px"
                    ),
                    "Check In": st.column_config.DateColumn(
                        "Check In",
                        width="120px"
                    ),
                    "Check Out": st.column_config.DateColumn(
                        "Check Out",
                        width="120px"
                    ),
                    "Phone Number": st.column_config.TextColumn(
                        "Phone Number",
                        width="150px"
                    ),
                    "Rate Code": st.column_config.TextColumn(
                        "Rate Code",
                        width="100px"
                    ),
                    "Price": st.column_config.NumberColumn(
                        "Price",
                        format="$%.2f",
                        width="100px"
                    ),
                    "Communication Status": st.column_config.TextColumn(
                        "Communication Status",
                        disabled=True,
                        width="150px"
                    ),
                    "Last Communication Date": st.column_config.TextColumn(
                        "Last Communication Date",
                        disabled=True,
                        width="180px"
                    ),
                    "Call Duration (seconds)": st.column_config.NumberColumn(
                        "Call Duration (seconds)",
                        format="%d",
                        disabled=True,
                        width="150px"
                    ),
                    "Agent Name": st.column_config.TextColumn(
                        "Agent Name",
                        disabled=True,
                        width="150px"
                    ),
                    "Total Messages": st.column_config.NumberColumn(
                        "Total Messages",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Total Calls": st.column_config.NumberColumn(
                        "Total Calls",
                        format="%d",
                        disabled=True,
                        width="100px"
                    ),
                    "Answered Calls": st.column_config.NumberColumn(
                        "Answered Calls",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Missed Calls": st.column_config.NumberColumn(
                        "Missed Calls",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Call Attempts": st.column_config.NumberColumn(
                        "Call Attempts",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Pre-Arrival Calls": st.column_config.NumberColumn(
                        "Pre-Arrival Calls",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Pre-Arrival Texts": st.column_config.NumberColumn(
                        "Pre-Arrival Texts",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Post-Arrival Calls": st.column_config.NumberColumn(
                        "Post-Arrival Calls",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Post-Arrival Texts": st.column_config.NumberColumn(
                        "Post-Arrival Texts",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Calls Under 40 sec": st.column_config.NumberColumn(
                        "Calls Under 40 sec",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key=f"guest_editor_{selected_resort}"
            )

            # Identify which rows are selected
            if 'Select' in edited_df.columns:
                edited_df['Select'] = edited_df['Select'].map({
                    True: True, False: False, 'True': True, 'False': False
                }).fillna(False).astype(bool)
                selected_guests = edited_df[edited_df['Select']]
            else:
                st.error("The 'Select' column is missing from the edited data.")
                selected_guests = pd.DataFrame()

            st.write("Display DataFrame after editing:")
            st.dataframe(edited_df.head())

            ############################
            # Fetch Communication Info
            ############################
            if st.button("Fetch Communication Info", key=f'fetch_info_{selected_resort}'):
                headers = {
                    "Authorization": OPENPHONE_API_KEY,
                    "Content-Type": "application/json"
                }

                # Only fetch for the selected rows:
                selected_data = selected_guests.copy().reset_index(drop=True)
                if not selected_data.empty:
                    with st.spinner("Fetching communication information for selected guests..."):
                        (
                            statuses, dates, durations, agent_names,
                            total_messages_list, total_calls_list,
                            answered_calls_list, missed_calls_list,
                            call_attempts_list,
                            pre_arrival_calls_list, pre_arrival_texts_list,
                            post_arrival_calls_list, post_arrival_texts_list,
                            calls_under_40sec_list
                        ) = fetch_communication_info_func(selected_data, headers)

                        # Update the main DataFrame & session state only for selected rows
                        for i in range(len(selected_data)):
                            phone = selected_data.at[i, 'Phone Number']
                            matching_idx = edited_df.index[edited_df['Phone Number'] == phone]
                            if not matching_idx.empty:
                                row_idx = matching_idx[0]
                                edited_df.at[row_idx, 'Communication Status'] = statuses[i]
                                edited_df.at[row_idx, 'Last Communication Date'] = dates[i]
                                edited_df.at[row_idx, 'Call Duration (seconds)'] = durations[i]
                                edited_df.at[row_idx, 'Agent Name'] = agent_names[i]
                                edited_df.at[row_idx, 'Total Messages'] = total_messages_list[i]
                                edited_df.at[row_idx, 'Total Calls'] = total_calls_list[i]
                                edited_df.at[row_idx, 'Answered Calls'] = answered_calls_list[i]
                                edited_df.at[row_idx, 'Missed Calls'] = missed_calls_list[i]
                                edited_df.at[row_idx, 'Call Attempts'] = call_attempts_list[i]
                                edited_df.at[row_idx, 'Pre-Arrival Calls'] = pre_arrival_calls_list[i]
                                edited_df.at[row_idx, 'Pre-Arrival Texts'] = pre_arrival_texts_list[i]
                                edited_df.at[row_idx, 'Post-Arrival Calls'] = post_arrival_calls_list[i]
                                edited_df.at[row_idx, 'Post-Arrival Texts'] = post_arrival_texts_list[i]
                                edited_df.at[row_idx, 'Calls Under 40 sec'] = calls_under_40sec_list[i]

                                # Also update session state
                                st.session_state['communication_data'][selected_resort][phone] = {
                                    'status': statuses[i],
                                    'date': dates[i],
                                    'duration': durations[i],
                                    'agent': agent_names[i],
                                    'total_messages': total_messages_list[i],
                                    'total_calls': total_calls_list[i],
                                    'answered_calls': answered_calls_list[i],
                                    'missed_calls': missed_calls_list[i],
                                    'call_attempts': call_attempts_list[i],
                                    'pre_arrival_calls': pre_arrival_calls_list[i],
                                    'pre_arrival_texts': pre_arrival_texts_list[i],
                                    'post_arrival_calls': post_arrival_calls_list[i],
                                    'post_arrival_texts': post_arrival_texts_list[i],
                                    'calls_under_40sec': calls_under_40sec_list[i]
                                }

                        st.success("Communication information updated for selected guests!")
                        # Force immediate re-run so the UI refreshes instantly:
                        st.rerun()
                else:
                    st.info("No guests selected to fetch communication info for.")

            ############################
            # Message Templates
            ############################
            st.markdown("---")
            st.subheader("Message Templates")

            message_templates = {
                "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
                "Check-in Follow-up": f"Hello, we hope you're enjoying your stay at {selected_resort}. Don't forget to collect your welcome gift at the concierge desk! 🎁",
                "Checkout Message": f"Thank you for staying with us at {selected_resort}! We hope you had a great stay. Please stop by the concierge desk before you leave for a special gift! 🎁"
            }
            selected_template = st.selectbox("Choose a Message Template", options=list(message_templates.keys()))
            message_preview = message_templates[selected_template]
            st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

            ############################
            # Send SMS to Selected Guests
            ############################
            selected_guests_updated = edited_df[edited_df['Select']]
            if not selected_guests_updated.empty:
                num_selected = len(selected_guests_updated)
                button_label = f"Send SMS to {num_selected} Guest{'s' if num_selected != 1 else ''}"
                if st.button(button_label):
                    openphone_url = "https://api.openphone.com/v1/messages"
                    headers_sms = {
                        "Authorization": OPENPHONE_API_KEY,
                        "Content-Type": "application/json"
                    }
                    sender_phone_number = OPENPHONE_NUMBER

                    for idx, row in selected_guests_updated.iterrows():
                        recipient_phone = row['Phone Number']
                        payload = {
                            "content": message_preview,
                            "from": sender_phone_number,
                            "to": [recipient_phone]
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

                        time.sleep(0.2)  # Rate limit
            else:
                st.info("No guests selected to send SMS.")
        else:
            st.warning("No data available for the selected filters.")
    else:
        st.warning("No data available for this resort.")
