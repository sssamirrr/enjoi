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
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # remove rows without valid createdAtPT

    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    # If there's an answeredAtPT column
    if 'answeredAtPT' in openphone_data.columns:
        openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')
        openphone_data['answeredAtET'] = (
            openphone_data['answeredAtPT']
            .dropna()
            .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert(eastern_tz)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS (DATE RANGE)
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
        st.error("Error: Start date must be before end date.")
        return

    # Filter data by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3B. FILTERS (AGENTS @enjoiresorts.com)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    # Filter agent emails to only those that end with @enjoiresorts.com
    all_emails = [
        email for email in openphone_data['userId'].dropna().unique()
        if email.endswith('@enjoiresorts.com')
    ]
    if not all_emails:
        st.warning("No agents found with '@enjoiresorts.com' in this date range.")
        return

    # Convert to short names by splitting on '@'
    display_names = [email.split('@')[0] for email in all_emails]
    # Map short name -> full email
    agent_map = dict(zip(display_names, all_emails))

    # Let user pick from short names
    selected_short_names = st.multiselect(
        "Select Agents (Enjoi Resorts Only)",
        options=sorted(display_names),
        default=[]
    )

    # Convert selection back to full emails
    selected_emails = [agent_map[name] for name in selected_short_names]

    # Filter openphone_data
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_emails)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. CALCULATE BOOKING & CONVERSION RATES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    bookings = openphone_data[openphone_data['status'] == 'booked']
    total_bookings = len(bookings)

    call_conversion_rate = (
        len(calls[calls['status'] == 'booked']) / len(calls) * 100
        if len(calls) > 0 else 0
    )
    message_conversion_rate = (
        len(messages[messages['status'] == 'booked']) / len(messages) * 100
        if len(messages) > 0 else 0
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 6. AGENT PERFORMANCE FOR CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_calls = calls.groupby('userId').size().reset_index(name='total_calls')

    agent_performance = pd.merge(agent_calls, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 7. DEFINE 'day' AND 'hour' (STRING) + LOGICAL day/hour ORDERS
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
    # 8. OUTBOUND CALL SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        max_duration = int(calls['duration'].max())

    min_success_duration = st.slider(
        "Minimum Call Duration (seconds) to Count as Success",
        min_value=0,
        max_value=max_duration,
        value=30
    )

    outbound_calls = calls[calls['direction'] == 'outgoing']
    successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]

    success_rate = (
        len(successful_outbound_calls) / len(outbound_calls) * 100
        if len(outbound_calls) > 0 else 0
    )

    agent_success = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
    agent_outbound = outbound_calls.groupby('userId').size().reset_index(name='total_outbound_calls')
    agent_success_rate = pd.merge(agent_outbound, agent_success, on='userId', how='outer').fillna(0)
    agent_success_rate['success_rate'] = (
        agent_success_rate['successful_calls'] / agent_success_rate['total_outbound_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 9. METRICS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bookings", total_bookings)
    with col2:
        st.metric("Call Conversion Rate", f"{call_conversion_rate:.2f}%")
    with col3:
        st.metric("Message Conversion Rate", f"{message_conversion_rate:.2f}%")
    with col4:
        st.metric("Outbound Call Success Rate", f"{success_rate:.2f}%")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 10. HOURLY TRENDS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends")
    if not calls.empty:
        # Make calls['hour'] a categorical for the bar chart order
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)

        hourly_stats = calls.groupby(['hour','direction']).size().reset_index(name='count')
        fig = px.bar(hourly_stats, x='hour', y='count', color='direction',
                     barmode='group', title='Call Volume by Hour (12 AM -> 11 PM)')
        st.plotly_chart(fig)
    else:
        st.warning("No calls found in the selected range/filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all() and not calls.empty:
        mean_duration = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_duration]

        if not long_calls.empty:
            long_calls['hour'] = pd.Categorical(long_calls['hour'], categories=hour_order, ordered=True)
            long_hourly = long_calls.groupby('hour').size().reset_index(name='count')
            fig = px.bar(long_hourly, x='hour', y='count',
                         title='Long Calls (Above Mean Duration) by Hour')
            st.plotly_chart(fig)

        # Heatmap of Average Call Duration (day vs. hour)
        dur_data = calls.groupby(['day','hour'])['duration'].mean().reset_index()
        if not dur_data.empty:
            pivot_dur = dur_data.pivot(index='day', columns='hour', values='duration')
            pivot_dur.index = pivot_dur.index.astype(str)
            pivot_dur.columns = pivot_dur.columns.astype(str)

            # Reindex day/hour intersection
            actual_days = [d for d in day_order if d in pivot_dur.index]
            actual_hours = [h for h in hour_order if h in pivot_dur.columns]
            pivot_dur = pivot_dur.reindex(index=actual_days, columns=actual_hours).fillna(0)

            fig = px.imshow(
                pivot_dur,
                title="Heatmap of Avg Call Duration by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Duration (s)")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No valid 'duration' data or no calls in filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour")
    if not messages.empty:
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)
        incoming_messages = messages[messages['direction'] == 'incoming']
        incoming_message_times = incoming_messages.groupby('hour').size().reset_index(name='count')

        fig = px.bar(
            incoming_message_times, x='hour', y='count',
            title='Incoming Messages by Hour (12 AM -> 11 PM)'
        )
        st.plotly_chart(fig)

        # Heatmap for Message Volume
        st.subheader("Message Volume Heatmap")
        msg_heat_data = messages.groupby(['day','hour']).size().reset_index(name='count')
        if not msg_heat_data.empty:
            pivot_msg = msg_heat_data.pivot(index='day', columns='hour', values='count')
            pivot_msg.index = pivot_msg.index.astype(str)
            pivot_msg.columns = pivot_msg.columns.astype(str)

            actual_days = [d for d in day_order if d in pivot_msg.index]
            actual_hours = [h for h in hour_order if h in pivot_msg.columns]
            pivot_msg = pivot_msg.reindex(index=actual_days, columns=actual_hours).fillna(0)

            fig = px.imshow(
                pivot_msg,
                title="Heatmap of Message Volume by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Volume"),
            )
            st.plotly_chart(fig)
    else:
        st.warning("No messages found in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 13. AGENT PERFORMANCE: CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Performance: Calls & Bookings")
    if not agent_performance.empty:
        fig = px.bar(
            agent_performance,
            x='userId',
            y=['total_calls','total_bookings'],
            title="Agent Performance (Calls vs. Bookings)",
            barmode='group'
        )
        st.plotly_chart(fig)

        st.dataframe(
            agent_performance.rename(columns={
                'userId': 'Agent',
                'total_calls': 'Total Calls',
                'total_bookings': 'Total Bookings',
                'booking_rate': 'Booking Rate (%)'
            })
        )
    else:
        st.warning("No agent performance data available.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 14. AGENT OUTBOUND SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Outbound Success Rate")
    if not agent_success_rate.empty:
        fig = px.bar(
            agent_success_rate,
            x='userId',
            y=['total_outbound_calls','successful_calls'],
            title="Agent Outbound Success Rate",
            barmode='group'
        )
        st.plotly_chart(fig)

        st.dataframe(
            agent_success_rate.rename(columns={
                'userId': 'Agent',
                'total_outbound_calls': 'Total Outbound Calls',
                'successful_calls': 'Successful Calls',
                'success_rate': 'Success Rate (%)'
            })
        )
    else:
        st.warning("No outbound success data available.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 15. CALL VOLUME HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Volume Heatmap")
    if not calls.empty:
        call_heatmap_data = calls.groupby(['day','hour']).size().reset_index(name='count')
        if not call_heatmap_data.empty:
            pivot_call = call_heatmap_data.pivot(index='day', columns='hour', values='count')
            pivot_call.index = pivot_call.index.astype(str)
            pivot_call.columns = pivot_call.columns.astype(str)

            actual_days = [d for d in day_order if d in pivot_call.index]
            actual_hours = [h for h in hour_order if h in pivot_call.columns]
            pivot_call = pivot_call.reindex(index=actual_days, columns=actual_hours).fillna(0)

            fig = px.imshow(
                pivot_call,
                title="Heatmap of Call Volume by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Volume"),
            )
            st.plotly_chart(fig)
    else:
        st.warning("No calls to display in the volume heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 16. SUCCESSFUL OUTBOUND CALLS HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls Heatmap")
    if not successful_outbound_calls.empty:
        so_data = successful_outbound_calls.groupby(['day','hour']).size().reset_index(name='count')
        pivot_so = so_data.pivot(index='day', columns='hour', values='count')
        pivot_so.index = pivot_so.index.astype(str)
        pivot_so.columns = pivot_so.columns.astype(str)

        actual_days = [d for d in day_order if d in pivot_so.index]
        actual_hours = [h for h in hour_order if h in pivot_so.columns]
        pivot_so = pivot_so.reindex(index=actual_days, columns=actual_hours).fillna(0)

        fig = px.imshow(
            pivot_so,
            title="Heatmap of Successful Outbound Calls by Day & Hour",
            labels=dict(x="Hour", y="Day", color="Volume"),
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig)

        # Individual Agent Comparison
        st.subheader("Compare Agents: Successful Outbound Calls Heatmap by Day & Hour")
        agent_so_df = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
        for full_email in selected_emails:
            adf = agent_so_df[agent_so_df['userId'] == full_email]
            if adf.empty:
                st.write(f"No successful outbound calls for agent: {full_email}")
                continue

            pivot_a = adf.pivot(index='day', columns='hour', values='count')
            pivot_a.index = pivot_a.index.astype(str)
            pivot_a.columns = pivot_a.columns.astype(str)

            a_days = [d for d in day_order if d in pivot_a.index]
            a_hours = [h for h in hour_order if h in pivot_a.columns]
            pivot_a = pivot_a.reindex(index=a_days, columns=a_hours).fillna(0)

            # Convert full_email -> short name
            short_name = [k for k,v in agent_map.items() if v == full_email]
            short_name = short_name[0] if short_name else full_email

            fig = px.imshow(
                pivot_a,
                color_continuous_scale='Blues',
                labels=dict(x="Hour", y="Day", color="Count"),
                title=f"Successful Outbound Calls - {short_name}"
            )
            st.plotly_chart(fig)
    else:
        st.warning("No successful outbound calls found in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap (Day & Hour)")
    if not outbound_calls.empty:
        grp_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        grp_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')

        grp_outbound['day'] = grp_outbound['day'].astype(str)
        grp_outbound['hour'] = grp_outbound['hour'].astype(str)
        grp_success['day'] = grp_success['day'].astype(str)
        grp_success['hour'] = grp_success['hour'].astype(str)

        merged_rate = pd.merge(grp_outbound, grp_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged_rate['success_rate'] = (
            merged_rate['success_count'] / merged_rate['outbound_count'] * 100
        )

        for full_email in selected_emails:
            agent_df = merged_rate[merged_rate['userId'] == full_email]
            if agent_df.empty:
                st.write(f"No outbound calls for agent: {full_email}")
                continue

            pivot_srate = agent_df.pivot(index='day', columns='hour', values='success_rate')
            pivot_srate.index = pivot_srate.index.astype(str)
            pivot_srate.columns = pivot_srate.columns.astype(str)

            a_days = [d for d in day_order if d in pivot_srate.index]
            a_hours = [h for h in hour_order if h in pivot_srate.columns]
            pivot_srate = pivot_srate.reindex(index=a_days, columns=a_hours).fillna(0)

            short_name = [k for k,v in agent_map.items() if v == full_email]
            short_name = short_name[0] if short_name else full_email

            fig = px.imshow(
                pivot_srate,
                color_continuous_scale='Blues',
                labels=dict(x="Hour", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap - {short_name}"
            )
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))
            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls for success rate heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 18. SIDE-BY-SIDE HEATMAP (MAX 2 AGENTS/ROW): SUCCESSFUL CALLS vs. SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Side-by-Side: Successful Calls vs. Success Rate (Max 2 Agents per Row)")

    if not calls.empty and not outbound_calls.empty and not successful_outbound_calls.empty:
        if len(selected_emails) > 0:
            # 1) Build 'Count' dataset
            df_count = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
            df_count['day'] = df_count['day'].astype(str)
            df_count['hour'] = df_count['hour'].astype(str)
            df_count['metric'] = "Count"
            df_count.rename(columns={'count': 'value'}, inplace=True)

            # 2) Build 'Success Rate' dataset
            df_outb = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
            df_succ = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')
            merged_df = pd.merge(df_outb, df_succ, on=['userId','day','hour'], how='outer').fillna(0)
            merged_df['success_rate'] = merged_df['success_count'] / merged_df['outbound_count'] * 100
            merged_df['day'] = merged_df['day'].astype(str)
            merged_df['hour'] = merged_df['hour'].astype(str)

            df_srate = merged_df[['userId','day','hour','success_rate']].copy()
            df_srate['metric'] = "Success Rate"
            df_srate.rename(columns={'success_rate': 'value'}, inplace=True)

            # 3) Combine
            combined = pd.concat([df_count, df_srate], ignore_index=True)

            # 4) Create 'agent_display' so the short name is used
            def get_shortname(full_email):
                for k, v in agent_map.items():
                    if v == full_email:
                        return k
                return full_email

            combined['agent_display'] = combined['userId'].apply(get_shortname)

            # 5) Use px.density_heatmap with facet_col_wrap=2
            fig = px.density_heatmap(
                combined,
                x='hour',
                y='day',
                z='value',
                facet_col='agent_display',   # columns = each agent
                facet_row='metric',          # rows = Count vs. Success Rate
                facet_col_wrap=2,           # max 2 agents per row
                color_continuous_scale='Blues',
                category_orders={
                    "hour": hour_order,
                    "day": day_order,
                    "metric": ["Count", "Success Rate"],
                    # Sort the short names to keep a nice order
                    "agent_display": sorted([get_shortname(e) for e in selected_emails])
                },
                title="Side-by-Side: Successful Calls vs. Success Rate (2 Agents per row)",
                text_auto=True
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No agents selected to show side-by-side heatmap.")
    else:
        st.warning("Not enough data (outbound calls or successful calls) to show side-by-side heatmap.")

    st.success("Enhanced Dashboard with Full Restored Functions is Ready!")
