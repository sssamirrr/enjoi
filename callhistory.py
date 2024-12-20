# Add these imports at the top
import altair as alt
from datetime import timedelta
import numpy as np

# Add these new visualization functions:

def create_communication_trend_chart(communications):
    """Creates a trend chart showing communication patterns over time"""
    df = pd.DataFrame(communications)
    df['date'] = pd.to_datetime(df['time']).dt.date
    
    # Count daily communications by type
    daily_counts = df.groupby(['date', 'type']).size().reset_index(name='count')
    
    chart = alt.Chart(daily_counts).mark_line(point=True).encode(
        x='date:T',
        y='count:Q',
        color='type:N',
        tooltip=['date', 'type', 'count']
    ).properties(
        title='Daily Communication Trends',
        width=700,
        height=400
    ).interactive()
    
    return chart

def create_hourly_distribution_chart(communications):
    """Creates a heatmap showing communication patterns by hour and day of week"""
    df = pd.DataFrame(communications)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    df['day_of_week'] = pd.to_datetime(df['time']).dt.day_name()
    
    hourly_counts = df.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    
    # Order days of week correctly
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hourly_counts['day_of_week'] = pd.Categorical(hourly_counts['day_of_week'], categories=days_order, ordered=True)
    
    heatmap = alt.Chart(hourly_counts).mark_rect().encode(
        x=alt.X('hour:O', title='Hour of Day'),
        y=alt.Y('day_of_week:O', title='Day of Week'),
        color=alt.Color('count:Q', scale=alt.Scale(scheme='viridis')),
        tooltip=['day_of_week', 'hour', 'count']
    ).properties(
        title='Communication Activity Heatmap',
        width=700,
        height=300
    )
    
    return heatmap

def create_response_time_histogram(response_times):
    """Creates a histogram of response times"""
    if not response_times:
        return None
        
    df = pd.DataFrame({'response_time': response_times})
    
    histogram = alt.Chart(df).mark_bar().encode(
        x=alt.X('response_time', bin=alt.Bin(maxbins=20), title='Response Time (minutes)'),
        y=alt.Y('count()', title='Frequency'),
        tooltip=['count()']
    ).properties(
        title='Response Time Distribution',
        width=700,
        height=300
    )
    
    return histogram

def create_direction_chart(communications):
    """Creates a bar chart showing inbound vs outbound communications"""
    df = pd.DataFrame(communications)
    direction_counts = df.groupby(['type', 'direction']).size().reset_index(name='count')
    
    bars = alt.Chart(direction_counts).mark_bar().encode(
        x='type:N',
        y='count:Q',
        color='direction:N',
        tooltip=['type', 'direction', 'count']
    ).properties(
        title='Communication Direction Distribution',
        width=700,
        height=300
    )
    
    return bars

# Modify the display_metrics function to include these visualizations:

def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")
    
    # Basic Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", inbound_calls)
    with col4:
        st.metric("Outbound Calls", outbound_calls)

    # Prepare communications data
    communications = []
    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction'),
            'duration': call.get('duration', 0)
        })
    
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction'),
            'content': message.get('content', '')
        })

    # Communication Trends
    st.subheader("📈 Communication Trends")
    trend_chart = create_communication_trend_chart(communications)
    st.altair_chart(trend_chart, use_container_width=True)

    # Activity Heatmap
    st.subheader("🗓️ Activity Patterns")
    heatmap = create_hourly_distribution_chart(communications)
    st.altair_chart(heatmap, use_container_width=True)

    # Direction Distribution
    st.subheader("↔️ Communication Direction")
    direction_chart = create_direction_chart(communications)
    st.altair_chart(direction_chart, use_container_width=True)

    # Call Duration Analysis
    if calls:
        st.subheader("⏱️ Call Duration Analysis")
        call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
        if call_durations:
            df_durations = pd.DataFrame({'duration': call_durations})
            duration_chart = alt.Chart(df_durations).mark_bar().encode(
                x=alt.X('duration', bin=alt.Bin(maxbins=20), title='Duration (seconds)'),
                y='count()',
                tooltip=['count()']
            ).properties(
                title='Call Duration Distribution',
                width=700,
                height=300
            )
            st.altair_chart(duration_chart, use_container_width=True)

    # Response Time Analysis
    st.subheader("⌛ Response Time Analysis")
    response_times = calculate_response_times(communications)
    if response_times:
        response_chart = create_response_time_histogram(response_times)
        if response_chart:
            st.altair_chart(response_chart, use_container_width=True)

    # Message Length Analysis
    if messages:
        st.subheader("📝 Message Length Analysis")
        message_lengths = [len(m.get('content', '')) for m in messages if m.get('content')]
        if message_lengths:
            df_lengths = pd.DataFrame({'length': message_lengths})
            length_chart = alt.Chart(df_lengths).mark_bar().encode(
                x=alt.X('length', bin=alt.Bin(maxbins=20), title='Message Length (characters)'),
                y='count()',
                tooltip=['count()']
            ).properties(
                title='Message Length Distribution',
                width=700,
                height=300
            )
            st.altair_chart(length_chart, use_container_width=True)

# Update the main display_history function to include a new tab for analytics:

def display_history(phone_number):
    st.title(f"📱 Communication History for {phone_number}")
    
    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    # Display all sections in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Analytics", "📅 Timeline", "📋 Details"])
    
    with tab1:
        display_metrics(calls, messages)
    
    with tab2:
        display_detailed_analytics(calls, messages)
    
    with tab3:
        display_timeline(calls, messages)
    
    with tab4:
        display_detailed_history(calls, messages)

def display_detailed_analytics(calls, messages):
    st.header("📊 Detailed Analytics")
    
    # Add any additional detailed analytics you want to show here
    # This could include more specific breakdowns, correlations, etc.
    
    # Example: Communication patterns by day of week
    communications = prepare_communications_data(calls, messages)
    df = pd.DataFrame(communications)
    df['day_of_week'] = pd.to_datetime(df['time']).dt.day_name()
    
    daily_pattern = alt.Chart(df).mark_bar().encode(
        x='day_of_week:N',
        y='count()',
        color='type:N',
        tooltip=['day_of_week', 'type', 'count()']
    ).properties(
        title='Communication Patterns by Day of Week',
        width=700,
        height=300
    )
    
    st.altair_chart(daily_pattern, use_container_width=True)

def prepare_communications_data(calls, messages):
    """Helper function to prepare communications data for analysis"""
    communications = []
    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction'),
            'duration': call.get('duration', 0)
        })
    
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction'),
            'content': message.get('content', '')
        })
    
    return communications
