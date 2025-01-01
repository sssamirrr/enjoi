import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1. FILE UPLOAD
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    openphone_data = pd.read_csv(uploaded_file)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 2. TIME ZONE CONVERSION (PT -> ET)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # remove NaT rows

    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    if 'answeredAtPT' in openphone_data.columns:
        openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')
        openphone_data['answeredAtET'] = (
            openphone_data['answeredAtPT']
            .dropna()
            .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert(eastern_tz)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS: DATE RANGE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Filters")

    min_date = openphone_data['createdAtET'].min().date()
    max_date = openphone_data['createdAtET'].max().date()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Filter data by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3B. FILTERS: AGENTS @enjoiresorts.com
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column in dataset.")
        return

    # 1) Filter to only emails ending with @enjoiresorts.com
    all_emails = [email for email in openphone_data['userId'].dropna().unique()
                  if email.endswith('@enjoiresorts.com')]
    if not all_emails:
        st.warning("No agents found with '@enjoiresorts.com' in the current dataset or date range.")
        return

    # 2) Create short names by splitting at '@'
    display_names = [email.split('@')[0] for email in all_emails]
    # 3) Map short name -> full email
    agent_map = dict(zip(display_names, all_emails))

    # 4) Let user select short names, default= empty
    selected_short_names = st.multiselect(
        "Select Agents (Enjoi Resorts Only)",
        options=sorted(display_names),
        default=[]
    )

    # 5) Convert short names back to full emails for filtering
    selected_emails = [agent_map[name] for name in selected_short_names]

    # Filter openphone_data to only those selected full emails
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_emails)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS / MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. DAY/HOUR ORDER
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hour_order = [
        "12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
        "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
        "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"
    ]

    if not calls.empty:
        calls['day'] = calls['createdAtET'].dt.strftime('%A').astype(str)
        calls['hour'] = calls['createdAtET'].dt.strftime('%I %p').astype(str)

    if not messages.empty:
        messages['day'] = messages['createdAtET'].dt.strftime('%A').astype(str)
        messages['hour'] = messages['createdAtET'].dt.strftime('%I %p').astype(str)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 6. EXAMPLE: SUCCESSFUL OUTBOUND CALLS (JUST ONE CHART HERE)
    #    We'll demonstrate your side-by-side facet with max 2 agents per row
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls vs. Success Rate (Side-by-Side, max 2 agents/row)")

    # For example, we define 'outbound_calls' and 'successful_outbound_calls'
    if not calls.empty:
        outbound_calls = calls[calls['direction'] == 'outgoing']

        # Suppose we define success by 'duration >= 30' seconds, or let user pick
        min_success_duration = 30
        successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]

        if not outbound_calls.empty and not successful_outbound_calls.empty:
            # 1) Count dataset
            df_count = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
            df_count['day'] = df_count['day'].astype(str)
            df_count['hour'] = df_count['hour'].astype(str)
            df_count['metric'] = "Count"
            df_count.rename(columns={'count': 'value'}, inplace=True)

            # 2) Success rate dataset
            df_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
            df_succ = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')
            merged_df = pd.merge(df_outbound, df_succ, on=['userId','day','hour'], how='outer').fillna(0)
            merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100
            merged_df['day'] = merged_df['day'].astype(str)
            merged_df['hour'] = merged_df['hour'].astype(str)

            df_srate = merged_df[['userId','day','hour','success_rate']].copy()
            df_srate['metric'] = "Success Rate"
            df_srate.rename(columns={'success_rate': 'value'}, inplace=True)

            # 3) Combine
            combined = pd.concat([df_count, df_srate], ignore_index=True)

            # 4) We'll create 'agent_display' so the short name is used for faceting
            def get_short_name(full_email):
                # If agent_map has an inverse item, use that
                for short_name, e in agent_map.items():
                    if e == full_email:
                        return short_name
                return full_email  # fallback

            combined['agent_display'] = combined['userId'].apply(get_short_name)

            # 5) We'll do a facet with 2 columns per row
            if len(selected_emails) > 0:
                fig = px.density_heatmap(
                    combined,
                    x='hour',
                    y='day',
                    z='value',
                    facet_col='agent_display',
                    facet_row='metric', 
                    facet_col_wrap=2,  # max 2 agents per row
                    color_continuous_scale='Blues',
                    category_orders={
                        "hour": hour_order,
                        "day": day_order,
                        "metric": ["Count","Success Rate"],
                        "agent_display": sorted([get_short_name(e) for e in selected_emails])
                    },
                    title="Side-by-Side Successful Calls vs. Success Rate (2 Agents per row)",
                    text_auto=True
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No agents selected or no data to display.")
        else:
            st.warning("No outbound calls or no successful calls in filters.")
    else:
        st.warning("No calls found in the filtered dataset.")

    st.success("Dashboard Ready!")
