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
        df = pd.read_csv(file, skiprows=1)
        # Ensure the first column (which is 'Day') is renamed to 'date'
        df.columns.values[0] = 'date'
        
        # Convert 'date' column to datetime objects with the correct format
        try:
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')
        except ValueError as e:
            st.error(f"Error parsing dates in '{file.name}'. Please ensure the date format is 'YYYY-MM-DD'. Error: {e}")
            st.stop() # Stop execution if date parsing fails

        # Identify anchor keyword (appears in all files)
        keywords = set(df.columns[1:])
        anchor_keywords.append(keywords)
        batch_dfs.append(df)

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
            # Handle cases where anchor_keyword might be 0 in the current batch to avoid division by zero
            df_merged['scaling_factor'] = np.where(
                df_merged[anchor_keyword] != 0,
                df_merged['anchor_ref'] / df_merged[anchor_keyword],
                np.nan # Setting to NaN for division by zero; consider if 0 or other value is more appropriate
            )
            
            # Create a copy to store normalized values
            norm_df = df.copy()

            # Apply the unique scaling factor for each row/date
            # Merge the scaling factors back to the original df for row-wise application
            norm_df = norm_df.merge(df_merged[['date', 'scaling_factor']], on='date', how='left')

            for col in norm_df.columns:
                if col not in ['date', 'scaling_factor']: # Exclude 'date' and the 'scaling_factor' column itself
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

        # --- CODE FOR ROUNDING NUMBERS ---
        for col in final_df.columns:
            if col != 'date' and pd.api.types.is_numeric_dtype(final_df[col]):
                final_df[col] = final_df[col].round().astype(int)
        # --- END CODE ---

        st.subheader("📈 Normalized Trends Line Chart")
        selected_keywords = st.multiselect("Select keywords to plot", final_df.columns[1:], default=final_df.columns[1:3])
        if selected_keywords:
            st.line_chart(final_df.set_index("date")[selected_keywords])

        # Download as Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # --- CODE FOR SHORT DATE FORMAT IN EXCEL ---
            # Create a copy to format date as string for Excel export only
            excel_df = final_df.copy()
            excel_df['date'] = excel_df['date'].dt.strftime('%Y-%m-%d')
            # --- END CODE ---
            excel_df.to_excel(writer, index=False, sheet_name='Normalized Trends')
        st.download_button("📥 Download Normalized Excel File", data=output.getvalue(), file_name="normalized_trends.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
