import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import requests
import phonenumbers
import sendgrid
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
import logging

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
    Send email using SendGrid.
    """
    try:
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
    Send text message using Twilio.
    """
    try:
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

    # Campaign Type Selection
    campaign_tabs = st.tabs(["📱 Text Message Campaign", "📧 Email Campaign"])

    for idx, campaign_type in enumerate(["Text", "Email"]):
        with campaign_tabs[idx]:
            st.header(f"{campaign_type} Campaign Management")

            # Filters Section
            with st.expander("📊 Filters", expanded=True):
                col1, col2, col3 = st.columns(3)

                # Column 1 Filters
                with col1:
                    selected_states = []
                    if 'State' in owner_df.columns:
                        states = sorted(owner_df['State'].dropna().unique().tolist())
                        selected_states = st.multiselect(
                            'Select States',
                            states,
                            key=f'{campaign_type}_states'
                        )

                    selected_unit = 'All'
                    if 'Unit' in owner_df.columns:
                        units = ['All'] + sorted(owner_df['Unit'].dropna().unique().tolist())
                        selected_unit = st.selectbox(
                            'Unit Type',
                            units,
                            key=f'{campaign_type}_unit'
                        )

                # Column 2 Filters
                with col2:
                    sale_date_min = owner_df['Sale Date'].min().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    sale_date_max = owner_df['Sale Date'].max().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    date_range = st.date_input(
                        'Sale Date Range',
                        value=(sale_date_min, sale_date_max),
                        key=f'{campaign_type}_dates'
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
                                key=f'{campaign_type}_fico'
                            )
                        else:
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(300, 850),
                                key=f'{campaign_type}_fico'
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
                avg_fico = int(filtered_df['Primary FICO'].mean()) if 'Primary FICO' in filtered_df.columns else 'N/A'
                st.metric("Average FICO", avg_fico)
            with metrics_cols[2]:
                avg_points = int(filtered_df['Points'].mean()) if 'Points' in filtered_df.columns else 'N/A'
                st.metric("Average Points", avg_points)
            with metrics_cols[3]:
                total_value = filtered_df['Points'].sum() * 0.20 if 'Points' in filtered_df.columns else 0
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
                group_a_size = len(filtered_df) * ab_split // 100
                group_b_size = len(filtered_df) * (100 - ab_split) // 100
                st.metric("Group A Size", f"{group_a_size}")
                st.metric("Group B Size", f"{group_b_size}")

            # Message Templates
            st.subheader("Message Templates")

            if campaign_type == "Email":
                email_templates = {
                    "Welcome": {
                        "subject": "Welcome to Our Premium Ownership Family",
                        "body": "Dear {first_name},\n\nWelcome to our exclusive community..."
                    },
                    "Upgrade Offer": {
                        "subject": "Exclusive Upgrade Opportunity",
                        "body": "Dear {first_name},\n\nAs a valued member, we are excited to offer you..."
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
                    value=email_templates[template_choice]["subject"],
                    key='email_subject'
                )

                body = st.text_area(
                    "Email Body",
                    value=email_templates[template_choice]["body"],
                    height=200,
                    key='email_body'
                )

            else:
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
                    height=100,
                    key='sms_message'
                )

            # Preview Section
            st.subheader("Campaign Preview")
            preview_cols = st.columns(2)
            with preview_cols[0]:
                st.write("Group A Preview:")
                if campaign_type == "Email":
                    st.info(f"Subject: {subject}\n\n{body}")
                else:
                    st.info(message)

            with preview_cols[1]:
                st.write("Group B Preview:")
                if campaign_type == "Email":
                    st.info(f"Subject: {subject}\n\n{body}")
                else:
                    st.info(message)

            # Campaign Execution
            st.subheader("Campaign Execution")

            if st.button(f"Launch {campaign_type} Campaign", key=f'launch_{campaign_type}'):

                if filtered_df.empty:
                    st.warning("No data available for the selected filters.")
                    return

                # Split the dataset for A/B testing
                filtered_df = filtered_df.sample(frac=1).reset_index(drop=True)  # Shuffle the DataFrame
                split_index = group_a_size
                group_a = filtered_df.iloc[:split_index].copy()
                group_b = filtered_df.iloc[split_index:].copy()

                # Combine groups with labels
                group_a['Group'] = 'A'
                group_b['Group'] = 'B'
                campaign_df = pd.concat([group_a, group_b], ignore_index=True)

                # Execute campaign
                with st.spinner(f"Sending {campaign_type} messages..."):
                    success_count = 0
                    fail_count = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    total = len(campaign_df)
                    for idx, row in campaign_df.iterrows():
                        try:
                            if campaign_type == "Email":
                                recipient_email = row['Email']  # Directly use the email without validation
                                if pd.notna(recipient_email) and '@' in recipient_email:
                                    personalized_subject = subject.format(first_name=row['First Name'])
                                    personalized_body = body.format(first_name=row['First Name'])
                                    success = send_email(recipient_email, personalized_subject, personalized_body)
                                else:
                                    success = False
                            else:
                                phone = format_phone_number(row['Phone Number'])
                                if phone:
                                    personalized_message = message.format(first_name=row['First Name'])
                                    success = send_text_message(phone, personalized_message)
                                else:
                                    success = False

                            if success:
                                success_count += 1
                            else:
                                fail_count += 1

                            # Update progress
                            progress = (idx + 1) / total
                            progress_bar.progress(progress)
                            status_text.text(
                                f"Processing: {idx + 1}/{total} "
                                f"({success_count} successful, {fail_count} failed)"
                            )

                            # Optional: Remove sleep in production
                            time.sleep(0.05)

                        except Exception as e:
                            st.error(f"Error processing row {idx}: {str(e)}")
                            logging.error(f"Error processing row {idx}: {str(e)}")
                            fail_count += 1

                    # Final summary
                    st.success(
                        f"Campaign completed: {success_count} successful, "
                        f"{fail_count} failed"
                    )

                    # Save campaign results
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{campaign_type}_campaign_{timestamp}.csv"
                    campaign_df.to_csv(filename, index=False)

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
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")
