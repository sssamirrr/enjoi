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

    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=dataset_min_date,
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_in_start"
        )
        check_in_end = st.date_input(
            "Check In Date (End)",
            value=dataset_max_date,
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_in_end"
        )
    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=dataset_min_date,
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_out_start"
        )
        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=dataset_max_date,
            min_value=dataset_min_date,
            max_value=dataset_max_date,
            key="check_out_end"
        )

    # Apply filters to the dataset
    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

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

        # Interactive data editor with the Select/Deselect functionality
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
            },
            hide_index=True,
            use_container_width=True,
            key="data_editor"
        )

        # Display count of selected guests
        selected_count = edited_df['Select'].sum()
        st.write(f"Selected Guests: {selected_count}")

