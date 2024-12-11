############################################
# Marketing Tab
############################################
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

    # Initialize or check session state variables
    if 'default_dates' not in st.session_state:
        st.session_state['default_dates'] = {}

    # Set default dates to the earliest check-in and latest check-out
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        departure_dates = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        arrival_dates = arrival_dates.dropna()
        departure_dates = departure_dates.dropna()

        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else pd.to_datetime('today').date()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else pd.to_datetime('today').date()

        st.session_state['default_dates'] = {
            'check_in_start': min_check_in,
            'check_in_end': max_check_out,
            'check_out_start': min_check_in,
            'check_out_end': max_check_out,
        }

        # Function to reset filters (move this definition outside the if block)
        def reset_filters():
            # Retrieve default dates from session state
            default_dates = st.session_state['default_dates']
            
            # Clear the date input widgets by removing their keys from session state
            keys_to_remove = ['check_in_start', 'check_in_end', 'check_out_start', 'check_out_end']
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
            value=st.session_state.get('check_in_start', min_check_in),
            key='check_in_start'
        )

        check_in_end = st.date_input(
            "Check In Date (End)",
            value=st.session_state.get('check_in_end', max_check_out),
            key='check_in_end'
        )

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=st.session_state.get('check_out_start', min_check_in),
            key='check_out_start'
        )

        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=st.session_state.get('check_out_end', max_check_out),
            key='check_out_end'
        )

    with col3:
        if st.button("Reset Dates"):
            reset_filters()

    # Apply filters to the dataset
    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce').dt.date
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce').dt.date
    resort_df = resort_df.dropna(subset=['Check In', 'Check Out'])

    mask = (
        (resort_df['Check In'] >= st.session_state['check_in_start']) &
        (resort_df['Check In'] <= st.session_state['check_in_end']) &
        (resort_df['Check Out'] >= st.session_state['check_out_start']) &
        (resort_df['Check Out'] <= st.session_state['check_out_end'])
    )
    filtered_df = resort_df[mask]

    # Handle empty DataFrame
    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        display_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status', 'Last Communication Date'])
    else:
        # Prepare display DataFrame
        display_df = filtered_df[['Name', 'Check In', 'Check Out', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']

        # Function to format phone numbers
        def format_phone_number(phone):
            phone = ''.join(filter(str.isdigit, str(phone)))
            if len(phone) == 10:
                return f"+1{phone}"
            elif len(phone) == 11 and phone.startswith('1'):
                return f"+{phone}"
            else:
                return phone  # Return as is if it doesn't match expected patterns

        # Apply phone number formatting
        display_df['Phone Number'] = display_df['Phone Number'].apply(format_phone_number)
        display_df['Communication Status'] = 'Checking...'
        display_df['Last Communication Date'] = None  # Initialize the new column

        # Add "Select All" checkbox
        select_all = st.checkbox("Select All")
        display_df['Select'] = select_all

        ## Prepare headers for API calls
        headers = {
            "Authorization": OPENPHONE_API_KEY,
            "Content-Type": "application/json"
        }

        # Fetch communication statuses and dates
        statuses, dates, durations, agent_names = fetch_communication_info(display_df, headers)
        display_df['Communication Status'] = statuses
        display_df['Last Communication Date'] = dates
        display_df['Call Duration (seconds)'] = durations
        display_df['Agent Name'] = agent_names



        # Reorder columns to have "Select" as the leftmost column
        display_df = display_df[['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name']]

        # Interactive data editor
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select or deselect this guest",
                    default=select_all
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
                "Communication Status": st.column_config.TextColumn(
                    "Communication Status",
                    help="Last communication status with the guest",
                    disabled=True
                ),
                "Last Communication Date": st.column_config.TextColumn(
                    "Last Communication Date",
                    help="Date and time of the last communication with the guest",
                    disabled=True
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="guest_editor"
        )


I WANT  a button that triggers the fetch communication so nothing else with make it load, no refesh, sms button or check button or change dates. only when the button is clicked
