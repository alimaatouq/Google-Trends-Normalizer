import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.title("Google Trends Batch Normalizer")

st.markdown("""
Upload multiple CSV files (each from a separate Google Trends batch).
Each file must contain a common keyword to normalize across batches.
""")

uploaded_files = st.file_uploader("Upload Google Trends CSV Batches", type="csv", accept_multiple_files=True)

if uploaded_files:
    batch_dfs = []
    anchor_keywords = []

    for file in uploaded_files:
        # Read the CSV, skipping the first row as before
        df = pd.read_csv(file, skiprows=1)
        df.columns.values[0] = 'date'

        # --- IMPORTANT CHANGE HERE ---
        # Try a specific format. You might need to change this based on your actual data.
        # Common Google Trends formats:
        # '%Y-%m-%d' for 'YYYY-MM-DD'
        # '%m/%d/%Y' for 'MM/DD/YYYY'
        # '%m/%d/%y' for 'MM/DD/YY'
        # If your data is 'Month DD, YYYY' (e.g., 'January 15, 2023'), use '%B %d, %Y'
        
        try:
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d') # Try YYYY-MM-DD first
        except ValueError:
            try:
                df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y') # Then try MM/DD/YYYY
            except ValueError:
                try:
                    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%y') # Then try MM/DD/YY
                except ValueError:
                    # If all specific formats fail, let pandas try to infer, but errors might still occur
                    st.warning(f"Could not parse dates with specific formats for {file.name}. Attempting generic parse, but errors may occur.")
                    df['date'] = pd.to_datetime(df['date'], errors='coerce') # 'coerce' will turn unparseable dates into NaT (Not a Time)

        # Drop rows where date couldn't be parsed (NaT) if 'coerce' was used
        df.dropna(subset=['date'], inplace=True)
        # --- END IMPORTANT CHANGE ---

        # The rest of your code remains the same
        # Identify anchor keyword (appears in all files)
        keywords = set(df.columns[1:])
        anchor_keywords.append(keywords)
        batch_dfs.append(df)

    # ... (rest of your code, including anchor detection and normalization logic)
    # Auto-detect common anchor keyword
    common_keywords = set.intersection(*anchor_keywords)
    if len(common_keywords) == 0:
        st.error("No common keyword found across all batches.")
    else:
        anchor_keyword = list(common_keywords)[0]
        st.success(f"Auto-detected anchor keyword: **{anchor_keyword}**")

        # Use first batch as reference
        anchor_reference = batch_dfs[0][["date", anchor_keyword]].copy()
        anchor_reference.rename(columns={anchor_keyword: "anchor_ref"}, inplace=True)

        normalized_dfs = []

        for i, df in enumerate(batch_dfs):
            # Merge with anchor_reference to get scaling factors for each date
            df_merged = df.merge(anchor_reference, on="date", how='left')
            
            # Calculate scaling_factor for each row/date
            df_merged['scaling_factor'] = np.where(
                df_merged[anchor_keyword] != 0,
                df_merged['anchor_ref'] / df_merged[anchor_keyword],
                np.nan # Handle division by zero: set to NaN
            )
            
            # Create a copy to store normalized values
            norm_df = df.copy()

            # Apply the unique scaling factor for each row/date
            norm_df = norm_df.merge(df_merged[['date', 'scaling_factor']], on='date', how='left')

            for col in norm_df.columns:
                if col not in ['date', 'scaling_factor']:
                    # Multiply each value by its corresponding row's scaling_factor
                    # Fill NaNs in 'scaling_factor' with 0 before multiplication if that's desired behavior
                    # Otherwise, rows with NaN scaling_factor will result in NaN after multiplication
                    norm_df[col] = norm_df[col] * norm_df['scaling_factor']

            # Drop the scaling_factor column before appending
            norm_df = norm_df.drop(columns=['scaling_factor'])
            
            normalized_dfs.append(norm_df.set_index("date"))

        # Combine normalized data
        final_df = pd.concat(normalized_dfs, axis=1)
        final_df = final_df.loc[:,~final_df.columns.duplicated()].copy()
        final_df.reset_index(inplace=True)

        st.subheader("📈 Normalized Trends Line Chart")
        selected_keywords = st.multiselect("Select keywords to plot", final_df.columns[1:], default=final_df.columns[1:3])
        if selected_keywords:
            st.line_chart(final_df.set_index("date")[selected_keywords])

        # Download as Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Normalized Trends')
        st.download_button("📥 Download Normalized Excel File", data=output.getvalue(), file_name="normalized_trends.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
