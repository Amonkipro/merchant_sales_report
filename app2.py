import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

# Custom CSS for navy blue and whitish theme with Poppins font
st.markdown("""
<style>
    /* Import Poppins font from Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

    /* Apply Poppins font and navy blue theme */
    body {
        font-family: 'Poppins', sans-serif;
        background-color: #F5F7FA; /* Whitish background */
        color: #1A2B5F; /* Navy blue text */
    }
    .stApp {
        background-color: #F5F7FA;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #1A2B5F; /* Navy blue headers */
        font-weight: 600;
    }
    .stMetric {
        background-color: #FFFFFF; /* White background for metrics */
        border: 1px solid #1A2B5F; /* Navy blue border */
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .stButton>button {
        background-color: #1A2B5F; /* Navy blue buttons */
        color: #FFFFFF; /* White text */
        border-radius: 8px;
        font-family: 'Poppins', sans-serif;
        font-weight: 400;
    }
    .stButton>button:hover {
        background-color: #2C3E7A; /* Lighter navy on hover */
        color: #FFFFFF;
    }
    .sidebar .sidebar-content {
        background-color: #1A2B5F; /* Navy blue sidebar */
        color: #FFFFFF;
    }
    .sidebar .sidebar-content .stMultiSelect div, .sidebar .sidebar-content .stTextArea textarea {
        background-color: #FFFFFF; /* White input fields */
        color: #1A2B5F;
        border-radius: 8px;
    }
    .stExpander {
        background-color: #FFFFFF;
        border: 1px solid #1A2B5F;
        border-radius: 8px;
    }
    .stDataFrame {
        background-color: #FFFFFF;
        border-radius: 8px;
    }
    /* Customize Plotly charts */
    .plotly-chart {
        background-color: #FFFFFF;
        border: 1px solid #1A2B5F;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Page config
st.set_page_config(page_title="Sales Analysis Dashboard", layout="wide", page_icon="📊")

# App title and description
st.title("📊 Sales Analysis Dashboard")
st.markdown("Upload one or more tab-separated `.xls`, `.xlsx`, or `.csv` files with the same structure to analyze revenue, transactions, and more. Channel Type filters apply only to charts and the downloadable report.")

# File uploader (allow multiple files)
uploaded_files = st.file_uploader("Choose files", type=["xls", "xlsx", "csv"], accept_multiple_files=True, help="Upload one or more tab-separated files with the same structure.")

if uploaded_files:
    try:
        # Load and concatenate multiple files
        dfs = []
        expected_columns = ['Date', 'Amount', 'Commission', 'Vat', 'Vid', 'Channel Type']
        for file in uploaded_files:
            df_temp = pd.read_csv(file, sep='\t', skiprows=1, header=0)
            # Validate columns
            if not all(col in df_temp.columns for col in expected_columns):
                st.error(f"File {file.name} does not have the expected columns: {', '.join(expected_columns)}")
                st.stop()
            dfs.append(df_temp)
        
        # Combine all files into a single DataFrame
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
        else:
            st.error("No valid data loaded from the uploaded files.")
            st.stop()
        
        # Data cleaning
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        numeric_cols = ['Amount', 'Commission', 'Vat', 'Vid', 'Running Balance']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        if 'Code' in df.columns:
            df['Code'] = df['Code'].astype(str).str.strip("'")
        
        # Add date_only for grouping
        df['Date_only'] = df['Date'].dt.date
        
        # Sidebar for filters
        st.sidebar.header("🔧 Filters & Mappings")
        
        # Channel Type filter (applies only to charts and report)
        channel_types = df['Channel Type'].dropna().unique().tolist()
        selected_channels = st.sidebar.multiselect(
            "Filter by Channel Type (Charts & Report Only)",
            options=channel_types,
            default=channel_types,
            help="Select channel types to filter charts and the downloadable report. Metrics are unaffected."
        )
        
        # Vid filter (applies to metrics, charts, and report)
        vids = sorted(df['Vid'].dropna().unique())
        selected_vids = st.sidebar.multiselect(
            "Filter by Vendor ID (Vid)",
            options=vids,
            default=vids,
            help="Select Vendor IDs to filter all data (metrics, charts, and report)."
        )
        
        # Vendor Mapping input
        mapping_input = st.sidebar.text_area(
            "Vendor ID Mapping (JSON format, e.g., {\"254499\": \"Vendlite\"})",
            value='{"254499": "Vendlite"}',
            height=100,
            help="Enter mappings as JSON. Example: {\"254499\": \"Vendlite\", \"254754\": \"VendorX\"}. Unmapped Vids will show numeric."
        )
        
        # Apply Vendor ID filter for metrics
        metrics_df = df[df['Vid'].isin(selected_vids) if selected_vids else True].copy()
        
        # Apply both filters for charts and report
        filtered_df = metrics_df[metrics_df['Channel Type'].isin(selected_channels)].copy()
        
        # Parse vendor mapping
        try:
            vendor_map = eval(mapping_input) if mapping_input.strip() else {}
            metrics_df['Vendor Name'] = metrics_df['Vid'].map(vendor_map).fillna(metrics_df['Vid'].astype(str))
            filtered_df['Vendor Name'] = filtered_df['Vid'].map(vendor_map).fillna(filtered_df['Vid'].astype(str))
        except Exception as e:
            st.sidebar.error(f"Invalid mapping format: {e}. Using default mapping (254499: Vendlite).")
            vendor_map = {254499: 'Vendlite'}
            metrics_df['Vendor Name'] = metrics_df['Vid'].map(vendor_map).fillna(metrics_df['Vid'].astype(str))
            filtered_df['Vendor Name'] = filtered_df['Vid'].map(vendor_map).fillna(filtered_df['Vid'].astype(str))
        
        # C2B filtered for transaction counts (metrics and charts)
        c2b_metrics = metrics_df[metrics_df['Channel Type'] == 'C2B'].copy()
        c2b_filtered = filtered_df[filtered_df['Channel Type'] == 'C2B'].copy()
        
        # Calculate metrics (using metrics_df, unaffected by Channel Type filter)
        total_revenue = c2b_metrics['Amount'].sum()
        total_refunds = abs(metrics_df[metrics_df['Channel Type'] == 'REFUND']['Amount'].sum())
        bank_transfer_charges = 50.0 * len(dfs)  # Fixed per file
        vat_bank_transfer = bank_transfer_charges * 0.16  # 16% VAT
        nayax_commission = c2b_metrics['Amount'].sum() * 0.01  # 1% of C2B amounts
        bck_commission = c2b_metrics['Amount'].sum() * 0.005  # 0.5% of C2B amounts
        ipay_commission = metrics_df['Commission'].sum()  # Ipay Commissions
        total_vat = metrics_df['Vat'].sum()
        amount_to_remit = total_revenue - (
            total_refunds + ipay_commission + bank_transfer_charges + 
            vat_bank_transfer + nayax_commission + bck_commission + total_vat
        )
        
        # Metrics container (canvas, split into two rows, unaffected by Channel Type filter)
        st.subheader("📊 Key Metrics")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Revenue (KES)", f"{total_revenue:.2f}")
        with col2:
            if len(metrics_df['Date_only'].unique()) > 0:
                daily_rev = metrics_df.groupby('Date_only')['Amount'].sum()
                avg_daily = daily_rev.mean()
                st.metric("Avg Daily Revenue (KES)", f"{avg_daily:.2f}")
            else:
                st.metric("Avg Daily Revenue (KES)", "0.00")
        with col3:
            total_trans = len(c2b_metrics)
            st.metric("Total C2B Transactions", total_trans)
        with col4:
            st.metric("Ipay Commissions (KES)", f"{ipay_commission:.2f}")
        with col5:
            st.metric("Total VAT (KES)", f"{total_vat:.2f}")
        
        # Second row for new metrics
        col6, col7, col8, col9, col10 = st.columns(5)
        
        with col6:
            st.metric("Total Refunds (KES)", f"{total_refunds:.2f}")
        with col7:
            st.metric("Bank Transfer Charges (KES)", f"{bank_transfer_charges:.2f}")
        with col8:
            st.metric("VAT on Bank Transfer (KES)", f"{vat_bank_transfer:.2f}")
        with col9:
            st.metric("Nayax Commission (KES)", f"{nayax_commission:.2f}")
        with col10:
            st.metric("BCK Commission (KES)", f"{bck_commission:.2f}")
        
        # Amount to Remit
        st.subheader("💰 Amount to be Remitted")
        st.metric("Amount to be Remitted (KES)", f"{amount_to_remit:.2f}", delta=None)
        
        # Downloadable report (CSV or Excel, affected by both filters)
        st.subheader("📄 Download Financial Report")
        # Prepare report data (using filtered_df for consistency with charts)
        date_range = f"{filtered_df['Date_only'].min()} to {filtered_df['Date_only'].max()}" if not filtered_df.empty else "N/A"
        uploaded_files_str = ", ".join([file.name for file in uploaded_files])
        filters_applied = f"Channel Types: {', '.join(selected_channels) if selected_channels else 'All'}, Vendor IDs: {', '.join(map(str, selected_vids)) if selected_vids else 'All'}"
        
        # Recalculate metrics for report to reflect Channel Type filter
        report_total_revenue = c2b_filtered['Amount'].sum()
        report_total_refunds = abs(filtered_df[filtered_df['Channel Type'] == 'REFUND']['Amount'].sum())
        report_bank_transfer_charges = 50.0 * len(dfs) if 'BANKCOST' in filtered_df['Channel Type'].values else 0.0
        report_vat_bank_transfer = report_bank_transfer_charges * 0.16
        report_nayax_commission = c2b_filtered['Amount'].sum() * 0.01
        report_bck_commission = c2b_filtered['Amount'].sum() * 0.005
        report_ipay_commission = filtered_df['Commission'].sum()
        report_total_vat = filtered_df['Vat'].sum()
        report_amount_to_remit = report_total_revenue - (
            report_total_refunds + report_ipay_commission + report_bank_transfer_charges + 
            report_vat_bank_transfer + report_nayax_commission + report_bck_commission + report_total_vat
        )
        
        report_data = {
            'Metric': [
                'Generated On',
                'Uploaded Files',
                'Date Range',
                'Filters Applied',
                'Total Revenue',
                'Total Refunds',
                'Ipay Commissions',
                'Bank Transfer Charges',
                'VAT on Bank Transfer (16%)',
                'Nayax Commission (1% of C2B)',
                'BCK Commission (0.5% of C2B)',
                'Total VAT',
                'Amount to be Remitted'
            ],
            'Amount (KES)': [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                uploaded_files_str,
                date_range,
                filters_applied,
                f"{report_total_revenue:.2f}",
                f"{report_total_refunds:.2f}",
                f"{report_ipay_commission:.2f}",
                f"{report_bank_transfer_charges:.2f}",
                f"{report_vat_bank_transfer:.2f}",
                f"{report_nayax_commission:.2f}",
                f"{report_bck_commission:.2f}",
                f"{report_total_vat:.2f}",
                f"{report_amount_to_remit:.2f}"
            ]
        }
        report_df = pd.DataFrame(report_data)
        
        # Format selection and download button
        report_format = st.selectbox("Select report format", ["CSV", "Excel"])
        
        if report_format == "CSV":
            csv = report_df.to_csv(index=False)
            st.download_button(
                label="Download Financial Report as CSV",
                data=csv,
                file_name="sales_financial_report.csv",
                mime="text/csv"
            )
        else:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                report_df.to_excel(writer, index=False, sheet_name='Financial Report')
            st.download_button(
                label="Download Financial Report as Excel",
                data=excel_buffer.getvalue(),
                file_name="sales_financial_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Cumulative line chart (affected by both filters)
        st.subheader("📈 Cumulative Revenue Over Time")
        if len(filtered_df) > 0:
            daily_revenue = filtered_df.groupby('Date_only')['Amount'].sum().reset_index()
            daily_revenue['Date_only'] = pd.to_datetime(daily_revenue['Date_only'])
            daily_revenue = daily_revenue.sort_values('Date_only')
            daily_revenue['Cumulative'] = daily_revenue['Amount'].cumsum()
            
            fig_cum = px.line(daily_revenue, x='Date_only', y='Cumulative', 
                            title="Cumulative Revenue Trend",
                            markers=True)
            fig_cum.update_layout(
                xaxis_title="Date",
                yaxis_title="Cumulative Revenue (KES)",
                template="plotly_white",
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(family="Poppins, sans-serif", color="#1A2B5F")
            )
            st.plotly_chart(fig_cum, use_container_width=True)
        else:
            st.info("No data available after applying filters. Adjust filters to view charts.")
        
        # Additional charts (affected by both filters)
        st.subheader("📊 Further Insights")
        col_a, col_b = st.columns(2)
        
        with col_a:
            # Daily Revenue Bar
            if len(daily_revenue) > 0:
                fig_daily = px.bar(daily_revenue, x='Date_only', y='Amount',
                                title="Daily Revenue",
                                color='Amount',
                                color_continuous_scale='Blues')
                fig_daily.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Daily Revenue (KES)",
                    template="plotly_white",
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    font=dict(family="Poppins, sans-serif", color="#1A2B5F")
                )
                st.plotly_chart(fig_daily, use_container_width=True)
        
        with col_b:
            # Vendor Breakdown Pie
            if 'Vendor Name' in filtered_df.columns and len(c2b_filtered) > 0:
                vendor_rev = c2b_filtered.groupby('Vendor Name')['Amount'].sum().reset_index()
                fig_pie = px.pie(vendor_rev, values='Amount', names='Vendor Name',
                                title="Revenue by Vendor (C2B Only)",
                                color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(
                    template="plotly_white",
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    font=dict(family="Poppins, sans-serif", color="#1A2B5F")
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # Raw data and download option (affected by both filters)
        with st.expander("📋 View Filtered Data"):
            st.dataframe(filtered_df, use_container_width=True)
            
            # Download filtered data as CSV
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Download Filtered Data as CSV",
                data=csv,
                file_name="filtered_sales_data.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"Error loading files: {e}. Ensure all files are valid tab-separated files with the same structure.")
        st.markdown("""
            **Troubleshooting Tips**:
            - Verify all files are tab-separated (open in a text editor to check for tabs).
            - Ensure all files have the same columns: Date, Amount, Commission, Vat, Vid, Channel Type.
            - If any file is an Excel file, save it as `.xlsx` and modify the code to use `pd.read_excel` with `engine='openpyxl'`.
            - Check for file corruption by opening in a text editor or Excel.
            - If issues persist, contact support with the error details.
        """)
else:
    st.info("👆 Please upload one or more tab-separated `.xls`, `.xlsx`, or `.csv` files to begin analysis.")

# Footer
st.markdown("---")
st.markdown("*Built with Streamlit & Plotly | Powered by pandas & openpyxl*")