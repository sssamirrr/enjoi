# Home Value Filter
include_non_numeric_hv = st.checkbox(
    "Include Non-Numeric Home Value Entries (e.g. 'Apartment', 'Not available')?",
    value=True
)

if "Home Value" in df_map.columns:
    # Convert "Home Value" to numeric => invalid => NaN
    df_map["Home Value"] = pd.to_numeric(df_map["Home Value"], errors="coerce")

    # Separate the numeric and non-numeric values
    numeric_values = df_map["Home Value"].dropna()  # Only numeric values
    non_numeric_values = df_map[df_map["Home Value"].isna()]  # Non-numeric values

    # If non-numeric values should be included
    if include_non_numeric_hv:
        # You can keep both the numeric and non-numeric entries
        df_map = df_map
    else:
        # Keep only the numeric values
        df_map = df_map[df_map["Home Value"].notna()]

    # Now apply the numeric filter using the slider, if applicable
    if not numeric_values.empty:
        min_home_val = numeric_values.min()
        max_home_val = numeric_values.max()
        home_range = st.slider(
            "Home Value Range",
            min_value=float(min_home_val),
            max_value=float(max_home_val),
            value=(float(min_home_val), float(max_home_val))
        )

        # Apply home value filter for numeric data
        df_map = df_map[
            (df_map["Home Value"].fillna(-999999999) >= home_range[0]) & 
            (df_map["Home Value"].fillna(999999999) <= home_range[1])
        ]
