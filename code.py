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
        df.columns.values[0] = 'date'
        df['date'] = pd.to_datetime(df['date'])

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
            df_merged = df.merge(anchor_reference, on="date", how='left') # Use left join to keep all dates from current df
            
            # Calculate scaling_factor for each row/date
            # Handle cases where anchor_keyword might be 0 in the current batch to avoid division by zero
            df_merged['scaling_factor'] = np.where(
                df_merged[anchor_keyword] != 0,
                df_merged['anchor_ref'] / df_merged[anchor_keyword],
                np.nan # Or 0, or some other handling for division by zero if appropriate for your data
            )
            
            # Create a copy to store normalized values
            norm_df = df.copy()

            # Apply the unique scaling factor for each row/date
            # Merge the scaling factors back to the original df for row-wise application
            norm_df = norm_df.merge(df_merged[['date', 'scaling_factor']], on='date', how='left')

            for col in norm_df.columns:
                if col not in ['date', 'scaling_factor']: # Exclude 'date' and the 'scaling_factor' column itself
                    # Multiply each value by its corresponding row's scaling_factor
                    # Use .fillna(0) or another strategy for NaNs in scaling_factor if needed
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
