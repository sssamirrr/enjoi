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
        logger.info(f"Demo Mode: Pretended to send email to {recipient} with subject '{subject}'.")
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
                st.secrets["twilio_account_sid"],
                st.secrets["twilio_auth_token"]
            )
            msg = client.messages.create(
                body=message,
                from_=st.secrets["twilio_phone_number"],
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
    campaign_tabs = st.tabs(["�� Text Message Campaign", "�� Email Campaign"])

    # Now, loop over the campaign tabs
    for idx, campaign_type in enumerate(["Text", "Email"]):
        with campaign_tabs[idx]:
            st.header(f"{campaign_type} Campaign Management")

            # Apply filters inside the tab
            with st.expander("�� Filters", expanded=True):
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

            # Display Filtered Data as a Table
            st.subheader("Filtered Owner Sheets Data")
            if campaign_filtered_df.empty:
                st.warning("No data matches the selected filters.")
            else:
                st.dataframe(campaign_filtered_df)

            # **Add Map of Owners' Locations**
                        # **Add Map of Owners' Locations**
            st.subheader("Map of Owner Locations")
 
            # Create a toggle for the map
            show_map = st.expander("Show/Hide Owners Map", expanded=False)

            def clean_zip_code(zip_code):
                """Clean and validate ZIP code"""
                if pd.isna(zip_code):
                    return None
                zip_str = str(zip_code)
                zip_digits = ''.join(filter(str.isdigit, zip_str))
                return zip_digits[:5] if len(zip_digits) >= 5 else None

            if 'Zip Code' in campaign_filtered_df.columns:
                # Clean and prepare ZIP codes
                campaign_filtered_df['Zip Code'] = campaign_filtered_df['Zip Code'].apply(clean_zip_code)
                campaign_filtered_df = campaign_filtered_df.dropna(subset=['Zip Code'])

                if not campaign_filtered_df.empty:
                    try:
                        # Geocode ZIP codes
                        nomi = pgeocode.Nominatim('us')
                        geocode_df = nomi.query_postal_code(campaign_filtered_df['Zip Code'].tolist())
                        
                        # Create map data
                        map_data = pd.DataFrame({
                            'lat': geocode_df['latitude'],
                            'lon': geocode_df['longitude']
                        }).dropna()

                        if not map_data.empty:
                            st.map(map_data)
                            st.info(f"Showing {len(map_data)} locations on the map")
                        else:
                            st.info("No valid coordinates available for mapping")
                    except Exception as e:
                        st.error(f"Error creating map: {str(e)}")
                else:
                    st.info("No valid ZIP codes available for mapping")
            else:
                st.info("ZIP Code data is not available to display the map")

            # Display metrics
            metrics_cols = st.columns(4)
            with metrics_cols[0]:
                st.metric("Total Owners", len(campaign_filtered_df))
            with metrics_cols[1]:
                if 'Primary FICO' in campaign_filtered_df.columns:
                    mean_fico = campaign_filtered_df['Primary FICO'].mean()
                    if pd.notna(mean_fico):
                        avg_fico = int(mean_fico)
                    else:
                        avg_fico = 'N/A'
                else:
                    avg_fico = 'N/A'
                st.metric("Average FICO", avg_fico)
            with metrics_cols[2]:
                if 'Points' in campaign_filtered_df.columns:
                    mean_points = campaign_filtered_df['Points'].mean()
                    if pd.notna(mean_points):
                        avg_points = int(mean_points)
                    else:
                        avg_points = 'N/A'
                else:
                    avg_points = 'N/A'
                st.metric("Average Points", avg_points)
            with metrics_cols[3]:
                if 'Points' in campaign_filtered_df.columns:
                    total_points = campaign_filtered_df['Points'].sum()
                    if pd.notna(total_points):
                        total_value = total_points * 0.20  # Example value calculation
                    else:
                        total_value = 0
                else:
                    total_value = 0
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
                group_a_size = len(campaign_filtered_df) * ab_split // 100
                group_b_size = len(campaign_filtered_df) * (100 - ab_split) // 100
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
                    key=f'email_template_{campaign_type}'
                )

                subject = st.text_input(
                    "Email Subject",
                    value=email_templates[template_choice]["subject"],
                    key=f'email_subject_{campaign_type}'
                )

                body = st.text_area(
                    "Email Body",
                    value=email_templates[template_choice]["body"],
                    height=200,
                    key=f'email_body_{campaign_type}'
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
                    key=f'text_template_{campaign_type}'
                )

                message = st.text_area(
                    "Message Text",
                    value=text_templates[template_choice],
                    height=100,
                    key=f'sms_message_{campaign_type}'
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
                if campaign_filtered_df.empty:
                    st.warning("No data available for the selected filters.")
                    return

                # Split the dataset for A/B testing
                campaign_filtered_df = campaign_filtered_df.sample(frac=1).reset_index(drop=True)  # Shuffle the DataFrame
                split_index = group_a_size
                group_a = campaign_filtered_df.iloc[:split_index].copy()
                group_b = campaign_filtered_df.iloc[split_index:].copy()

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
                                recipient_email = row['Email']
                                if pd.notna(recipient_email) and '@' in recipient_email and '.' in recipient_email.split('@')[-1]:
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
                            logger.error(f"Error processing row {idx}: {str(e)}")
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

def run_minimal_app():
    st.title("Owner Marketing Dashboard")
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
