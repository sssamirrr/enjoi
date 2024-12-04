# Marketing Tab
with tab2:
    st.title("📊 Marketing Information by Resort")
    
    # Determine dynamic min and max dates from the dataset
    dataset_min_date = pd.to_datetime(df['Arrival Date Short']).min().date()
    dataset_max_date = pd.to_datetime(df['Departure Date Short']).max().date()

    # Initialize session state for dates dynamically
    if 'check_in_start' not in st.session_state:
        st.session_state['check_in_start'] = dataset_min_date
    if 'check_in_end' not in st.session_state:
        st.session_state['check_in_end'] = dataset_max_date
    if 'check_out_start' not in st.session_state:
        st.session_state['check_out_start'] = dataset_min_date
    if 'check_out_end' not in st.session_state:
        st.session_state['check_out_end'] = dataset_max_date
    
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
                value=st.session_state['check_in_start'],
                key="check_in_start_input",
                min_value=dataset_min_date,
                max_value=dataset_max_date
            )
            check_in_end = st.date_input(
                "Check In Date (End)",
                value=st.session_state['check_in_end'],
                key="check_in_end_input",
                min_value=dataset_min_date,
                max_value=dataset_max_date
            )
        
        with col2:
            check_out_start = st.date_input(
                "Check Out Date (Start)",
                value=st.session_state['check_out_start'],
                key="check_out_start_input",
                min_value=dataset_min_date,
                max_value=dataset_max_date
            )
            check_out_end = st.date_input(
                "Check Out Date (End)",
                value=st.session_state['check_out_end'],
                key="check_out_end_input",
                min_value=dataset_min_date,
                max_value=dataset_max_date
            )
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button('Reset Dates'):
                # Reset session state values dynamically
                st.session_state['check_in_start'] = dataset_min_date
                st.session_state['check_in_end'] = dataset_max_date
                st.session_state['check_out_start'] = dataset_min_date
                st.session_state['check_out_end'] = dataset_max_date
                
                # Use rerun only when session state is safely updated
                st.experimental_rerun()

    # Validation for invalid date ranges
    invalid_date_range = False

    if check_in_start > check_in_end:
        st.warning("Check-In Start Date cannot be after Check-In End Date. Resetting to default values.")
        st.session_state['check_in_start'] = dataset_min_date
        st.session_state['check_in_end'] = dataset_max_date
        invalid_date_range = True

    if check_out_start > check_out_end:
        st.warning("Check-Out Start Date cannot be after Check-Out End Date. Resetting to default values.")
        st.session_state['check_out_start'] = dataset_min_date
        st.session_state['check_out_end'] = dataset_max_date
        invalid_date_range = True

    if invalid_date_range:
        st.experimental_rerun()

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
        if 'Select' not in display_df.columns:
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
                    st.experimental_rerun()
            
            with col2:
                if st.button("Deselect All", key="deselect_all"):
                    st.session_state.select_all_state = False
                    st.experimental_rerun()

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
        selected_guests = edited_df[
