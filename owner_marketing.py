# owner_marketing.py
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import phonenumbers
import logging
from logging.handlers import RotatingFileHandler
import pgeocode  # For geocoding ZIP codes to latitude and longitude
import communication  # Import the communication module
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode

# Define a global flag for demo mode
DEMO_MODE = True  # Set to False to enable live functionality

# Setup logging with rotation to manage log file sizes
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('campaign.log', maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Cache data fetching to improve performance
@st.cache_data(ttl=600)
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        client = gspread.authorize(credentials)
        sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
        sheet = client.open_by_key(sheet_key)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.warning("The Google Sheet is empty. Please ensure it contains data.")
            logger.warning("Fetched data from Google Sheet is empty.")

        # Data Cleaning
        for date_col in ['Sale Date', 'Maturity Date']:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        for num_col in ['Points', 'Primary FICO']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce')

        if 'Phone Number' in df.columns:
            df['Phone Number'] = df['Phone Number'].astype(str)

        if 'Campaign Type' not in df.columns:
            df['Campaign Type'] = 'Text'  # Default campaign type

        return df

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Google Sheet not found. Please check the sheet key and permissions.")
        logger.error("Google Sheet not found. Check the sheet key and permissions.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        logger.error(f"Google Sheet Access Error: {str(e)}")
        return pd.DataFrame()

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    return communication.format_phone_number_e164(phone)

def clean_zip_code(zip_code):
    """Clean and validate ZIP code"""
    if pd.isna(zip_code):
        return None
    zip_str = str(zip_code)
    zip_digits = ''.join(filter(str.isdigit, zip_str))
    return zip_digits[:5] if len(zip_digits) >= 5 else None

def send_email(recipient, subject, body):
    """
    Mock function to simulate sending an email.
    """
    if DEMO_MODE:
        logger.info(f"Demo Mode: Pretended to send email to {recipient} with subject '{subject}'.")
        return True
    else:
        # Live email sending logic using SendGrid
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            sg = sendgrid.SendGridAPIClient(api_key=st.secrets["sendgrid"]["api_key"])
            email = Mail(
                from_email=st.secrets["sendgrid"]["from_email"],
                to_emails=recipient,
                subject=subject,
                plain_text_content=body
            )
            response = sg.send(email)
            if response.status_code in [200, 202]:
                logger.info(f"Email sent to {recipient}")
                return True
            else:
                logger.error(f"Failed to send email to {recipient}: {response.status_code}")
                return False
        except Exception as e:
            st.error(f"Error sending email to {recipient}: {str(e)}")
            logger.error(f"SendGrid Error for {recipient}: {str(e)}")
            return False

def send_text_message(phone_number, message):
    """
    Mock function to simulate sending a text message.
    """
    if DEMO_MODE:
        logger.info(f"Demo Mode: Pretended to send SMS to {phone_number} with message '{message}'.")
        return True
    else:
        # Live SMS sending logic using Twilio
        try:
            from twilio.rest import Client

            client = Client(
                st.secrets["twilio"]["account_sid"],
                st.secrets["twilio"]["auth_token"]
            )
            msg = client.messages.create(
                body=message,
                from_=st.secrets["twilio"]["phone_number"],
                to=phone_number
            )
            if msg.sid:
                logger.info(f"SMS sent to {phone_number}")
                return True
            else:
                logger.error(f"Failed to send SMS to {phone_number}")
                return False
        except Exception as e:
            st.error(f"Error sending SMS to {phone_number}: {str(e)}")
            logger.error(f"Twilio Error for {phone_number}: {str(e)}")
            return False

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Display Demo Mode Notification
    if DEMO_MODE:
        st.warning("**Demo Mode Enabled:** No real emails or SMS messages will be sent.")
    else:
        st.success("**Live Mode Enabled:** Emails and SMS messages will be sent as configured.")

    # Campaign Type Selection
    campaign_tabs = st.tabs(["📱 Text Message Campaign", "✉️ Email Campaign"])

    # Now, loop over the campaign tabs
    for idx, campaign_type in enumerate(["Text", "Email"]):
        with campaign_tabs[idx]:
            st.header(f"{campaign_type} Campaign Management")

            # Apply filters inside the tab
            with st.expander("⚙️ Filter Options", expanded=True):
                col1, col2, col3 = st.columns(3)

                # Column 1 Filters
                with col1:
                    selected_states = []
                    if 'State' in owner_df.columns:
                        states = sorted(owner_df['State'].dropna().unique().tolist())
                        selected_states = st.multiselect(
                            'Select States',
                            states,
                            key=f'states_{campaign_type}'
                        )

                    selected_unit = 'All'
                    if 'Unit' in owner_df.columns:
                        units = ['All'] + sorted(owner_df['Unit'].dropna().unique().tolist())
                        selected_unit = st.selectbox(
                            'Unit Type',
                            units,
                            key=f'unit_{campaign_type}'
                        )

                # Column 2 Filters
                with col2:
                    sale_date_min = owner_df['Sale Date'].min().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    sale_date_max = owner_df['Sale Date'].max().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    date_range = st.date_input(
                        'Sale Date Range',
                        value=(sale_date_min, sale_date_max),
                        key=f'dates_{campaign_type}'
                    )

                # Column 3 Filters (FICO)
                with col3:
                    fico_range = (300, 850)
                    if 'Primary FICO' in owner_df.columns:
                        valid_fico = owner_df['Primary FICO'].dropna()
                        if not valid_fico.empty:
                            min_fico = max(300, int(valid_fico.min()))
                            max_fico = min(850, int(valid_fico.max()))
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(min_fico, max_fico),
                                key=f'fico_{campaign_type}'
                            )
                        else:
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(300, 850),
                                key=f'fico_{campaign_type}'
                            )

            # Apply filters to the data
            campaign_filtered_df = owner_df.copy()

            if selected_states:
                campaign_filtered_df = campaign_filtered_df[campaign_filtered_df['State'].isin(selected_states)]

            if selected_unit != 'All':
                campaign_filtered_df = campaign_filtered_df[campaign_filtered_df['Unit'] == selected_unit]

            if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
                campaign_filtered_df = campaign_filtered_df[
                    (campaign_filtered_df['Sale Date'].dt.date >= date_range[0]) &
                    (campaign_filtered_df['Sale Date'].dt.date <= date_range[1])
                ]

            if 'Primary FICO' in campaign_filtered_df.columns:
                campaign_filtered_df = campaign_filtered_df[
                    (campaign_filtered_df['Primary FICO'] >= fico_range[0]) &
                    (campaign_filtered_df['Primary FICO'] <= fico_range[1])
                ]

            # Remove duplicate rows based on 'Phone Number' and reset index
            display_df = campaign_filtered_df.drop_duplicates(subset=['Phone Number']).reset_index(drop=True)

            # Optional: Verify that 'Phone Number' is unique
            if display_df['Phone Number'].duplicated().any():
                st.error("Duplicate Phone Numbers found in the data. Please ensure each owner has a unique phone number.")
                st.stop()

            # Add a checkbox for each row to select owners using AgGrid
            st.subheader("Select Owners to Fetch Communication Status")

            if display_df.empty:
                st.warning("No data matches the selected filters.")
            else:
                # Configure AgGrid options with a checkbox selection
                gb = GridOptionsBuilder.from_dataframe(display_df)
                gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren=True, groupSelectsFiltered=True)
                gb.configure_grid_options(domLayout='normal')
                grid_options = gb.build()

                grid_response = AgGrid(
                    display_df,
                    gridOptions=grid_options,
                    enable_enterprise_modules=False,
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    height=400,
                    width='100%',
                    allow_unsafe_jscode=True  # Set to True to allow checkbox integration
                )

                selected_rows_df = pd.DataFrame(grid_response['selected_rows'])
                selected_indices = selected_rows_df.index.tolist()

                # Add "Fetch Communication Status" button
                fetch_button = st.button("Fetch Communication Status", key=f'fetch_comm_{campaign_type}')

                if fetch_button:
                    if selected_rows_df.empty:
                        st.warning("No owners selected for fetching communication status.")
                    else:
                        selected_owners = selected_rows_df
