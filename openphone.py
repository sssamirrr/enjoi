import streamlit as st
import pandas as pd

def run_openphone_tab():
    # ... (the code that reads your CSV into `openphone_data`, does timezone conversion, etc.) ...

    # 1) EXTRACT VALID AGENTS = only those with '@enjoiresorts.com'
    valid_emails = [
        agent for agent in openphone_data['userId'].dropna().unique()
        if agent.endswith('@enjoiresorts.com')
    ]

    # 2) CREATE SHORT NAMES by splitting on '@'
    display_names = [email.split('@')[0] for email in valid_emails]  # e.g. "m.allen"

    # 3) MAP display name -> full email
    agent_map = dict(zip(display_names, valid_emails))

    # 4) MULTISELECT uses the short names
    selected_display_names = st.multiselect(
        "Select Agents (Enjoi Resorts Only)",
        options=sorted(display_names),
        default=[]
    )

    # 5) Convert selected short names back to full emails
    selected_full_emails = [agent_map[name] for name in selected_display_names]

    # 6) FILTER your data
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_full_emails)]

    # ... (rest of your dashboard code that uses `openphone_data` and/or `calls`, etc.) ...
