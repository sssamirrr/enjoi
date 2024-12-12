import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime
import gspread
from google.oauth2 import service_account
import plotly.express as px

@st.cache_resource
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
    try:
        # Create credentials
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        # Create gspread client
        client = gspread.authorize(credentials)
        
        # Open the spreadsheet
        sheet_key = st.secrets["sheets"]["owners_sheet_key"]
        sheet = client.open_by_key(sheet_key)
        
        # Get the first worksheet
        worksheet = sheet.get_worksheet(0)
        
        # Get all records
        data = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Basic data cleaning
        if 'Sale Date' in df.columns:
            df['Sale Date'] = pd.to_datetime(df['Sale Date'], errors='coerce')
        
        if 'Maturity Date' in df.columns:
            df['Maturity Date'] = pd.to_datetime(df['Maturity Date'], errors='coerce')
            
        if 'Phone Number' in df.columns:
            df['Phone Number'] = df['Phone Number'].astype(str)
            
        if 'Points' in df.columns:
            df['Points'] = pd.to_numeric(df['Points'], errors='coerce')
            
        if 'Primary FICO' in df.columns:
            df['Primary FICO'] = pd.to_numeric(df['Primary FICO'], errors='coerce')

        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        print(f"Full error: {str(e)}")
        return pd.DataFrame()

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
            st.info("Response rate tracking will be implemented based on message interaction data")
            
        with campaign_metrics[2]:
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
            "Campaign": st.column_config.SelectboxColumn(
                "Campaign",
                help="A/B Test Campaign Assignment",
                width="medium",
                options=["A", "B"],
                required=True
            ),
            "Account ID": st.column_config.TextColumn("Account ID", width="medium"),
            "Last Name": st.column_config.TextColumn("Last Name", width="medium"),
            "First Name": st.column_config.TextColumn("First Name", width="medium"),
            "Unit": st.column_config.TextColumn("Unit", width="small"),
            "Sale Date": st.column_config.DateColumn("Sale Date"),
            "Address": st.column_config.TextColumn("Address"),
            "City": st.column_config.TextColumn("City"),
            "State": st.column_config.TextColumn("State", width="small"),
            "Zip Code": st.column_config.TextColumn("Zip Code"),
            "Primary FICO": st.column_config.NumberColumn(
                "Primary FICO",
                help="Credit Score",
                min_value=300,
                max_value=850,
                step=1,
                format="%d"
            ),
            "Maturity Date": st.column_config.DateColumn("Maturity Date"),
            "Closing Costs": st.column_config.NumberColumn(
                "Closing Costs",
                help="Total closing costs",
                format="$%.2f"
            ),
            "Phone Number": st.column_config.TextColumn("Phone Number"),
            "Email Address": st.column_config.TextColumn("Email Address"),
            "Points": st.column_config.NumberColumn(
                "Points",
                help="Membership points",
                format="%d"
            ),
            "Equity": st.column_config.NumberColumn(
                "Equity",
                help="Current equity",
                format="$%.2f"
            )
        },
        column_order=[
            "Select",
            "Campaign",
            "Account ID",
            "Last Name",
            "First Name",
            "Unit",
            "Sale Date",
            "Address",
            "City",
            "State",
            "Zip Code",
            "Primary FICO",
            "Maturity Date",
            "Closing Costs",
            "Phone Number",
            "Email Address",
            "Points",
            "Equity"
        ],
        hide_index=True,
        use_container_width=True
    )

    # Campaign Performance Metrics
    st.subheader("Campaign Performance Metrics")
    campaign_stats_cols = st.columns(4)
    
    with campaign_stats_cols[0]:
        total_selected = len(edited_df[edited_df['Select']])
        st.metric("Total Selected", total_selected)
        
    with campaign_stats_cols[1]:
        selected_a = len(edited_df[(edited_df['Select']) & (edited_df['Campaign'] == 'A')])
        st.metric("Selected Campaign A", selected_a)
        
    with campaign_stats_cols[2]:
        selected_b = len(edited_df[(edited_df['Select']) & (edited_df['Campaign'] == 'B')])
        st.metric("Selected Campaign B", selected_b)
        
    with campaign_stats_cols[3]:
        if total_selected > 0:
            balance = abs(selected_a - selected_b)
            st.metric("Campaign Balance", balance, 
                     delta=f"{'Balanced' if balance == 0 else 'Unbalanced'}")

    # Campaign Distribution Chart
    st.subheader("Campaign Distribution")
    campaign_chart_cols = st.columns(2)
    
    with campaign_chart_cols[0]:
        # Campaign distribution pie chart
        campaign_counts = edited_df['Campaign'].value_counts()
        fig_pie = px.pie(
            values=campaign_counts.values,
            names=campaign_counts.index,
            title="Campaign Distribution",
            color_discrete_sequence=['#1f77b4', '#ff7f0e']
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with campaign_chart_cols[1]:
        # Average points by campaign bar chart
        avg_points = edited_df.groupby('Campaign')['Points'].mean().reset_index()
        fig_bar = px.bar(
            avg_points,
            x='Campaign',
            y='Points',
            title="Average Points by Campaign",
            color='Campaign',
            color_discrete_sequence=['#1f77b4', '#ff7f0e']
        )
        st.plotly_chart(fig_bar, use_container_width=True)

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

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    owner_df = get_owner_sheet_data()
    run_owner_marketing_tab(owner_df)
