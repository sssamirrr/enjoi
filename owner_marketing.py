import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import requests
import phonenumbers
import logging

# Define a global flag for demo mode
DEMO_MODE = True  # Set to False to enable live functionality

# Setup logging
logging.basicConfig(
    filename='campaign.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Cache data fetching
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
            logging.warning("Fetched data from Google Sheet is empty.")

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
        logging.error("Google Sheet not found. Check the sheet key and permissions.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        logging.error(f"Google Sheet Access Error: {str(e)}")
        return pd.DataFrame()

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    try:
        parsed_phone = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None

def send_email(recipient, subject, body):
    """
    Mock function to simulate sending an email.
    """
    if DEMO_MODE:
        logging.info(f"Demo Mode: Pretended to send email to {recipient} with subject '{subject}'.")
        return True
    else:
        # Live email sending logic using SendGrid
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            sg = sendgrid.SendGridAPIClient(api_key=st.secrets["sendgrid_api_key"])
            email = Mail(
                from_email=st.secrets["sendgrid_from_email"],
                to_emails=recipient,
                subject=subject,
                plain_text_content=body
            )
            response = sg.send(email)
            if response.status_code in [200, 202]:
                logging.info(f"Email sent to {recipient}")
                return True
            else:
                logging.error(f"Failed to send email to {recipient}: {response.status_code}")
                return False
        except Exception as e:
            st.error(f"Error sending email to {recipient}: {str(e)}")
            logging.error(f"SendGrid Error for {recipient}: {str(e)}")
            return False

def send_text_message(phone_number, message):
    """
    Mock function to simulate sending a text message.
    """
    if DEMO_MODE:
        logging.info(f"Demo Mode: Pretended to send SMS to {phone_number} with message '{message}'.")
        return True
    else:
        # Live SMS sending logic using Twilio
        try:
            from twilio.rest import Client

            client = Client(
                st.secrets["twilio_account_sid"],
                st.secrets["twilio_auth_token"]
            )
            msg = client.messages.create(
                body=message,
                from_=st.secrets["twilio_phone_number"],
                to=phone_number
            )
            if msg.sid:
                logging.info(f"SMS sent to {phone_number}")
                return True
            else:
                logging.error(f"Failed to send SMS to {phone_number}")
                return False
        except Exception as e:
            st.error(f"Error sending SMS to {phone_number}: {str(e)}")
            logging.error(f"Twilio Error for {phone_number}: {str(e)}")
            return False

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Display Demo Mode Notification
    if DEMO_MODE:
        st.warning("**Demo Mode Enabled:** No real emails or SMS messages will be sent.")
    else:
        st.success("**Live Mode Enabled:** Emails and SMS messages will be sent as configured.")

    # **Display the Owner Sheets Table**
    st.subheader("Owner Sheets Data")
    st.dataframe(owner_df)  # Ensure this line is present to display the table

    # Rest of your existing code...
    # For example, filters, metrics, campaign setup, etc.

    # Example: Display metrics
    metrics_cols = st.columns(4)
    with metrics_cols[0]:
        st.metric("Total Owners", len(owner_df))
    with metrics_cols[1]:
        if 'Primary FICO' in owner_df.columns:
            mean_fico = owner_df['Primary FICO'].mean()
            if pd.notna(mean_fico):
                avg_fico = int(mean_fico)
            else:
                avg_fico = 'N/A'
        else:
            avg_fico = 'N/A'
        st.metric("Average FICO", avg_fico)
    with metrics_cols[2]:
        if 'Points' in owner_df.columns:
            mean_points = owner_df['Points'].mean()
            if pd.notna(mean_points):
                avg_points = int(mean_points)
            else:
                avg_points = 'N/A'
        else:
            avg_points = 'N/A'
        st.metric("Average Points", avg_points)
    with metrics_cols[3]:
        if 'Points' in owner_df.columns:
            total_points = owner_df['Points'].sum()
            if pd.notna(total_points):
                total_value = total_points * 0.20  # Example value calculation
            else:
                total_value = 0
        else:
            total_value = 0
        st.metric("Total Value", f"${total_value:,.2f}")

    # Continue with the rest of your campaign setup and execution logic
    # ...

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")
