def run_owner_marketing_tab(owner_df):
    """Main function to run the owner marketing dashboard"""
    st.header("🏠 Owner Marketing Dashboard")

    if owner_df.empty:
        st.warning("No owner data available.")
        return

    # Create Campaign Analysis section
    st.subheader("Campaign Analysis")
    if 'Campaign' in owner_df.columns:
        campaign_metrics = st.tabs(["Campaign Overview", "Response Rates", "Conversion Analysis"])
        
        with campaign_metrics[0]:
            col1, col2 = st.columns(2)
            
            with col1:
                # Campaign distribution
                campaign_dist = owner_df['Campaign'].value_counts()
                st.metric("Campaign A Count", campaign_dist.get('A', 0))
                st.metric("Campaign B Count", campaign_dist.get('B', 0))
                
            with col2:
                # Average metrics by campaign
                if 'Points' in owner_df.columns:
                    avg_points = owner_df.groupby('Campaign')['Points'].mean()
                    st.metric("Avg Points - Campaign A", f"{avg_points.get('A', 0):,.0f}")
                    st.metric("Avg Points - Campaign B", f"{avg_points.get('B', 0):,.0f}")

        with campaign_metrics[1]:
            # Add response rate metrics here when implemented
            st.info("Response rate tracking will be implemented based on message interaction data")
            
        with campaign_metrics[2]:
            # Add conversion analysis here when implemented
            st.info("Conversion analysis will be implemented based on sales/upgrade data")

    # Filters Section
    st.subheader("Filter Owners")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'Unit' in owner_df.columns:
            unit_types = ['All'] + sorted(owner_df['Unit'].unique().tolist())
            selected_unit = st.selectbox('Unit Type', unit_types)
        
        if 'State' in owner_df.columns:
            states = ['All'] + sorted(owner_df['State'].unique().tolist())
            selected_state = st.selectbox('State', states)

    with col2:
        if 'Sale Date' in owner_df.columns:
            date_range = st.date_input(
                'Sale Date Range',
                value=(
                    owner_df['Sale Date'].min().date(),
                    owner_df['Sale Date'].max().date()
                )
            )

    with col3:
        if 'Primary FICO' in owner_df.columns:
            fico_range = st.slider(
                'FICO Score Range',
                min_value=300,
                max_value=850,
                value=(500, 850)
            )

    with col4:
        if 'Campaign' in owner_df.columns:
            campaigns = ['All'] + sorted(owner_df['Campaign'].unique().tolist())
            selected_campaign = st.selectbox('Campaign', campaigns)

    # Apply filters
    filtered_df = owner_df.copy()
    
    if selected_unit != 'All':
        filtered_df = filtered_df[filtered_df['Unit'] == selected_unit]
    
    if selected_state != 'All':
        filtered_df = filtered_df[filtered_df['State'] == selected_state]
    
    if selected_campaign != 'All':
        filtered_df = filtered_df[filtered_df['Campaign'] == selected_campaign]

    # Add Select column
    filtered_df.insert(0, 'Select', False)

    # Create the editable dataframe
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select owner for communication"),
            "Campaign": st.column_config.TextColumn("Campaign", help="A/B Test Campaign"),
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

    # Campaign Performance Metrics
    st.subheader("Campaign Performance Metrics")
    if 'Campaign' in edited_df.columns:
        metric_cols = st.columns(4)
        
        with metric_cols[0]:
            total_selected = len(edited_df[edited_df['Select']])
            st.metric("Total Selected", total_selected)
            
        with metric_cols[1]:
            selected_a = len(edited_df[(edited_df['Select']) & (edited_df['Campaign'] == 'A')])
            st.metric("Selected Campaign A", selected_a)
            
        with metric_cols[2]:
            selected_b = len(edited_df[(edited_df['Select']) & (edited_df['Campaign'] == 'B')])
            st.metric("Selected Campaign B", selected_b)
            
        with metric_cols[3]:
            if total_selected > 0:
                balance = abs(selected_a - selected_b)
                st.metric("Campaign Balance", balance, 
                         delta=f"{'Balanced' if balance == 0 else 'Unbalanced'}")

    # Message Templates Section with Campaign-specific messages
    st.markdown("---")
    st.subheader("Campaign Message Templates")

    templates = {
        "Campaign A - Welcome": "Welcome to our premium timeshare family! We're excited to have you with us.",
        "Campaign A - Offer": "As a valued premium member, we have a special upgrade opportunity for you.",
        "Campaign B - Welcome": "Welcome to our timeshare community! We're glad you're here.",
        "Campaign B - Offer": "We'd like to present you with an exclusive upgrade opportunity.",
        "Custom Message": ""
    }

    template_choice = st.selectbox("Select Message Template", list(templates.keys()))
    message_text = st.text_area(
        "Customize Your Message",
        value=templates[template_choice],
        height=100
    )

    # Send Messages Section with Campaign tracking
    selected_owners = edited_df[edited_df['Select']]
    if len(selected_owners) > 0:
        st.write(f"Selected {len(selected_owners)} owners for communication")
        campaign_breakdown = selected_owners['Campaign'].value_counts()
        st.write(f"Campaign A: {campaign_breakdown.get('A', 0)}, Campaign B: {campaign_breakdown.get('B', 0)}")
        
        if st.button("Send Campaign Messages"):
            with st.spinner("Sending messages..."):
                for _, owner in selected_owners.iterrows():
                    try:
                        # Here you would implement your actual message sending logic
                        # Make sure to use the appropriate template based on the campaign
                        campaign_specific_message = message_text
                        if owner['Campaign'] == 'A':
                            # Modify message for Campaign A
                            pass
                        else:
                            # Modify message for Campaign B
                            pass
                            
                        st.success(f"Campaign {owner['Campaign']} message sent to {owner['First Name']} {owner['Last Name']}")
                        time.sleep(0.5)
                    except Exception as e:
                        st.error(f"Failed to send message to {owner['First Name']} {owner['Last Name']}: {str(e)}")
    else:
        st.info("Please select owners to send campaign messages")

    return edited_df
