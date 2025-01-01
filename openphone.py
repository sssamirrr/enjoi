import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1. UPLOAD FILE
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
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # remove rows with no createdAtPT

    # Convert createdAtPT -> createdAtET
    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    # If there's an answeredAtPT column, convert similarly
    if 'answeredAtPT' in openphone_data.columns:
        openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')
        openphone_data['answeredAtET'] = (
            openphone_data['answeredAtPT']
            .dropna()
            .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert(eastern_tz)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS (DATE RANGE & AGENT)
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
        st.error("Error: Start date cannot exceed end date.")
        return

    # Filter by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # A) Agent Filter: only keep those whose email ends with "@enjoiresorts.com"
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    # Gather valid emails from your domain
    all_emails = [
        agent for agent in openphone_data['userId'].dropna().unique()
        if agent.endswith('@enjoiresorts.com')
    ]
    if not all_emails:
        st.warning("No agents found with '@enjoiresorts.com' in this data/date range.")
        return

    # Short display names
    display_names = [email.split('@')[0] for email in all_emails]  # e.g. 'm.allen'
    # Map short name -> full email
    agent_map = dict(zip(display_names, all_emails))

    # B) Let user pick short names in multiselect, default=empty
    selected_display_names = st.multiselect(
        "Select Enjoi Agents by Short Name",
        sorted(display_names),
        default=[]
    )

    # Convert selection back to full emails
    selected_full_emails = [agent_map[name] for name in selected_display_names]

    # Filter data by those agents
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_full_emails)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. BOOKING / CONVERSION
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    bookings = openphone_data[openphone_data['status'] == 'booked']
    total_bookings = len(bookings)

    call_conversion_rate = (
        len(calls[calls['status'] == 'booked']) / len(calls) * 100
        if len(calls) else 0
    )
    message_conversion_rate = (
        len(messages[messages['status'] == 'booked']) / len(messages) * 100
        if len(messages) else 0
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 6. AGENT PERFORMANCE (CALLS & BOOKINGS)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_calls = calls.groupby('userId').size().reset_index(name='total_calls')

    agent_performance = pd.merge(agent_calls, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 7. DEFINE day/hour (STRING) + day_order & hour_order
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
    # 8. OUTBOUND CALL SUCCESS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        max_duration = int(calls['duration'].max())

    min_success_duration = st.slider(
        "Min Call Duration (seconds) for Success",
        min_value=0,
        max_value=max_duration,
        value=30
    )

    outbound_calls = calls[calls['direction'] == 'outgoing']
    successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]

    success_rate = (
        len(successful_outbound_calls) / len(outbound_calls) * 100
        if len(outbound_calls) else 0
    )

    agent_success = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
    agent_outbound = outbound_calls.groupby('userId').size().reset_index(name='total_outbound_calls')

    agent_success_rate = pd.merge(agent_outbound, agent_success, on='userId', how='outer').fillna(0)
    agent_success_rate['success_rate'] = (
        agent_success_rate['successful_calls'] / agent_success_rate['total_outbound_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 9. KEY METRICS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bookings", total_bookings)
    with col2:
        st.metric("Call Conv. Rate", f"{call_conversion_rate:.2f}%")
    with col3:
        st.metric("Msg Conv. Rate", f"{message_conversion_rate:.2f}%")
    with col4:
        st.metric("Outbound Success Rate", f"{success_rate:.2f}%")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ... (Hourly Trends, Call Duration, etc. as before)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # For brevity, we won't repeat *all* chart sections. You can reuse your existing code
    # for Hourly Trends (#10), Call Duration Analysis (#11), Incoming Messages (#12), etc.
    # ensuring that each pivot + reindex includes the day/hour logic.

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap (Day & Hour)")
    if not outbound_calls.empty:
        group_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        group_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')

        group_outbound['day'] = group_outbound['day'].astype(str)
        group_outbound['hour'] = group_outbound['hour'].astype(str)
        group_success['day'] = group_success['day'].astype(str)
        group_success['hour'] = group_success['hour'].astype(str)

        merged = pd.merge(group_outbound, group_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged['success_rate'] = (merged['success_count'] / merged['outbound_count']) * 100

        # Pivot per agent
        for full_email in selected_full_emails:
            agent_df = merged[merged['userId'] == full_email]
            if agent_df.empty:
                st.write(f"No outbound calls for agent: {full_email}")
                continue

            pivot_srate = agent_df.pivot(index='day', columns='hour', values='success_rate')
            pivot_srate.index = pivot_srate.index.astype(str)
            pivot_srate.columns = pivot_srate.columns.astype(str)

            # Intersection with day/hour
            a_days = [d for d in day_order if d in pivot_srate.index]
            a_hours = [h for h in hour_order if h in pivot_srate.columns]
            pivot_srate = pivot_srate.reindex(index=a_days, columns=a_hours).fillna(0)

            # Convert full email back to short display
            short_name = [k for k,v in agent_map.items() if v == full_email]
            short_name = short_name[0] if short_name else full_email

            fig = px.imshow(
                pivot_srate,
                color_continuous_scale='Blues',
                labels=dict(x="Hour (AM/PM)", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap - {short_name}",
            )
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))
            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls for success rate heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 18. SIDE-BY-SIDE HEATMAP: SUCCESSFUL OUTBOUND CALLS + SUCCESS RATE
    #    with max 2 agents per row: facet_col_wrap=2
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Side-by-Side: Successful Calls (Count) vs. Success Rate per Agent (Max 2 Agents per Row)")

    # Only if 2+ agents are selected and data is not empty
    if len(selected_full_emails) >= 1 and not successful_outbound_calls.empty and not outbound_calls.empty:
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

        # For userId in selected_full_emails, we want the short display
        # We'll create a new column 'agent_display' that maps full email -> short name
        combined['agent_display'] = combined['userId'].apply(
            lambda full: next((k for k,v in agent_map.items() if v == full), full)
        )

        # 4) Now we do a facet with 2 columns per row
        fig = px.density_heatmap(
            combined,
            x='hour',
            y='day',
            z='value',
            facet_col='agent_display',   # columns = each agent
            facet_row='metric',          # rows = Count vs. Success Rate
            facet_col_wrap=2,           # <-- max 2 agents per row
            color_continuous_scale='Blues',
            category_orders={
                "hour": hour_order,
                "day": day_order,
                "metric": ["Count","Success Rate"], 
                "agent_display": sorted([k for k in agent_map.keys() if agent_map[k] in selected_full_emails])
            },
            title="Side-by-Side: Successful Calls vs. Success Rate (2 Agents Per Row)",
            text_auto=True
        )
        # We have one color scale across both 'Count' and 'Success Rate'.
        # If you'd like separate color scales, you'd need a more custom approach.

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Not enough agents or data to show side-by-side calls vs. success rate.")

    st.success("Enhanced Dashboard Complete!")
