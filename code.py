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
        # Read CSV, handling Google Trends header format
        df = pd.read_csv(file, skiprows=1)
        
        # Clean column names and set date
        df.columns.values[0] = 'date'
        df['date'] = pd.to_datetime(df['date'], dayfirst=True)  # Added dayfirst for DD-MM-YY format
        
        # Store keywords for anchor detection
        keywords = set(df.columns[1:])
        anchor_keywords.append(keywords)
        batch_dfs.append(df)

    # Auto-detect common anchor keyword
    common_keywords = set.intersection(*anchor_keywords)
    if len(common_keywords) == 0:
        st.error("No common keyword found across all batches.")
    else:
        # Let user select anchor if multiple options exist
        if len(common_keywords) > 1:
            anchor_keyword = st.selectbox("Select anchor keyword for normalization:", 
                                        list(common_keywords))
        else:
            anchor_keyword = list(common_keywords)[0]
            st.success(f"Auto-detected anchor keyword: **{anchor_keyword}**")

        # Use first batch as reference
        reference_batch = batch_dfs[0]
        anchor_reference = reference_batch[["date", anchor_keyword]].copy()
        anchor_reference.rename(columns={anchor_keyword: "anchor_ref"}, inplace=True)

        normalized_dfs = [reference_batch]  # First batch is our reference

        for i, df in enumerate(batch_dfs[1:], start=1):  # Start from second batch
            # Merge with reference anchor values
            df_merged = df.merge(anchor_reference, on="date")
            
            # Calculate daily ratios (like your Excel)
            df_merged['scaling_factor'] = df_merged[anchor_keyword] / df_merged['anchor_ref']
            
            # Normalize all columns (divide by ratio - matches Excel approach)
            norm_df = df.copy()
            for col in norm_df.columns:
                if col not in ['date', anchor_keyword]:
                    norm_df[col] = np.where(
                        df_merged['scaling_factor'] != 0,
                        df[col] / df_merged['scaling_factor'],
                        df[col]
                    )
            
            # Keep anchor column from reference batch for consistency
            norm_df[anchor_keyword] = anchor_reference['anchor_ref']
            normalized_dfs.append(norm_df.set_index("date"))

        # Combine normalized data
        final_df = pd.concat(normalized_dfs, axis=1)
        
        # Remove duplicate columns (keeping first occurrence)
        final_df = final_df.loc[:,~final_df.columns.duplicated()].copy()
        final_df.reset_index(inplace=True)

        # Display results
        st.subheader("📈 Normalized Trends")
        st.dataframe(final_df.style.format("{:.1f}"), height=300)

        st.subheader("📈 Normalized Trends Line Chart")
        selected_keywords = st.multiselect("Select keywords to plot", 
                                         final_df.columns[1:], 
                                         default=final_df.columns[1:3])
        if selected_keywords:
            st.line_chart(final_df.set_index("date")[selected_keywords])

        # Download as Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Normalized Trends')
            
            # Add ratio calculations sheet like your example
            comparison_df = batch_dfs[0][['date', anchor_keyword]].copy()
            comparison_df = comparison_df.merge(
                batch_dfs[1][['date', anchor_keyword]], 
                on='date', 
                suffixes=('_batch1', '_batch2'))
            comparison_df['ratio'] = comparison_df[f'{anchor_keyword}_batch2'] / comparison_df[f'{anchor_keyword}_batch1']
            comparison_df.to_excel(writer, sheet_name='Ratio Calculations', index=False))
            
        st.download_button(
            "📥 Download Normalized Excel File",
            data=output.getvalue(),
            file_name="normalized_trends.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
