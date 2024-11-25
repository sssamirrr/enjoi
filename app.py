# Modified Marketing Tab (Tab2) section - replace the previous tab2 section with this:

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
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if st.button('Select/Deselect All'):
            if len(st.session_state.selected_rows) < len(display_df):
                st.session_state.selected_rows = set(display_df.index)
            else:
                st.session_state.selected_rows = set()

    # Create a selection column
    display_df['Select'] = False

    # Create a wider display using custom CSS
    st.markdown("""
        <style>
        .stDataFrame {
            width: 100%;
        }
        .dataframe-container {
            margin-top: 1rem;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Display sortable table with checkboxes
    st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
    
    # Convert the display DataFrame to include checkboxes
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select guest",
                default=False,
            ),
            "Guest Name": st.column_config.TextColumn("Guest Name", width="medium"),
            "Check In": st.column_config.DateColumn("Check In", width="medium"),
            "Check Out": st.column_config.DateColumn("Check Out", width="medium"),
            "Phone Number": st.column_config.TextColumn("Phone Number", width="medium"),
        },
        hide_index=True,
        width=None
    )

    # Update selected rows based on checkboxes
    st.session_state.selected_rows = set(edited_df[edited_df['Select']].index)

    # Message selection and preview
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
    
    # Show message preview immediately
    with col2:
        st.text_area("Message Preview", 
                     value=message_options[selected_message],
                     height=100,
                     disabled=True)
    
    # Send button and selection info
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        if st.button('Send Messages to Selected Guests'):
            selected_guests = edited_df[edited_df['Select']]
            if len(selected_guests) > 0:
                st.success(f"Messages would be sent to {len(selected_guests)} guests")
                # Here you would implement actual SMS sending logic
            else:
                st.warning("Please select at least one guest")
    
    with col2:
        selected_count = len(edited_df[edited_df['Select']])
        st.info(f"Selected guests: {selected_count}")
    
    # Add export functionality
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Guest List",
        csv,
        f"{selected_resort}_guest_list.csv",
        "text/csv",
        key='download-csv'
    )
