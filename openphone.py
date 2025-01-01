# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 18. AGENT-BY-AGENT HEATMAPS: Success Rate & Outbound Calls
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
st.subheader("Agent-by-Agent Heatmaps: Success Rate & Outbound Calls")

if len(selected_agents) >= 1 and not successful_outbound_calls.empty and not outbound_calls.empty:
    for agent_id in selected_agents:
        agent_name = agent_map.get(agent_id, agent_id)

        st.markdown(f"### {agent_name}")
        col1, col2 = st.columns(2)

        # Build data
        agent_outbound = outbound_calls[outbound_calls['userId'] == agent_id].copy()
        agent_success  = successful_outbound_calls[successful_outbound_calls['userId'] == agent_id].copy()

        outb_df = agent_outbound.groupby(['day','hour']).size().reset_index(name='outbound_count')
        succ_df = agent_success.groupby(['day','hour']).size().reset_index(name='success_count')
        merged_df = pd.merge(outb_df, succ_df, on=['day','hour'], how='outer').fillna(0)
        merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100

        # Summaries for agent
        total_outbound_left = merged_df['outbound_count'].sum()
        total_outbound_right = total_outbound_left  # same in both columns

        # --- Left Column: Success Rate ---
        with col1:
            st.subheader("Success Rate (%)")
            if total_outbound_left == 0:
                st.write("No outbound calls for this agent.")
            else:
                df_rate = merged_df[['day','hour','success_rate','success_count','outbound_count']].copy()

                fig_rate = px.density_heatmap(
                    df_rate,
                    x='hour',
                    y='day',
                    z='success_rate',
                    histfunc='avg',
                    nbinsx=len(hour_order),
                    nbinsy=len(day_order),
                    color_continuous_scale='RdYlGn',  # or 'Blues', your choice
                    range_color=[0, 100],
                    title="Success Rate by Day/Hour"
                )

                # Enhanced tooltip with success_count & outbound_count
                fig_rate.update_traces(
                    customdata=df_rate[['success_count', 'outbound_count']].values,
                    hovertemplate=(
                        "Hour: %{x}<br>"
                        "Day: %{y}<br>"
                        "Success Rate: %{z:.1f}%<br>"
                        "Successful Calls: %{customdata[0]}<br>"
                        "Total Calls: %{customdata[1]}"
                    ),
                    selector=dict(type='heatmap')
                )
                fig_rate.update_yaxes(categoryorder='array', categoryarray=day_order)
                fig_rate.update_xaxes(categoryorder='array', categoryarray=hour_order)
                fig_rate.update_layout(height=400)
                st.plotly_chart(fig_rate, use_container_width=True)

        # --- Right Column: Outbound Calls ---
        with col2:
            st.subheader("Total Outbound Calls (#)")
            if total_outbound_right == 0:
                st.write("No outbound calls for this agent.")
            else:
                df_calls = merged_df[['day','hour','outbound_count','success_count','success_rate']].copy()

                fig_calls = px.density_heatmap(
                    df_calls,
                    x='hour',
                    y='day',
                    z='outbound_count',
                    histfunc='sum',
                    nbinsx=len(hour_order),
                    nbinsy=len(day_order),
                    color_continuous_scale='Blues',
                    title="Outbound Calls by Day/Hour"
                )

                # Enhanced tooltip with success_count & success_rate
                fig_calls.update_traces(
                    customdata=df_calls[['success_count', 'success_rate']].values,
                    hovertemplate=(
                        "Hour: %{x}<br>"
                        "Day: %{y}<br>"
                        "Total Calls: %{z}<br>"
                        "Successful Calls: %{customdata[0]}<br>"
                        "Success Rate: %{customdata[1]:.1f}%"
                    ),
                    selector=dict(type='heatmap')
                )
                fig_calls.update_yaxes(categoryorder='array', categoryarray=day_order)
                fig_calls.update_xaxes(categoryorder='array', categoryarray=hour_order)
                fig_calls.update_layout(height=400)
                st.plotly_chart(fig_calls, use_container_width=True)

    # (Optional) Summary table for all agents
    st.subheader("Summary Table: Outbound Calls & Success Rate")
    total_success = successful_outbound_calls.groupby('userId').size()
    total_calls_df = outbound_calls.groupby('userId').size()
    summary_df = pd.DataFrame({
        'Total Outbound Calls': total_calls_df,
        'Successful Calls': total_success
    }).fillna(0)
    summary_df['Success Rate (%)'] = (
        summary_df['Successful Calls'] / summary_df['Total Outbound Calls'] * 100
    ).round(1)
    summary_df['Agent'] = summary_df.index.map(agent_map)
    summary_table = summary_df[['Agent','Successful Calls','Total Outbound Calls','Success Rate (%)']]
    st.table(summary_table)

else:
    st.warning("No outbound calls or no agents selected. Cannot show agent-by-agent heatmaps.")
