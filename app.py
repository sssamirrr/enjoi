import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for styling
st.markdown("""
    <style>
    .stDateInput {
        width: 100%;
    }
    div[data-baseweb="input"] {
        width: 100%;
    }
    .stDateInput > div {
        width: 100%;
    }
    div[data-baseweb="input"] > div {
        width: 100%;
    }
    .stDataFrame {
        width: 100%;
    }
    .dataframe-container {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Create a connection to Google Sheets
@st.cache_resource
def get_google_sheet_data():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# Load the data
df = get_google_sheet_data()

if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

# Create tabs
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

# Dashboard Tab (existing code remains the same)
with tab1:
    # ... (paste your existing Dashboard tab code here)

# Marketing Tab (existing code remains the same)
with tab2:
    # ... (paste your existing Marketing tab code here)

# Tour Prediction Tab
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    
    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.to_datetime(df['Arrival Date Short']).min().date())
    with col2:
        end_date = st.date_input("End Date", value=pd.to_datetime(df['Arrival Date Short']).max().date())
    
    # Filter data for selected resort and date range
    resort_df = df[df['Market'] == selected_resort].copy()
    resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'])
    filtered_resort_df = resort_df[
        (resort_df['Arrival Date Short'].dt.date >= start_date) & 
        (resort_df['Arrival Date Short'].dt.date <= end_date)
    ]
    
    # Daily Arrivals
    daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index()
    daily_arrivals.columns = ['Date', 'Arrivals']
    
    # Conversion Rate Input
    conversion_rate = st.number_input(
        f"Conversion Rate for {selected_resort} (%)", 
        min_value=0.0, 
        max_value=100.0, 
        value=10.0, 
        step=0.5
    ) / 100
    
    # Calculate Tours
    daily_arrivals['Tours'] = (daily_arrivals['Arrivals'] * conversion_rate).apply(lambda x: round(x))
    
    # Display Daily Arrivals and Tours
    st.subheader(f"Arrivals and Tours for {selected_resort}")
    results_df = daily_arrivals.copy()
    results_df['Date'] = results_df['Date'].astype(str)
    
    # Editable data editor for manual tour adjustments
    edited_results = st.data_editor(
        results_df, 
        column_config={
            "Date": st.column_config.TextColumn("Date"),
            "Arrivals": st.column_config.NumberColumn("Arrivals", disabled=True),
            "Tours": st.column_config.NumberColumn("Tours", help="Calculated or manually adjusted tours")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Arrivals", filtered_resort_df.shape[0])
    with col2:
        st.metric("Estimated Tours", edited_results['Tours'].sum())
    with col3:
        st.metric("Average Daily Tours", edited_results['Tours'].mean())
    
    # Visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Arrivals Chart
        fig_arrivals = px.bar(
            edited_results, 
            x='Date', 
            y='Arrivals', 
            title=f'Daily Arrivals - {selected_resort}'
        )
        st.plotly_chart(fig_arrivals, use_container_width=True)
    
    with col2:
        # Tours Chart
        fig_tours = px.bar(
            edited_results, 
            x='Date', 
            y='Tours', 
            title=f'Estimated Tours - {selected_resort}'
        )
        st.plotly_chart(fig_tours, use_container_width=True)
    
    # Comprehensive Resort and Overall Tour Summary
    st.markdown("---")
    st.subheader("Resort and Overall Tour Summary")
    
    # Prepare summary for all resorts
    all_resort_summary = []
    
    for resort in sorted(df['Market'].unique()):
        # Filter data for each resort
        resort_data = df[df['Market'] == resort].copy()
        resort_data['Arrival Date Short'] = pd.to_datetime(resort_data['Arrival Date Short'])
        filtered_data = resort_data[
            (resort_data['Arrival Date Short'].dt.date >= start_date) & 
            (resort_data['Arrival Date Short'].dt.date <= end_date)
        ]
        
        # Calculate resort-specific summary
        daily_resort_arrivals = filtered_data.groupby(filtered_data['Arrival Date Short'].dt.date).size().reset_index()
        daily_resort_arrivals.columns = ['Date', 'Arrivals']
        
        # Use a default conversion rate if not specified (you might want to store this in a configuration)
        resort_conversion_rate = 0.1  # 10% default
        
        daily_resort_arrivals['Tours'] = (daily_resort_arrivals['Arrivals'] * resort_conversion_rate).apply(lambda x: round(x))
        
        resort_summary = {
            'Resort': resort,
            'Total Arrivals': filtered_data.shape[0],
            'Total Tours': daily_resort_arrivals['Tours'].sum(),
            'Average Daily Tours': daily_resort_arrivals['Tours'].mean()
        }
        
        all_resort_summary.append(resort_summary)
    
    # Convert summary to DataFrame and display
    summary_df = pd.DataFrame(all_resort_summary)
    st.dataframe(summary_df, use_container_width=True)
    
    # Overall Totals
    st.subheader("Overall Totals")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Arrivals Across Resorts", summary_df['Total Arrivals'].sum())
    with col2:
        st.metric("Total Estimated Tours", summary_df['Total Tours'].sum())
    with col3:
        st.metric("Average Daily Tours Across Resorts", summary_df['Average Daily Tours'].mean())

# Raw data viewer
with st.expander("Show Raw Data"):
    st.dataframe(df)
