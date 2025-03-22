def display_history(phone_number):
    st.title(f"📱 Communication History for {phone_number}")
    
    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    # We keep tabs for "Metrics" and "Timeline" if you still want them:
    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])

    with tab1:
        display_metrics(calls, messages)

    with tab2:
        display_timeline(calls, messages)

    # ---------------------- NEW “Details” Tab (Book-style) ----------------------
    with tab3:
        st.header("Complete Communication History (Chronological)")

        # 1) Combine calls + messages into a single list
        communications = []

        # Add calls
        for c in calls:
            dt_obj = datetime.fromisoformat(c['createdAt'].replace('Z', '+00:00'))
            communications.append({
                'time': dt_obj,
                'type': 'call',
                'direction': c.get('direction', 'unknown'),  # inbound/outbound
                'from': c.get('from', {}).get('phoneNumber', 'Unknown'),
                'to': c.get('to', {}).get('phoneNumber', 'Unknown'),
                'status': c.get('status', 'unknown'),  # e.g. 'completed', 'missed', 'voicemail'
                'duration': c.get('duration', 0),      # raw seconds
            })

        # Add messages
        for m in messages:
            dt_obj = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
            # If your data has 'from'/'to' or participants, adapt as needed
            from_num = "Unknown"
            to_num = "Unknown"
            # for consistency with calls
            from_dict = m.get('from', {})
            to_dict = m.get('to', {})

            communications.append({
                'time': dt_obj,
                'type': 'message',
                'direction': m.get('direction', 'unknown'),  # inbound/outbound
                'from': from_dict.get('phoneNumber', 'Unknown'),
                'to': to_dict.get('phoneNumber', 'Unknown'),
                'text': m.get('text', 'No content')
            })

        # 2) Sort everything by timestamp (ascending)
        communications.sort(key=lambda x: x['time'])

        # 3) Print each item in chronological order
        for item in communications:
            timestamp_str = item['time'].strftime("%Y-%m-%d %H:%M")
            direction_str = item['direction'] or 'unknown'

            if item['type'] == 'call':
                # Check if the call was missed or completed
                if item['status'] == 'missed':
                    st.write(
                        f"**{timestamp_str}** - {direction_str} call "
                        f"from {item['from']} to {item['to']} **[MISSED]**"
                    )
                else:
                    # show the duration in min+sec
                    dur_str = format_duration_seconds(item['duration'])
                    st.write(
                        f"**{timestamp_str}** - {direction_str} call "
                        f"from {item['from']} to {item['to']} ({dur_str})"
                    )
            else:
                # It's a message
                st.write(
                    f"**{timestamp_str}** - {direction_str} message "
                    f"from {item['from']} to {item['to']}: {item.get('text','')}"
                )
