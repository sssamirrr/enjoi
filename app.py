# Process and display data
if not resort_df.empty:
    # Existing code to process resort_df...
    
    if f'display_df_{selected_resort}' in st.session_state:
        display_df = st.session_state[f'display_df_{selected_resort}']
    else:
        # Prepare the
        display DataFrame using your function
        display_df = prepare_display_dataframe(filtered_df)
        st.session_state[f'display_df_{selected_resort}'] = display_df
else:
    st.warning("No data available for the selected filters.")
