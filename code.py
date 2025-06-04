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

uploaded_files = st.file_uploader("Upload Google Trends CSV Batches", 
                                type="csv", 
                                accept_multiple_files=True)

if uploaded_files and len(uploaded_files) >= 2:
    try:
        # Read and process all files
        batch_dfs = []
        anchor_keywords = []
        
        for file in uploaded_files:
            df = pd.read_csv(file, skiprows=1)
            df.columns.values[0] = 'date'
            df['date'] = pd.to_datetime(df['date'], dayfirst=True)
            keywords = set(df.columns[1:])
            anchor_keywords.append(keywords)
            batch_dfs.append(df)

        # Find common anchor keywords
        common_keywords = set.intersection(*anchor_keywords)
        
        if not common_keywords:
            st.error("No common keyword found across all batches.")
            st.stop()
            
        # Let user select anchor if multiple exist
        if len(common_keywords) > 1:
            anchor_keyword = st.selectbox("Select anchor keyword:", 
                                        list(common_keywords))
        else:
            anchor_keyword = list(common_keywords)[0]
            st.success(f"Using anchor keyword: {anchor_keyword}")

        # Normalization process
        reference_df = batch_dfs[0][['date', anchor_keyword]].copy()
        reference_df.columns = ['date', 'reference_value']
        
        normalized_dfs = [batch_dfs[0]]  # Keep first batch as-is
        
        for i in range(1, len(batch_dfs)):
            current_df = batch_dfs[i].copy()
            
            # Merge with reference values
            merged_df = pd.merge(current_df, reference_df, on='date')
            
            # Calculate per-date scaling ratios
            merged_df['ratio'] = merged_df['reference_value'] / merged_df[anchor_keyword]

            # Apply ratio to all relevant columns
            for col in current_df.columns:
                if col not in ['date', anchor_keyword]:
                    current_df[col] = current_df[col] * merged_df['ratio']

            # Set anchor values to match reference
            current_df[anchor_keyword] = reference_df['reference_value']
            normalized_dfs.append(current_df)

        # Combine all normalized data
        final_df = pd.concat([df.set_index('date') for df in normalized_dfs], axis=1)
        final_df = final_df.loc[:,~final_df.columns.duplicated()]
        final_df.reset_index(inplace=True)

        # Display results
        st.subheader("Normalized Data")
        st.dataframe(final_df)

        # Visualization
        st.subheader("Trend Visualization")
        cols_to_plot = st.multiselect("Select columns to plot",
                                    final_df.columns[1:],
                                    default=final_df.columns[1:3])
        
        if cols_to_plot:
            st.line_chart(final_df.set_index('date')[cols_to_plot])

        # Excel Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, sheet_name='Normalized Data', index=False)
            
            # Add ratio calculations
            ratio_df = pd.merge(
                batch_dfs[0][['date', anchor_keyword]],
                batch_dfs[1][['date', anchor_keyword]],
                on='date',
                suffixes=('_batch1', '_batch2')
            )
            ratio_df['ratio'] = ratio_df[f'{anchor_keyword}_batch1'] / ratio_df[f'{anchor_keyword}_batch2']
            ratio_df.to_excel(writer, sheet_name='Scaling Factors', index=False)
            
        st.download_button(
            "Download Normalized Data",
            data=output.getvalue(),
            file_name="normalized_trends.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
elif uploaded_files and len(uploaded_files) < 2:
    st.warning("Please upload at least 2 files for normalization")
