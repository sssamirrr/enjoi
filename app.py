import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Sample data - replace this with your actual data loading logic
@st.cache_data
def load_data():
    # Replace this with your actual data loading code
    df = pd.DataFrame({
        'Market': ['Resort A', 'Resort B', 'Resort C'],
        'Name': ['Guest 1', 'Guest 2', 'Guest 3'],
        'Arrival Date Short': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'Departure Date Short': ['2024-01-05', '2024-01-06', '2024-01-07'],
        'Phone Number': ['123-456-7890', '234-567-8901', '345-678-9012'],
        '# Nights': [4, 4, 4],
        'Rate Code Name': ['Standard', 'Premium', 'Deluxe']
    })
    return df

# Load the data
df = load_data()

# Create tabs
tab1, tab2 = st.tabs(["Dashboard", "Marketing"])

# Dashboard Tab
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    # Your existing dashboard code here...

# Marketing Tab
with tab2:
    st.title("📊 Marketing Information by Resort")
    
    # Correct syntax for selectbox
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
    
    # Create display DataFrame
    display_df = resort_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
    display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
    
    # Convert dates
    display_df['Check In'] = pd.to_datetime(display_df['Check In'])
    display_df['Check Out'] = pd.to_datetime(display_df['Check Out'])
    
    # Apply filters
    mask = (
        (display_df['Check In'].dt.date >= check_in_filter[0]) &
        (display_df['Check In'].dt.date <= check_in_filter[1]) &
        (display_df['Check Out'].dt.date >= check_out_filter[0]) &
        (display_df['Check Out'].dt.date <= check_out_filter[1])
    )
    display_df = display_df[mask]

    # Add selection column
    display_df['Select'] = False

    # Display table
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select guest",
                default=False,
            )
        },
        hide_index=True
    )

    # Message templates
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
    
    # Send button and selection info
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        if st.button('Send Messages to Selected Guests'):
            selected_guests = edited_df[edited_df['Select']]
            if len(selected_guests) > 0:
                st.success(f"Messages would be sent to {len(selected_guests)} guests")
            else:
                st.warning("Please select at least one guest")
    
    with col2:
        selected_count = len(edited_df[edited_df['Select']])
        st.info(f"Selected guests: {selected_count}")
    
    # Export functionality
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Guest List",
        csv,
        f"{selected_resort}_guest_list.csv",
        "text/csv",
        key='download-csv'
    )

# Show raw data
with st.expander("Show Raw Data"):
    st.dataframe(df)
