# Add to your existing imports and configurations

def fetch_transcript(call_id):
    """Fetch transcript for a specific call"""
    url = f"https://api.openphone.com/v1/calls/{call_id}/transcript"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", {})
    return None

def format_transcript(transcript):
    """Format transcript for display"""
    if not transcript:
        return "No transcript available"
    
    formatted_text = ""
    for segment in transcript.get('segments', []):
        speaker = "Agent" if segment.get('speakerId') == 0 else "Customer"
        text = segment.get('text', '')
        timestamp = segment.get('startTime', 0)
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        formatted_text += f"[{minutes:02d}:{seconds:02d}] **{speaker}**: {text}\n\n"
    
    return formatted_text

def display_timeline(calls, messages):
    st.subheader("📅 Communication Timeline")
    
    # Combine and sort all communications
    timeline = []
    
    for call in calls:
        timeline.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown'),
            'id': call.get('id'),  # Add call ID for transcript lookup
            'recording_url': call.get('recordingUrl'),  # Add recording URL if available
        })
    
    for message in messages:
        timeline.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown')
        })
    
    # Sort by time
    timeline.sort(key=lambda x: x['time'], reverse=True)
    
    # Display timeline
    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if item['type'] == "Call":
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Duration:** {item['duration']} seconds")
                    st.write(f"**Status:** {item['status']}")
                    
                    # Add recording link if available
                    if item.get('recording_url'):
                        st.audio(item['recording_url'], format='audio/mp3')
                    
                    # Add transcript button and display
                    if item.get('id'):
                        if st.button(f"Load Transcript", key=f"transcript_{item['id']}"):
                            with st.spinner('Loading transcript...'):
                                transcript = fetch_transcript(item['id'])
                                if transcript:
                                    st.markdown(format_transcript(transcript))
                                else:
                                    st.warning("No transcript available for this call")
                
                with col2:
                    # Display call metadata or additional information
                    if item.get('recording_url'):
                        st.write("📀 Recording available")
            else:
                st.write(f"**Message:** {item['content']}")
                st.write(f"**Status:** {item['status']}")
                
                # If message has attachments, display them
                if 'attachments' in item:
                    for attachment in item['attachments']:
                        if attachment.get('url'):
                            # Display image attachments
                            if attachment.get('type', '').startswith('image/'):
                                st.image(attachment['url'])
                            # Display other attachments as links
                            else:
                                st.markdown(f"[📎 Attachment]({attachment['url']})")

def display_detailed_metrics(calls, messages):
    """Display detailed communication metrics"""
    st.subheader("📊 Detailed Metrics")
    
    # Call metrics
    if calls:
        st.write("### Call Statistics")
        recorded_calls = len([c for c in calls if c.get('recordingUrl')])
        transcribed_calls = len([c for c in calls if c.get('id')])  # Assuming all calls with IDs can be transcribed
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Calls", len(calls))
        with col2:
            st.metric("Recorded Calls", recorded_calls)
        with col3:
            st.metric("Transcribable Calls", transcribed_calls)
        
        # Call duration distribution
        call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
        if call_durations:
            fig = px.histogram(
                x=call_durations,
                title="Call Duration Distribution",
                labels={'x': 'Duration (seconds)', 'y': 'Count'}
            )
            st.plotly_chart(fig)
    
    # Message metrics
    if messages:
        st.write("### Message Statistics")
        messages_with_attachments = len([m for m in messages if m.get('attachments')])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Messages", len(messages))
        with col2:
            st.metric("Messages with Attachments", messages_with_attachments)

def main():
    st.set_page_config(page_title="Communication Analytics", 
                      page_icon="📊", 
                      layout="wide")

    st.title("📱 Communication Analytics Dashboard")

    query_params = st.experimental_get_query_params()
    phone_number = query_params.get("phone", [""])[0]
    
    if not phone_number:
        phone_number = st.text_input("Enter phone number:")
    
    if phone_number:
        with st.spinner('Loading communication history...'):
            calls = fetch_call_history(phone_number)
            messages = fetch_message_history(phone_number)

            if not calls and not messages:
                st.warning("No communication history found for this number.")
                return

            # Create tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Overview", 
                "📈 Analysis", 
                "📅 Timeline",
                "🎯 Detailed Metrics"
            ])

            with tab1:
                metrics = create_communication_metrics(calls, messages)
                display_metrics_dashboard(metrics)

            with tab2:
                display_communications_analysis(calls, messages)

            with tab3:
                display_timeline(calls, messages)
            
            with tab4:
                display_detailed_metrics(calls, messages)

if __name__ == "__main__":
    main()
