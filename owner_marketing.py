def run_owner_marketing_tab(owner_df):
    """Main function to run the owner marketing dashboard"""
    st.header("🏠 Owner Marketing Dashboard")

    if owner_df.empty:
        st.warning("No owner data available.")
        return

    # Create a copy of the dataframe to avoid modifying the original
    df = owner_df.copy()

    # Convert date columns
    date_columns = ['Sale Date', 'Maturity Date']
    for col in date_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except Exception as e:
                st.warning(f"Could not convert {col} to date format: {str(e)}")

    # Convert monetary columns
    money_columns = ['Closing Costs', 'Equity']
    for col in money_columns:
        if col in df.columns:
            try:
                # First, ensure the column is string type
                df[col] = df[col].astype(str)
                # Remove currency symbols and commas
                df[col] = df[col].replace('[\$,]', '', regex=True)
                # Convert to float, replacing errors with NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                st.warning(f"Could not convert {col} to numeric format: {str(e)}")

    # Ensure Points column is numeric
    if 'Points' in df.columns:
        try:
            df['Points'] = pd.to_numeric(df['Points'], errors='coerce')
        except Exception as e:
            st.warning(f"Could not convert Points to numeric format: {str(e)}")

    # Ensure FICO score is numeric
    if 'Primary FICO' in df.columns:
        try:
            df['Primary FICO'] = pd.to_numeric(df['Primary FICO'], errors='coerce')
        except Exception as e:
            st.warning(f"Could not convert Primary FICO to numeric format: {str(e)}")

    # Filters Section
    st.subheader("Filter Owners")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Unit Type Filter
        if 'Unit' in df.columns:
            unit_types = ['All'] + sorted(df['Unit'].unique().tolist())
            selected_unit = st.selectbox('Unit Type', unit_types)
        
        # State Filter
        if 'State' in df.columns:
            states = ['All'] + sorted(df['State'].unique().tolist())
            selected_state = st.selectbox('State', states)

    with col2:
        # Date Range Filter
        if 'Sale Date' in df.columns and df['Sale Date'].notna().any():
            min_date = df['Sale Date'].min().date()
            max_date = df['Sale Date'].max().date()
            date_range = st.date_input(
                'Sale Date Range',
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )

        # FICO Score Range
        if 'Primary FICO' in df.columns and df['Primary FICO'].notna().any():
            min_fico = int(df['Primary FICO'].min())
            max_fico = int(df['Primary FICO'].max())
            fico_range = st.slider(
                'FICO Score Range',
                min_value=min_fico,
                max_value=max_fico,
                value=(min_fico, max_fico)
            )

    with col3:
        # Points Range
        if 'Points' in df.columns and df['Points'].notna().any():
            min_points = int(df['Points'].min())
            max_points = int(df['Points'].max())
            points_range = st.slider(
                'Points Range',
                min_value=min_points,
                max_value=max_points,
                value=(min_points, max_points)
            )

    # Apply filters
    filtered_df = df.copy()
    
    if 'Unit' in df.columns and selected_unit != 'All':
        filtered_df = filtered_df[filtered_df['Unit'] == selected_unit]
    
    if 'State' in df.columns and selected_state != 'All':
        filtered_df = filtered_df[filtered_df['State'] == selected_state]
    
    if 'Sale Date' in filtered_df.columns and 'date_range' in locals():
        filtered_df = filtered_df[
            (filtered_df['Sale Date'].dt.date >= date_range[0]) &
            (filtered_df['Sale Date'].dt.date <= date_range[1])
        ]
    
    if 'Primary FICO' in filtered_df.columns and 'fico_range' in locals():
        filtered_df = filtered_df[
            (filtered_df['Primary FICO'] >= fico_range[0]) &
            (filtered_df['Primary FICO'] <= fico_range[1])
        ]
    
    if 'Points' in filtered_df.columns and 'points_range' in locals():
        filtered_df = filtered_df[
            (filtered_df['Points'] >= points_range[0]) &
            (filtered_df['Points'] <= points_range[1])
        ]

    # Add Select column
    filtered_df.insert(0, 'Select', False)

    # Create the editable dataframe
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select owner for communication"),
            "Account ID": st.column_config.TextColumn("Account ID"),
            "Last Name": st.column_config.TextColumn("Last Name"),
            "First Name": st.column_config.TextColumn("First Name"),
            "Unit": st.column_config.TextColumn("Unit"),
            "Sale Date": st.column_config.DateColumn("Sale Date"),
            "Address": st.column_config.TextColumn("Address"),
            "City": st.column_config.TextColumn("City"),
            "State": st.column_config.TextColumn("State"),
            "Zip Code": st.column_config.TextColumn("Zip Code"),
            "Primary FICO": st.column_config.NumberColumn("Primary FICO"),
            "Maturity Date": st.column_config.DateColumn("Maturity Date"),
            "Closing Costs": st.column_config.NumberColumn("Closing Costs", format="$%.2f"),
            "Phone Number": st.column_config.TextColumn("Phone Number"),
            "Email Address": st.column_config.TextColumn("Email Address"),
            "Points": st.column_config.NumberColumn("Points"),
            "Equity": st.column_config.NumberColumn("Equity", format="$%.2f")
        },
        hide_index=True,
        use_container_width=True
    )

    # Summary Statistics
    st.subheader("Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Owners", len(filtered_df))
    with col2:
        if 'Points' in filtered_df.columns:
            st.metric("Average Points", f"{filtered_df['Points'].mean():,.0f}")
    with col3:
        if 'Primary FICO' in filtered_df.columns:
            st.metric("Average FICO", f"{filtered_df['Primary FICO'].mean():.0f}")
    with col4:
        st.metric("Selected Owners", len(filtered_df[filtered_df['Select']]))

    # Rest of your code...

    return edited_df
