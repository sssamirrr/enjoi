import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Timeshare Marketing Dashboard",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .stMetric:hover {
        background-color: #e0e2e6;
    }
    .stTab {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

def calculate_additional_metrics(calls, messages, bookings):
    metrics = {
        'total_interactions': len(calls) + len(messages),
        'avg_call_duration': calls['duration'].mean() if 'duration' in calls.columns else 0,
        'callback_rate': (
            len(calls[calls['direction'] == 'incoming']) / 
            len(calls[calls['direction'] == 'outgoing']) * 100
            if len(calls[calls['direction'] == 'outgoing']) > 0 else 0
        ),
        'peak_hour': calls['hour'].mode().iloc[0] if not calls.empty else "N/A",
        'booking_rate': (len(bookings) / len(calls) * 100) if len(calls) > 0 else 0
    }
    return metrics

def run_openphone_tab():
    st.title("📞 Timeshare Marketing Operations Dashboard")

    # File upload
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    # Load and process data
    openphone_data = pd.read_csv(uploaded_file)

    # Time zone conversion
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])

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

    # Date range filters
    st.sidebar.header("📅 Date Range")
    min_date = openphone_data['createdAtET'].min().date()
    max_date = openphone_data['createdAtET'].max().date()
    
    start_date = st.sidebar.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Start date cannot exceed end date.")
        return

    # Filter by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # Agent filter
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    all_agents = sorted([
        agent for agent in openphone_data['userId'].dropna().unique()
        if agent.endswith("@enjoiresorts.com")
    ])

    def short_agent_name(full_email):
        return full_email.replace("@enjoiresorts.com", "")

    agent_map = {agent: short_agent_name(agent) for agent in all_agents}
    agent_choices = list(agent_map.values())

    st.sidebar.header("👥 Agent Selection")
    selected_short_names = st.sidebar.multiselect(
        "Select Agents",
        agent_choices,
        default=[]
    )

    selected_agents = [
        full_email
        for full_email, short_name in agent_map.items()
        if short_name in selected_short_names
    ]

    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]

    # Split data
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']
    bookings = openphone_data[openphone_data['status'] == 'booked']

    # Calculate metrics
    total_bookings = len(bookings)
    call_conversion_rate = (
        len(calls[calls['status'] == 'booked']) / len(calls) * 100
        if len(calls) > 0 else 0
    )
    message_conversion_rate = (
        len(messages[messages['status'] == 'booked']) / len(messages) * 100
        if len(messages) > 0 else 0
    )

    # Additional metrics
    metrics = calculate_additional_metrics(calls, messages, bookings)

    # Main Dashboard Layout
    st.header("📊 Performance Overview")

    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Bookings 📚", 
            f"{total_bookings}",
            help="Total number of successful bookings"
        )

    with col2:
        st.metric(
            "Call Conversion 📈",
            f"{call_conversion_rate:.1f}%",
            help="Percentage of calls resulting in bookings"
        )

    with col3:
        st.metric(
            "Avg Call Duration ⏱️",
            f"{metrics['avg_call_duration']:.1f}s",
            help="Average duration of all calls"
        )

    with col4:
        st.metric(
            "Callback Rate 📞",
            f"{metrics['callback_rate']:.1f}%",
            help="Percentage of outbound calls that received callbacks"
        )

    # Second row of metrics
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(
            "Total Interactions 🤝",
            f"{metrics['total_interactions']}",
            help="Sum of all calls and messages"
        )

    with col6:
        st.metric(
            "Message Conv. Rate 💬",
            f"{message_conversion_rate:.1f}%",
            help="Percentage of messages leading to bookings"
        )

    # ROI Calculator in Sidebar
    st.sidebar.header("💰 ROI Calculator")
    avg_booking_value = st.sidebar.number_input(
        "Average Booking Value ($)",
        min_value=0,
        value=1000
    )
    cost_per_call = st.sidebar.number_input(
        "Cost per Call ($)",
        min_value=0,
        value=5
    )

    if not calls.empty:
        total_cost = len(calls) * cost_per_call
        total_revenue = total_bookings * avg_booking_value
        roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        
        st.sidebar.metric(
            "Campaign ROI",
            f"{roi:.1f}%",
            help="Return on Investment for the campaign"
        )

    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📞 Call Analytics", 
        "👥 Agent Performance", 
        "⏰ Time Analysis",
        "📊 Conversion Metrics"
    ])

    # Tab 1: Call Analytics
    with tab1:
        st.subheader("Call Volume Analysis")
        
        # Hourly call distribution
        if not calls.empty:
            hourly_stats = calls.groupby(['hour','direction']).size().reset_index(name='count')
            fig = px.bar(
                hourly_stats, 
                x='hour', 
                y='count', 
                color='direction',
                barmode='group', 
                title="Calls by Hour"
            )
            st.plotly_chart(fig)

        # Call duration distribution
        if 'duration' in calls.columns and not calls['duration'].isnull().all():
            fig_duration = px.histogram(
                calls,
                x='duration',
                title="Call Duration Distribution",
                nbins=50
            )
            st.plotly_chart(fig_duration)

    # Tab 2: Agent Performance
    with tab2:
        if not calls.empty and len(selected_agents) > 0:
            # Agent booking performance
            agent_stats = calls.groupby('userId').agg({
                'status': lambda x: (x == 'booked').sum(),
                'duration': 'mean'
            }).reset_index()
            
            agent_stats['Agent'] = agent_stats['userId'].map(agent_map)
            agent_stats.columns = ['userId', 'Bookings', 'Avg Duration', 'Agent']
            
            fig_agent = px.bar(
                agent_stats,
                x='Agent',
                y=['Bookings', 'Avg Duration'],
                barmode='group',
                title="Agent Performance Metrics"
            )
            st.plotly_chart(fig_agent)

    # Tab 3: Time Analysis
    with tab3:
        st.subheader("Time-based Patterns")
        
        if not calls.empty:
            # Create heatmap of call volume
            calls['day_name'] = calls['createdAtET'].dt.day_name()
            calls['hour'] = calls['createdAtET'].dt.hour
            
            heatmap_data = calls.pivot_table(
                index='day_name',
                columns='hour',
                values='duration',
                aggfunc='count',
                fill_value=0
            )
            
            fig_heatmap = px.imshow(
                heatmap_data,
                title="Call Volume Heatmap",
                labels=dict(x="Hour of Day", y="Day of Week", color="Number of Calls")
            )
            st.plotly_chart(fig_heatmap)

    # Tab 4: Conversion Metrics
    with tab4:
        st.subheader("Conversion Analytics")

        # Conversion Funnel
        funnel_data = {
            'Stage': ['Total Contacts', 'Engaged (>1min)', 'Interested (>5min)', 'Booked'],
            'Count': [
                len(calls),
                len(calls[calls['duration'] > 60]),
                len(calls[calls['duration'] > 300]),
                total_bookings
            ]
        }
        fig_funnel = px.funnel(funnel_data, x='Count', y='Stage')
        st.plotly_chart(fig_funnel)

        # Lead Quality Score
        if not calls.empty:
            calls['lead_quality_score'] = calls.apply(
                lambda x: (
                    10 if x['status'] == 'booked' 
                    else 7 if x['duration'] > 300
                    else 5 if x['duration'] > 120
                    else 3 if x['duration'] > 60
                    else 1
                ),
                axis=1
            )
            
            fig_lead_quality = px.box(
                calls,
                x='userId',
                y='lead_quality_score',
                title="Lead Quality Distribution by Agent",
                color='status'
            )
            st.plotly_chart(fig_lead_quality)

        # Download section
        st.subheader("📥 Download Reports")
        if st.button("Generate Report"):
            csv = calls.to_csv(index=False)
            st.download_button(
                label="Download Full Report",
                data=csv,
                file_name="timeshare_marketing_report.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    run_openphone_tab()
