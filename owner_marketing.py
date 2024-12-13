import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import requests

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
        sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
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

        # Ensure Campaign Type column exists
        if 'Campaign Type' not in df.columns:
            df['Campaign Type'] = 'Text'  # Default campaign type

        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        return pd.DataFrame()

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    if pd.isna(phone):
        return None
    # Remove any non-numeric characters
    phone = ''.join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith('1'):
        return f"+{phone}"
    return None

def send_email(recipient, subject, body):
    """
    Send email using your email service provider
    Implement your email sending logic here
    """
    try:
        # Add your email sending logic here
        return True
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        return False

def send_text_message(phone_number, message):
    """
    Send text message using your SMS service provider
    Implement your SMS sending logic here
    """
    try:
        # Add your SMS sending logic here
        return True
    except Exception as e:
        st.error(f"Error sending text message: {str(e)}")
        return False

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")
    
    # Campaign Type Selection
    campaign_tabs = st.tabs(["📱 Text Message Campaign", "📧 Email Campaign"])
    
    # Process each campaign type
    for idx, campaign_type in enumerate(["Text", "Email"]):
        with campaign_tabs[idx]:
            st.header(f"{campaign_type} Campaign Management")
            
            # Filters Section
            with st.expander("📊 Filters", expanded=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if 'State' in owner_df.columns:
                        states = sorted(owner_df['State'].unique().tolist())
                        selected_states = st.multiselect(
                            'Select States',
                            states,
                            key=f'{campaign_type}_states'
                        )
                    
                    if 'Unit' in owner_df.columns:
                        units = ['All'] + sorted(owner_df['Unit'].unique().tolist())
                        selected_unit = st.selectbox(
                            'Unit Type',
                            units,
                            key=f'{campaign_type}_unit'
                        )
                
                with col2:
                    if 'Sale Date' in owner_df.columns:
                        date_range = st.date_input(
                            'Sale Date Range',
                            value=(
                                owner_df['Sale Date'].min().date(),
                                owner_df['Sale Date'].max().date()
                            ),
                            key=f'{campaign_type}_dates'
                        )
                
                with col3:
                    if 'Primary FICO' in owner_df.columns:
                        try:
                            min_fico = int(filtered_df['Primary FICO'].min())
                            max_fico = int(filtered_df['Primary FICO'].max())
                            default_min = max(300, min_fico)
                            default_max = min(850, max_fico)
                            
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(default_min, default_max)
                            )
                        except:
                            # If there's an error, use default FICO range
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(500, 850)
                            )

            # Apply filters
            filtered_df = owner_df.copy()
            
            # Filter by campaign type
            filtered_df = filtered_df[filtered_df['Campaign Type'] == campaign_type]
            
            # Apply other filters
            if selected_states:
                filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
            
            if selected_unit != 'All':
                filtered_df = filtered_df[filtered_df['Unit'] == selected_unit]
            
            if isinstance(date_range, tuple) and len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['Sale Date'].dt.date >= date_range[0]) &
                    (filtered_df['Sale Date'].dt.date <= date_range[1])
                ]
            
            if 'Primary FICO' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['Primary FICO'] >= fico_range[0]) &
                    (filtered_df['Primary FICO'] <= fico_range[1])
                ]

            # Display metrics
            metrics_cols = st.columns(4)
            with metrics_cols[0]:
                st.metric("Total Owners", len(filtered_df))
            with metrics_cols[1]:
                st.metric("Average FICO", 
                         int(filtered_df['Primary FICO'].mean()))
            with metrics_cols[2]:
                st.metric("Average Points", 
                         int(filtered_df['Points'].mean()))
            with metrics_cols[3]:
                total_value = filtered_df['Points'].sum() * 0.20  # Example value calculation
                st.metric("Total Value", f"${total_value:,.2f}")

            # Campaign Setup
            st.subheader("Campaign Setup")
            
            # A/B Testing setup
            col1, col2 = st.columns(2)
            with col1:
                ab_split = st.slider(
                    "A/B Testing Split (A:B)",
                    0, 100, 50,
                    key=f'{campaign_type}_split'
                )
            with col2:
                st.metric("Group A Size", f"{len(filtered_df) * ab_split // 100}")
                st.metric("Group B Size", f"{len(filtered_df) * (100-ab_split) // 100}")

            # Message Templates
            st.subheader("Message Templates")
            
            if campaign_type == "Email":
                # Email specific templates
                email_templates = {
                    "Welcome": {
                        "subject": "Welcome to Our Premium Ownership Family",
                        "body": "Dear {first_name},\n\nWelcome to..."
                    },
                    "Upgrade Offer": {
                        "subject": "Exclusive Upgrade Opportunity",
                        "body": "Dear {first_name},\n\nAs a valued member..."
                    },
                    "Custom": {
                        "subject": "",
                        "body": ""
                    }
                }
                
                template_choice = st.selectbox(
                    "Select Email Template",
                    list(email_templates.keys()),
                    key='email_template'
                )
                
                subject = st.text_input(
                    "Email Subject",
                    value=email_templates[template_choice]["subject"]
                )
                
                message = st.text_area(
                    "Email Body",
                    value=email_templates[template_choice]["body"],
                    height=200
                )
                
            else:
                # Text message specific templates
                text_templates = {
                    "Welcome": "Welcome to our premium ownership family! Reply STOP to opt out.",
                    "Upgrade": "Exclusive upgrade opportunity available! Reply STOP to opt out.",
                    "Custom": ""
                }
                
                template_choice = st.selectbox(
                    "Select Text Template",
                    list(text_templates.keys()),
                    key='text_template'
                )
                
                message = st.text_area(
                    "Message Text",
                    value=text_templates[template_choice],
                    height=100
                )

            # Preview Section
            st.subheader("Campaign Preview")
            preview_cols = st.columns(2)
            with preview_cols[0]:
                st.write("Group A Preview:")
                if campaign_type == "Email":
                    st.info(f"Subject: {subject}\n\n{message}")
                else:
                    st.info(message)
            
            with preview_cols[1]:
                st.write("Group B Preview:")
                if campaign_type == "Email":
                    st.info(f"Subject: {subject}\n\n{message}")
                else:
                    st.info(message)

            # Campaign Execution
            st.subheader("Campaign Execution")
            
            if st.button(f"Launch {campaign_type} Campaign", 
                        key=f'launch_{campaign_type}'):
                
                # Split the dataset for A/B testing
                filtered_df['Group'] = 'A'
                b_size = len(filtered_df) * (100-ab_split) // 100
                filtered_df.iloc[:b_size, filtered_df.columns.get_loc('Group')] = 'B'
                
                # Execute campaign
                with st.spinner(f"Sending {campaign_type} messages..."):
                    success_count = 0
                    fail_count = 0
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, row in filtered_df.iterrows():
                        try:
                            if campaign_type == "Email":
                                success = send_email(
                                    row['Email'],
                                    subject.format(first_name=row['First Name']),
                                    message.format(first_name=row['First Name'])
                                )
                            else:
                                phone = format_phone_number(row['Phone Number'])
                                if phone:
                                    success = send_text_message(
                                        phone,
                                        message.format(first_name=row['First Name'])
                                    )
                                else:
                                    success = False
                            
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                                
                            # Update progress
                            progress = (idx + 1) / len(filtered_df)
                            progress_bar.progress(progress)
                            status_text.text(
                                f"Processing: {idx + 1}/{len(filtered_df)} "
                                f"({success_count} successful, {fail_count} failed)"
                            )
                            
                            time.sleep(0.1)  # Simulate processing time
                            
                        except Exception as e:
                            st.error(f"Error processing row {idx}: {str(e)}")
                            fail_count += 1
                    
                    # Final summary
                    st.success(
                        f"Campaign completed: {success_count} successful, "
                        f"{fail_count} failed"
                    )

                    # Save campaign results
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{campaign_type}_campaign_{timestamp}.csv"
                    filtered_df.to_csv(filename, index=False)
                    
                    # Offer download of results
                    with open(filename, 'rb') as f:
                        st.download_button(
                            label="Download Campaign Results",
                            data=f,
                            file_name=filename,
                            mime="text/csv"
                        )

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    owner_df = get_owner_sheet_data()
    run_owner_marketing_tab(owner_df)
