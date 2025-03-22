import streamlit as st
import pandas as pd
import numpy as np
import pytz
import plotly.express as px
from datetime import datetime

###############################################################################
# Helper: Convert numeric "duration" (seconds) into "Xm YYs"
###############################################################################
def format_duration_seconds(sec):
    """
    Convert a duration in seconds to a string like "3m 05s".
    If sec is NaN or None, returns empty string.
    """
    if pd.isnull(sec):
        return ""
    total_sec = int(sec)
    minutes = total_sec // 60
    seconds = total_sec % 60
    return f"{minutes}m {seconds:02d}s"


###############################################################################
# Helper: Display All Messages + Call Transcripts in one chronological table
###############################################################################
def display_all_events_in_one_table(openphone_data):
    """
    Combine calls & messages in one chronological table, with
    timestamps in GMT-4, direction, type, from/to, content (text or transcript).
    """
    # We'll copy the data to avoid changing the original
    df = openphone_data.copy()

    # For uniform content:
    #   - If it's a call row, use df['transcript'] as content
    #   - If it's a message row, use df['text'] (or 'body') as content
    # Create a new column called "content" that merges these.
    df["content"] = np.where(
        df["type"] == "call",
        df.get("transcript", ""),   # fallback "" if transcript col doesn't exist
        df.get("text", "")          # fallback "" if text col doesn't exist
    )

    # We'll create a "DisplayTime" column that shows the GMT-4 timestamp as a string
    # If you prefer a different format, change strftime below.
    df["DisplayTime"] = df["createdAtGMT4"].dt.strftime("%Y-%m-%d %I:%M:%S %p")

    # Sort by the actual datetime so it's strictly chronological
    df.sort_values(by="createdAtGMT4", inplace=True)

    # Prepare subset of columns for display in the table
    # Adjust to match columns present in your dataset
    columns_to_show = [
        "DisplayTime",  # the formatted date/time in GMT-4
        "type",         # call or message
        "direction",    # incoming or outgoing
        "from",         # phone number from
        "to",           # phone number to
        "content",      # text or transcript
    ]
    # Filter to only columns that actually exist in df
    columns_to_show = [c for c in columns_to_show if c in df.columns]

    st.subheader("All Messages + Call Transcripts (GMT‑4)")
    st.dataframe(df[columns_to_show])

###############################################################################
# 20) Text Success Rate Heatmap (from previous code, minor adjustments)
###############################################################################
def run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map=None):
    """
    Creates a day-hour heatmap of text success rate (the fraction of first
    outbound texts that receive any inbound reply within 24 hours).
    """

    # ... same as before, except it uses 'createdAtGMT4' instead of 'createdAtET'
    # 1) Make a copy
    messages = messages.copy()

    # 2) Add day/hour from 'createdAtGMT4'
    messages['day'] = messages['createdAtGMT4'].dt.strftime('%A')
    messages['hour'] = messages['createdAtGMT4'].dt.strftime('%I %p')

    # Separate outgoing vs incoming
    msgs_out = messages[messages['direction'] == 'outgoing'].copy()
    msgs_in  = messages[messages['direction'] == 'incoming'].copy()

    # Sort so we can find "first" outbound per day
    msgs_out.sort_values(by=['userId','phoneNumber','day','createdAtGMT4'], inplace=True)

    # Mark only the FIRST outbound text per (userId, phoneNumber, day)
    msgs_out['is_first_message'] = (
        msgs_out.groupby(['userId','phoneNumber','day'])['createdAtGMT4']
        .rank(method='first')
        .eq(1)
        .astype(int)
    )

    # 24-hr window
    df_first = msgs_out[msgs_out['is_first_message'] == 1].copy()
    df_first['window_end'] = df_first['createdAtGMT4'] + pd.Timedelta(hours=24)

    # Merge w/ inbound msgs to see if there's a reply
    df_first = df_first.reset_index(drop=False).rename(columns={'index':'orig_index'})
    merged = df_first.merge(
        msgs_in[['phoneNumber','createdAtGMT4','direction']],
        on='phoneNumber', how='left', suffixes=('_out','_in')
    )

    cond = (
        (merged['createdAtGMT4_in'] >= merged['createdAtGMT4_out']) &
        (merged['createdAtGMT4_in'] <= merged['window_end'])
    )
    merged['reply_success'] = np.where(cond, 1, 0)

    # If ANY inbound matched => success_flag=1
    success_df = merged.groupby('orig_index')['reply_success'].max().reset_index(name='success_flag')
    df_first = df_first.merge(success_df, on='orig_index', how='left')

    # Summarize
    df_first['day']  = df_first['day'].astype(str)
    df_first['hour'] = df_first['hour'].astype(str)

    group_text = df_first.groupby(['userId','day','hour']).agg(
        first_messages=('is_first_message','sum'),
        successful=('success_flag','sum')
    ).reset_index()
    group_text['success_rate'] = (
        group_text['successful'] / group_text['first_messages'] * 100
    ).fillna(0)

    # If no agent_map, default
    if agent_map is None:
        agent_map = {}

    st.subheader("20) Agent Text Success Rate Heatmap by Day & Hour")

    if group_text.empty:
        st.warning("No text messages or no 'first messages' to display (#20).")
        return

    all_agents = group_text['userId'].unique()
    for agent_id in all_agents:
        agent_df = group_text[group_text['userId'] == agent_id].copy()
        if agent_df.empty:
            continue

        # Pivot
        pivot_rate  = agent_df.pivot(index='day', columns='hour', values='success_rate').fillna(0)
        pivot_first = agent_df.pivot(index='day', columns='hour', values='first_messages').fillna(0)
        pivot_succ  = agent_df.pivot(index='day', columns='hour', values='successful').fillna(0)

        # Reindex
        pivot_rate  = pivot_rate.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_first = pivot_first.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_succ  = pivot_succ.reindex(index=day_order, columns=hour_order, fill_value=0)

        agent_title = f"{agent_map.get(agent_id, agent_id)} ({agent_id})"

        fig = px.imshow(
            pivot_rate,
            color_continuous_scale='Blues',
            range_color=[0, 100],
            labels=dict(x="Hour", y="Day", color="Rate (%)"),
            title=f"Agent: {agent_title} - Text Success Rate"
        )

        hover_text = []
        for d in pivot_rate.index:
            row_text = []
            for h in pivot_rate.columns:
                r_val   = pivot_rate.loc[d, h]
                f_count = pivot_first.loc[d, h]
                s_count = pivot_succ.loc[d, h]
                txt = (f"Day: {d}<br>Hour: {h}<br>"
                       f"Success Rate: {r_val:.1f}%<br>"
                       f"First Msgs: {int(f_count)}<br>"
                       f"Successful: {int(s_count)}")
                row_text.append(txt)
            hover_text.append(row_text)

        fig.update_traces(
            customdata=hover_text,
            hovertemplate="%{customdata}<extra></extra>"
        )
        fig.update_xaxes(side="top")
        fig.update_layout(height=400, margin=dict(l=50, r=50, t=50, b=50))

        st.plotly_chart(fig, use_container_width=True)

    # Overall summary table
    sum_agent = group_text.groupby('userId').agg(
        total_first=('first_messages','sum'),
        total_success=('successful','sum')
    ).reset_index()
    sum_agent['success_rate'] = (
        sum_agent['total_success'] / sum_agent['total_first'] * 100
    ).round(1).fillna(0)
    sum_agent['Agent'] = sum_agent['userId'].map(agent_map)

    st.subheader("Texting Summary by Agent (#20)")
    st.dataframe(sum_agent[['Agent', 'userId', 'total_first', 'total_success', 'success_rate']])


###############################################################################
# 22) Compare Call Durations: Preceded by Text
###############################################################################
def run_call_duration_preceded_by_text(messages, calls, default_time_window=8):
    """
    Compare average outbound call duration where it WAS preceded by
    an outbound text (within X hours) vs. where it was NOT preceded.
    """

    st.subheader("22) Compare Call Durations (Preceding Text Logic)")

    if messages.empty or calls.empty:
        st.warning("No messages or calls to analyze for #22.")
        return

    time_window_hours = st.slider(
        "Time Window (hours) for a Preceding Outbound Text (#22)",
        min_value=1, max_value=72, value=default_time_window, step=1
    )

    if 'duration' not in calls.columns:
        st.warning("No 'duration' column found in calls (#22).")
        return

    # Keep only outbound calls
    calls_out = calls[
        (calls['direction'] == 'outgoing') &
        (calls['duration'] >= 0)
    ].copy()
    if calls_out.empty:
        st.warning("No outbound calls left (#22).")
        return

    calls_out['call_time'] = pd.to_datetime(calls_out['createdAtGMT4'], errors='coerce')

    # All outgoing texts
    msgs_out = messages[
        (messages['direction'] == 'outgoing') &
        (messages['type'] == 'message')
    ].copy()
    msgs_out['text_time'] = pd.to_datetime(msgs_out['createdAtGMT4'], errors='coerce')

    msgs_out.sort_values(by=['userId','phoneNumber','text_time'], inplace=True)
    calls_out.sort_values(by=['userId','phoneNumber','call_time'], inplace=True)

    # Preceded => text in [call_time - X, call_time)
    calls_out['min_text_time'] = calls_out['call_time'] - pd.Timedelta(hours=time_window_hours)

    merged = calls_out.merge(
        msgs_out[['userId','phoneNumber','text_time']],
        on=['userId','phoneNumber'],
        how='left'
    )

    cond = (
        (merged['text_time'] >= merged['min_text_time']) &
        (merged['text_time'] < merged['call_time'])
    )
    merged['text_preceded'] = np.where(cond, 1, 0)

    merged = merged.reset_index(drop=False).rename(columns={'index':'call_index'})
    preceded_df = merged.groupby('call_index')['text_preceded'].max().reset_index(name='call_preceded_flag')

    calls_out = calls_out.reset_index(drop=False).rename(columns={'index':'orig_call_idx'})
    calls_out = calls_out.merge(preceded_df, left_on='orig_call_idx', right_on='call_index', how='left')
    calls_out['call_preceded_flag'] = calls_out['call_preceded_flag'].fillna(0).astype(int)

    # Overall comparison
    comp_df = calls_out.groupby('call_preceded_flag')['duration'].mean().reset_index()
    comp_df['call_preceded_flag'] = comp_df['call_preceded_flag'].map({
        0: 'No preceding text',
        1: 'Preceded by text'
    })
    # Format for display
    comp_df['avg_duration_str'] = comp_df['duration'].apply(format_duration_seconds)

    st.markdown("#### Overall: Combined (All Selected Agents)")
    fig = px.bar(
        comp_df,
        x='call_preceded_flag',
        y='duration',
        color='call_preceded_flag',
        labels=dict(call_preceded_flag="Preceding Text?", duration="Avg Duration (sec)"),
        title="Avg Call Duration: w/o vs w/ Preceding Text (#22)",
        text='avg_duration_str'
    )
    fig.update_layout(showlegend=False)
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

    st.table(comp_df[['call_preceded_flag','avg_duration_str']].rename(columns={
        'call_preceded_flag': 'Preceding Text?',
        'avg_duration_str': 'Avg Duration'
    }))

    # Per-agent
    st.markdown("#### Per-Agent Comparison (#22)")
    agent_df = calls_out.groupby(['userId','call_preceded_flag'])['duration'].mean().reset_index()
    agent_df['call_preceded_flag'] = agent_df['call_preceded_flag'].map({
        0: 'No preceding text',
        1: 'Preceded by text'
    })
    agent_df.rename(columns={'duration': 'avg_duration_sec'}, inplace=True)
    agent_df['avg_duration_str'] = agent_df['avg_duration_sec'].apply(format_duration_seconds)

    fig_per_agent = px.bar(
        agent_df,
        x='avg_duration_sec',
        y='userId',
        color='call_preceded_flag',
        orientation='h',
        barmode='group',
        labels=dict(
            userId="Agent (userId)",
            avg_duration_sec="Avg Duration (sec)",
            call_preceded_flag="Preceding Text?"
        ),
        title="Call Duration by Agent: w/o vs. w/ Preceding Text (#22)",
        text='avg_duration_str'
    )
    fig_per_agent.update_layout(legend_title_text="Preceding Text?")
    fig_per_agent.update_traces(textposition='outside')
    st.plotly_chart(fig_per_agent, use_container_width=True)

    st.dataframe(agent_df.rename(columns={
        'userId': 'Agent',
        'call_preceded_flag': 'Preceding Text?',
        'avg_duration_str': 'Avg Duration'
    }))


###############################################################################
# Main Streamlit function
###############################################################################
def run_openphone_tab():
    st.header("OpenPhone Operations Dashboard (GMT‑4, Full)")

    ############################################################################
    # 1) Upload CSV
    ############################################################################
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the CSV to proceed.")
        return

    openphone_data = pd.read_csv(uploaded_file)

    ############################################################################
    # 2) Convert 'createdAtPT' (or whichever you have) -> GMT-4
    ############################################################################
    # Adjust as needed if your column is named differently.
    # If your data is truly in Pacific Time, do:
    #    .tz_localize("America/Los_Angeles") and then .tz_convert(gmt_minus_4)
    # If your data is in UTC, localize to "UTC" first, etc.

    gmt_minus_4 = pytz.timezone("Etc/GMT+4")  # generic offset
    pacific_tz = pytz.timezone("America/Los_Angeles")

    # parse the 'createdAtPT' as datetime
    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])

    # localize to Pacific, then convert to GMT-4
    openphone_data['createdAtGMT4'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(gmt_minus_4)
    )

    # If you have 'answeredAtPT', do similarly for answeredAtGMT4 if desired
    # ...

    ############################################################################
    # 3) Basic date filters
    ############################################################################
    st.subheader("Filters")

    # get min/max from 'createdAtGMT4'
    min_date = openphone_data['createdAtGMT4'].min().date()
    max_date = openphone_data['createdAtGMT4'].max().date()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Start date cannot exceed end date.")
        return

    # Filter data by date
    openphone_data = openphone_data[
        (openphone_data['createdAtGMT4'].dt.date >= start_date) &
        (openphone_data['createdAtGMT4'].dt.date <= end_date)
    ]
    if openphone_data.empty:
        st.warning("No rows found after date filtering.")
        return

    ############################################################################
    # 4) Agent filter
    ############################################################################
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found. Please check your CSV.")
        return

    # Example: only keep userIds that end with "@enjoiresorts.com"
    all_agents = sorted([
        a for a in openphone_data['userId'].dropna().unique()
        if a.endswith("@enjoiresorts.com")
    ])
    def short_agent_name(full_email):
        return full_email.replace("@enjoiresorts.com", "")

    agent_map = {agent: short_agent_name(agent) for agent in all_agents}
    agent_choices = list(agent_map.values())

    selected_short_names = st.multiselect(
        "Select Agents",
        agent_choices,
        default=agent_choices  # or empty list
    )
    selected_agents = [
        full_email
        for full_email, short_name in agent_map.items()
        if short_name in selected_short_names
    ]

    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]
    if openphone_data.empty:
        st.warning("No rows remain after agent filter.")
        return

    ############################################################################
    # 5) Identify calls vs messages
    ############################################################################
    calls = openphone_data[openphone_data['type'] == 'call'].copy()
    messages = openphone_data[openphone_data['type'] == 'message'].copy()

    ############################################################################
    # 6) Display “All Messages + Call Transcripts” in one table
    ############################################################################
    display_all_events_in_one_table(openphone_data)

    ############################################################################
    # 7) Additional analytics (booking conversion, call duration, etc.)
    ############################################################################
    # Example: total bookings
    if 'status' in openphone_data.columns:
        bookings = openphone_data[openphone_data['status'] == 'booked']
        total_bookings = len(bookings)
    else:
        bookings = pd.DataFrame()
        total_bookings = 0

    # Basic call/message conversion rates
    call_conversion_rate = 0
    if len(calls) > 0 and 'status' in calls.columns:
        call_conversion_rate = len(calls[calls['status'] == 'booked']) / len(calls) * 100
    message_conversion_rate = 0
    if len(messages) > 0 and 'status' in messages.columns:
        message_conversion_rate = len(messages[messages['status'] == 'booked']) / len(messages) * 100

    # Basic agent performance (calls vs. bookings)
    if not bookings.empty:
        agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    else:
        agent_bookings = pd.DataFrame(columns=['userId','total_bookings'])

    agent_calls_count = calls.groupby('userId').size().reset_index(name='total_calls') if not calls.empty else pd.DataFrame(columns=['userId','total_calls'])

    agent_performance = pd.merge(agent_calls_count, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = np.where(
        agent_performance['total_calls']>0,
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100,
        0
    )
    agent_performance['Agent'] = agent_performance['userId'].map(agent_map)

    # Show some key metrics
    st.subheader("Key Metrics")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Bookings", total_bookings)
    with c2:
        st.metric("Call Conv. Rate", f"{call_conversion_rate:.2f}%")
    with c3:
        st.metric("Msg Conv. Rate", f"{message_conversion_rate:.2f}%")

    # If you want to do outbound call success:
    st.subheader("Outbound Call Success Rate")
    if not calls.empty and 'duration' in calls.columns:
        outbound_calls = calls[calls['direction'] == 'outgoing']
        max_dur = int(outbound_calls['duration'].max()) if not outbound_calls.empty else 60

        min_success_duration = st.slider(
            "Min Call Duration (seconds) for 'successful' call?",
            min_value=0, max_value=max_dur, value=30
        )
        successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]
        success_rate = 0
        if len(outbound_calls) > 0:
            success_rate = len(successful_outbound_calls)/len(outbound_calls)*100

        st.write(f"Overall Outbound Success Rate: {success_rate:.2f}%")

    # (You can continue with your prior code for hourly analysis, heatmaps, etc.)
    # E.g. day/hour definitions:
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hour_order = [
        "12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
        "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
        "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"
    ]
    # If you want to run the #20 text success rate heatmap:
    if not messages.empty:
        run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map)

    # #22 compare call durations with preceding text
    if not messages.empty and not calls.empty:
        run_call_duration_preceded_by_text(messages, calls, default_time_window=8)

    st.success("Dashboard Complete (GMT-4)!")


###############################################################################
# Optional: If you want to run as a Streamlit app directly
###############################################################################
# def main():
#     run_openphone_tab()
#
# if __name__ == "__main__":
#     main()
