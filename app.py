import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import phonenumbers
import re

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
        else:
            # Normalize 'Campaign Type' to title case and strip spaces
            df['Campaign Type'] = df['Campaign Type'].astype(str).str.strip().str.title()

        return df

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Google Sheet not found. Please check the sheet key and permissions.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        return pd.DataFrame()

def is_valid_email(email):
    """Enhanced email validation using regex."""
    regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    return isinstance(email, str) and re.fullmatch(regex, email) is not None

def is_valid_phone(phone):
    """Enhanced phone validation using phonenumbers."""
    try:
        parsed_phone = phonenumbers.parse(phone, "US")
        return phonenumbers.is_valid_number(parsed_phone)
    except phonenumbers.NumberParseException:
        return False

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
    Function to send an email using SendGrid.
    """
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
            return True
        else:
            st.error(f"Failed to send email to {recipient}: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error sending email to {recipient}: {str(e)}")
        return False

def send_text_message(phone_number, message):
    """
    Function to send a text message using Twilio.
    """
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
        return bool(msg.sid)
    except Exception as e:
        st.error(f"Error sending SMS to {phone_number}: {str(e)}")
        return False

def run_text_campaign(filtered_df, campaign_type):
    st.header(f"{campaign_type} Campaign Management - Text Message Campaign")

    # **Display Filtered Data as a Table**
    st.subheader("Filtered Owner Sheets Data")
    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
    else:
        # Calculate per-owner value
        if 'Points' in filtered_df.columns:
            filtered_df['Value ($)'] = filtered_df['Points'] * 0.20  # Adjust the multiplier as needed
        else:
            filtered_df['Value ($)'] = 0

        st.dataframe(filtered_df)

    # **Debugging Outputs**
    # Optional: Provide a checkbox to toggle debugging info
    show_debug = st.checkbox("Show Debugging Information", key=f'{campaign_type}_text_debug')
    if show_debug:
        st.write(f"### Debugging Information for {campaign_type} Text Campaign")
        st.write(f"Total records after 'Campaign Type' filter: {len(filtered_df)}")
        st.write("### Unique Campaign Types in Data:")
        st.write(filtered_df['Campaign Type'].unique())

    # Display metrics
    metrics_cols = st.columns(4)
    with metrics_cols[0]:
        st.metric("Total Owners", len(filtered_df))
    with metrics_cols[1]:
        if 'Primary FICO' in filtered_df.columns:
            mean_fico = filtered_df['Primary FICO'].mean()
            avg_fico = int(mean_fico) if pd.notna(mean_fico) else 'N/A'
        else:
            avg_fico = 'N/A'
        st.metric("Average FICO", avg_fico)
    with metrics_cols[2]:
        if 'Points' in filtered_df.columns:
            mean_points = filtered_df['Points'].mean()
            avg_points = int(mean_points) if pd.notna(mean_points) else 'N/A'
        else:
            avg_points = 'N/A'
        st.metric("Average Points", avg_points)
    with metrics_cols[3]:
        if 'Value ($)' in filtered_df.columns:
            total_value = filtered_df['Value ($)'].sum()
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
            key=f'{campaign_type}_text_split'
        )
    with col2:
        group_a_size = len(filtered_df) * ab_split // 100
        group_b_size = len(filtered_df) * (100 - ab_split) // 100
        st.metric("Group A Size", f"{group_a_size}")
        st.metric("Group B Size", f"{group_b_size}")

    # Message Templates
    st.subheader("Message Templates")

    text_templates = {
        "Welcome": "Welcome to our premium ownership family! Reply STOP to opt out.",
        "Upgrade": "Exclusive upgrade opportunity available! Reply STOP to opt out.",
        "Custom": ""
    }

    template_choice = st.selectbox(
        "Select Text Template",
        list(text_templates.keys()),
        key='text_template_text'
    )

    message = st.text_area(
        "Message Text",
        value=text_templates[template_choice],
        height=100,
        key='sms_message_text'
    )

    # Preview Section
    st.subheader("Campaign Preview")
    preview_cols = st.columns(2)
    with preview_cols[0]:
        st.write("Group A Preview:")
        st.info(message)

    with preview_cols[1]:
        st.write("Group B Preview:")
        st.info(message)

    # Campaign Execution
    st.subheader("Campaign Execution")

    if st.button(f"Launch {campaign_type} Text Campaign", key=f'launch_{campaign_type}_text'):
        if filtered_df.empty:
            st.warning("No data available for the selected filters.")
            return

        # Split the dataset for A/B testing
        campaign_df = filtered_df.sample(frac=1, random_state=42).reset_index(drop=True)  # Shuffle the DataFrame
        split_index = group_a_size
        group_a = campaign_df.iloc[:split_index].copy()
        group_b = campaign_df.iloc[split_index:].copy()

        # Combine groups with labels
        group_a['Group'] = 'A'
        group_b['Group'] = 'B'
        campaign_df = pd.concat([group_a, group_b], ignore_index=True)

        # Execute campaign
        with st.spinner(f"Sending {campaign_type} text messages..."):
            success_count = 0
            fail_count = 0

            progress_bar = st.progress(0)
            status_text = st.empty()

            total = len(campaign_df)
            for idx, row in campaign_df.iterrows():
                try:
                    phone = format_phone_number(row['Phone Number'])
                    if is_valid_phone(phone):
                        personalized_message = message.format(first_name=row['First Name'])
                        success = send_text_message(phone, personalized_message)
                    else:
                        st.warning(f"Invalid phone number for {row['First Name']}: {row['Phone Number']}")
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
                    fail_count += 1

            # Final summary
            st.success(
                f"Campaign completed: {success_count} successful, "
                f"{fail_count} failed"
            )

            # Save campaign results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"text_campaign_{timestamp}.csv"
            campaign_df.to_csv(filename, index=False)

            # Offer download of results
            with open(filename, 'rb') as f:
                st.download_button(
                    label="Download Campaign Results",
                    data=f,
                    file_name=filename,
                    mime="text/csv"
                )

def run_email_campaign(filtered_df, campaign_type):
    st.header(f"{campaign_type} Campaign Management - Email Campaign")

    # **Display Filtered Data as a Table**
    st.subheader("Filtered Owner Sheets Data")
    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
    else:
        # Calculate per-owner value
        if 'Points' in filtered_df.columns:
            filtered_df['Value ($)'] = filtered_df['Points'] * 0.20  # Adjust the multiplier as needed
        else:
            filtered_df['Value ($)'] = 0

        st.dataframe(filtered_df)

    # **Debugging Outputs**
    # Optional: Provide a checkbox to toggle debugging info
    show_debug = st.checkbox("Show Debugging Information", key=f'{campaign_type}_email_debug')
    if show_debug:
        st.write(f"### Debugging Information for {campaign_type} Email Campaign")
        st.write(f"Total records after 'Campaign Type' filter: {len(filtered_df)}")
        st.write("### Unique Campaign Types in Data:")
        st.write(filtered_df['Campaign Type'].unique())

    # Display metrics
    metrics_cols = st.columns(4)
    with metrics_cols[0]:
        st.metric("Total Owners", len(filtered_df))
    with metrics_cols[1]:
        if 'Primary FICO' in filtered_df.columns:
            mean_fico = filtered_df['Primary FICO'].mean()
            avg_fico = int(mean_fico) if pd.notna(mean_fico) else 'N/A'
        else:
            avg_fico = 'N/A'
        st.metric("Average FICO", avg_fico)
    with metrics_cols[2]:
        if 'Points' in filtered_df.columns:
            mean_points = filtered_df['Points'].mean()
            avg_points = int(mean_points) if pd.notna(mean_points) else 'N/A'
        else:
            avg_points = 'N/A'
        st.metric("Average Points", avg_points)
    with metrics_cols[3]:
        if 'Value ($)' in filtered_df.columns:
            total_value = filtered_df['Value ($)'].sum()
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
            key=f'{campaign_type}_email_split'
        )
    with col2:
        group_a_size = len(filtered_df) * ab_split // 100
        group_b_size = len(filtered_df) * (100 - ab_split) // 100
        st.metric("Group A Size", f"{group_a_size}")
        st.metric("Group B Size", f"{group_b_size}")

    # Message Templates
    st.subheader("Message Templates")

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
        key='email_template_email'
    )

    subject = st.text_input(
        "Email Subject",
        value=email_templates[template_choice]["subject"],
        key='email_subject_email'
    )

    body = st.text_area(
        "Email Body",
        value=email_templates[template_choice]["body"],
        height=200,
        key='email_body_email'
    )

    # Preview Section
    st.subheader("Campaign Preview")
    preview_cols = st.columns(2)
    with preview_cols[0]:
        st.write("Group A Preview:")
        st.info(f"Subject: {subject}\n\n{body}")

    with preview_cols[1]:
        st.write("Group B Preview:")
        st.info(f"Subject: {subject}\n\n{body}")

    # Campaign Execution
    st.subheader("Campaign Execution")

    if st.button(f"Launch {campaign_type} Email Campaign", key=f'launch_{campaign_type}_email'):
        if filtered_df.empty:
            st.warning("No data available for the selected filters.")
            return

        # Split the dataset for A/B testing
        campaign_df = filtered_df.sample(frac=1, random_state=42).reset_index(drop=True)  # Shuffle the DataFrame
        split_index = group_a_size
        group_a = campaign_df.iloc[:split_index].copy()
        group_b = campaign_df.iloc[split_index:].copy()

        # Combine groups with labels
        group_a['Group'] = 'A'
        group_b['Group'] = 'B'
        campaign_df = pd.concat([group_a, group_b], ignore_index=True)

        # Execute campaign
        with st.spinner(f"Sending {campaign_type} emails..."):
            success_count = 0
            fail_count = 0

            progress_bar = st.progress(0)
            status_text = st.empty()

            total = len(campaign_df)
            for idx, row in campaign_df.iterrows():
                try:
                    recipient_email = row['Email']
                    if is_valid_email(recipient_email):
                        personalized_subject = subject.format(first_name=row['First Name'])
                        personalized_body = body.format(first_name=row['First Name'])
                        success = send_email(recipient_email, personalized_subject, personalized_body)
                    else:
                        st.warning(f"Invalid email address for {row['First Name']}: {recipient_email}")
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
                    fail_count += 1

            # Final summary
            st.success(
                f"Campaign completed: {success_count} successful, "
                f"{fail_count} failed"
            )

            # Save campaign results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"email_campaign_{timestamp}.csv"
            campaign_df.to_csv(filename, index=False)

            # Offer download of results
            with open(filename, 'rb') as f:
                st.download_button(
                    label="Download Campaign Results",
                    data=f,
                    file_name=filename,
                    mime="text/csv"
                )

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # **Campaign Type Selection**
    campaign_tabs = st.tabs(["📱 Text Message Campaign", "📧 Email Campaign"])

    # **Text Message Campaign Tab**
    with campaign_tabs[0]:
        run_text_campaign(owner_df, "Text")

    # **Email Campaign Tab**
    with campaign_tabs[1]:
        run_email_campaign(owner_df, "Email")

def run_minimal_app():
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    st.title("Owner Marketing Dashboard")

    # Option to use sample data for testing
    use_sample = st.sidebar.checkbox("Use Sample Data", value=False)

    if use_sample:
        owner_df = pd.DataFrame({
            'First Name': ['John', 'Jane', 'Alice'],
            'Last Name': ['Doe', 'Smith', 'Johnson'],
            'Email': ['john.doe@example.com', 'jane.smith@example.com', 'alice.johnson@example.com'],
            'Phone Number': ['+1234567890', '+1987654321', '+1123456789'],
            'Primary FICO': [720, 680, None],
            'Points': [150, 200, 180],
            'Sale Date': [datetime(2023, 1, 15), datetime(2023, 3, 22), datetime(2023, 5, 10)],
            'Maturity Date': [datetime(2024, 1, 15), datetime(2024, 3, 22), datetime(2024, 5, 10)],
            'State': ['CA', 'NY', 'TX'],
            'Unit': ['A', 'B', 'C'],
            'Campaign Type': ['Email', 'Text', 'Email']
        })
    else:
        owner_df = get_owner_sheet_data()

    if not owner_df.empty:
        # **Verify 'Campaign Type' Data**
        st.sidebar.subheader("Data Verification")
        unique_campaign_types = owner_df['Campaign Type'].unique()
        st.sidebar.write("**Unique 'Campaign Type' Values:**")
        st.sidebar.write(unique_campaign_types)

        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")

if __name__ == "__main__":
    run_minimal_app()
