import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime
import gspread
from google.oauth2 import service_account

@st.cache_resource
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
    try:
        # Retrieve Google Sheets credentials from st.secrets
        service_account_info = st.secrets["gcp_service_account"]
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["owner_sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error connecting to Owner Google Sheet: {str(e)}")
        return pd.DataFrame()

def cleanup_phone_number(phone):
    """Clean up phone number format"""
    if pd.isna(phone):
        return 'No Data'
    phone = ''.join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith('1'):
        return f"+{phone}"
    return phone

def fetch_communication_info(guest_df, headers):
    """Fetch communication info for owners"""
    statuses, dates, durations, agent_names = [], [], [], []
    
    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        if phone and phone != 'No Data':
            try:
                status, last_date, duration, agent_name = get_last_communication_info(phone, headers)
                statuses.append(status)
                dates.append(last_date)
                durations.append(duration)
                agent_names.append(agent_name)
            except Exception as e:
                statuses.append("Error")
                dates.append(None)
                durations.append(None)
                agent_names.append("Unknown")
        else:
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")

    return statuses, dates, durations, agent_names

def get_last_communication_info(phone_number, headers):
    """Placeholder for actual OpenPhone API call"""
    # Replace with actual API implementation
    return "No Communication", None, None, "Unknown"

def run_owner_marketing_tab(owner_df):
    """Main function to run the owner marketing dashboard"""
    st.header("🏠 Owner Marketing Dashboard")

    if owner_df.empty:
        st.warning("No owner data available.")
        return

    # Convert date columns
    date_columns = ['Sale Date', 'Maturity Date']
    for col in date_columns:
        if col in owner_df.columns:
            owner_df[col] = pd.to_datetime(owner_df[col], errors='coerce')

    # Convert monetary columns
    money_columns = ['Closing Costs', 'Equity']
    for col in money_columns:
        if col in owner_df.columns:
            owner_df[col] = owner_df[col].replace({'\$': '', ',': ''}, regex=True).astype(float)

    # Filters Section
    st.subheader("Filter Owners")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Unit Type Filter
        if 'Unit' in owner_df.columns:
            unit_types = ['All'] + sorted(owner_df['Unit'].unique().tolist())
            selected_unit = st.selectbox('Unit Type', unit_types)
        
        # State Filter
        if 'State' in owner_df.columns:
            states = ['All'] + sorted(owner_df['State'].unique().tolist())
            selected_state = st.selectbox('State', states)

    with col2:
        # Date Range Filter
        if 'Sale Date' in owner_df.columns:
            date_range = st.date_input(
                'Sale Date Range',
                value=(
                    owner_df['Sale Date'].min().date(),
                    owner_df['Sale Date'].max().date()
                )
            )

        # FICO Score Range
        if 'Primary FICO' in owner_df.columns:
            fico_range = st.slider(
                'FICO Score Range',
                min_value=300,
                max_value=850,
                value=(500, 850)
            )

    with col3:
        # Points Range
        if 'Points' in owner_df.columns:
            points_range = st.slider(
                'Points Range',
                min_value=int(owner_df['Points'].min()),
                max_value=int(owner_df['Points'].max()),
                value=(int(owner_df['Points'].min()), int(owner_df['Points'].max()))
            )

    # Apply filters
    filtered_df = owner_df.copy()
    
    if selected_unit != 'All':
        filtered_df = filtered_df[filtered_df['Unit'] == selected_unit]
    
    if selected_state != 'All':
        filtered_df = filtered_df[filtered_df['State'] == selected_state]
    
    if 'Sale Date' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Sale Date'].dt.date >= date_range[0]) &
            (filtered_df['Sale Date'].dt.date <= date_range[1])
        ]
    
    if 'Primary FICO' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Primary FICO'] >= fico_range[0]) &
            (filtered_df['Primary FICO'] <= fico_range[1])
        ]
    
    if 'Points' in filtered_df.columns:
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
        st.metric("Average Points", f"{filtered_df['Points'].mean():,.0f}")
    with col3:
        st.metric("Average FICO", f"{filtered_df['Primary FICO'].mean():.0f}")
    with col4:
        st.metric("Selected Owners", len(filtered_df[filtered_df['Select']]))

    # Message Templates Section
    st.markdown("---")
    st.subheader("Owner Message Templates")

    templates = {
        "Welcome": "Welcome to our timeshare family! We're excited to have you with us.",
        "Payment Reminder": "This is a friendly reminder about your upcoming payment due on {due_date}.",
        "Special Offer": "As a valued owner, we'd like to offer you a special upgrade opportunity.",
        "Maintenance Notice": "Important information about upcoming maintenance in your unit.",
        "Custom Message": ""
    }

    template_choice = st.selectbox("Select Message Template", list(templates.keys()))
    message_text = st.text_area(
        "Customize Your Message",
        value=templates[template_choice],
        height=100
    )

    # Send Messages Section
    selected_owners = edited_df[edited_df['Select']]
    if len(selected_owners) > 0:
        st.write(f"Selected {len(selected_owners)} owners for communication")
        
        if st.button("Send Messages to Selected Owners"):
            with st.spinner("Sending messages..."):
                for _, owner in selected_owners.iterrows():
                    try:
                        # Replace with actual message sending logic
                        st.success(f"Message sent to {owner['First Name']} {owner['Last Name']}")
                        time.sleep(0.5)  # Simulate API call
                    except Exception as e:
                        st.error(f"Failed to send message to {owner['First Name']} {owner['Last Name']}: {str(e)}")
    else:
        st.info("Please select owners to send messages")

    return edited_df

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    # Test data for development
    test_data = {
        "Account ID": ["123", "456"],
        "First Name": ["John", "Jane"],
        "Last Name": ["Doe", "Smith"],
        "Unit": ["2BR", "1BR"],
        "Points": [1000, 2000]
    }
    test_df = pd.DataFrame(test_data)
    run_owner_marketing_tab(test_df)
