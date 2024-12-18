def display_map(df):
    """
    Display map of owner locations based on ZIP codes.
    """
    if 'Zip Code' not in df.columns or df['Zip Code'].dropna().empty:
        st.warning("No ZIP Code data available to display the map.")
        return
    
    try:
        nomi = pgeocode.Nominatim('us')
        valid_zips = df['Zip Code'].dropna().astype(str)  # Ensure ZIP codes are strings
        zip_data = nomi.query_postal_code(valid_zips.tolist())
        
        if zip_data is not None and not zip_data.empty:
            map_data = pd.DataFrame({
                'lat': zip_data['latitude'],
                'lon': zip_data['longitude']
            }).dropna()
            if not map_data.empty:
                st.map(map_data)
            else:
                st.warning("No valid coordinates found for ZIP codes.")
        else:
            st.warning("Invalid ZIP codes provided.")
    except Exception as e:
        st.error(f"Error generating map: {e}")
