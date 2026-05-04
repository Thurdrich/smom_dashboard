import streamlit as st
import pandas as pd
import plotly.express as px

# Streamlit page configuration
st.set_page_config(page_title="DON/MSC Dashboard", layout="wide", initial_sidebar_state="expanded")

# Add custom CSS for styling
st.markdown("""
<style>
    .main { background-color: #f4f4f9; }
    h1 { color: #00205b; text-align: center; }
    .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# Title and sidebar
st.title("🎖️ DON/MSC Interactive Manpower & Financial Dashboard")

with st.sidebar:
    st.header("Dashboard Controls")
    st.markdown("---")
    refresh_data = st.button("🔄 Refresh Data", use_container_width=True)
    export_html = st.button("📥 Export as HTML", use_container_width=True)
    st.markdown("---")
    st.info("📊 Dashboard updated: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))

# Load the data
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv')
        return df
    except FileNotFoundError:
        st.error("❌ Data file not found. Please ensure 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv' is in the working directory.")
        st.stop()

df = load_data()

# Add Cost Data (Data Enrichment)
cost_map = {
    'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
    'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
}
df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)
df.dropna(subset=['Cost_per_Billet'], inplace=True)

# Calculate financial impact
df['Gap_Cost'] = df['Gap'] * df['Cost_per_Billet']
df['Gap_Size'] = df['Gap'].abs()

# Key Metrics Row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Manpower Gaps", f"{int(df['Gap'].sum()):,}")
with col2:
    st.metric("Total Financial Impact", f"${df['Gap_Cost'].sum():,.0f}")
with col3:
    st.metric("Avg Criticality Score", f"{df['Model_Criticality_Score'].mean():.2f}")
with col4:
    st.metric("Records Analyzed", f"{len(df):,}")

st.markdown("---")

# Create the 4 Interactive Plots
st.subheader("📈 Manpower Gap Analysis")

col1, col2 = st.columns(2)

with col1:
    # Chart 1: Gaps by BSO
    bso_gaps = df.groupby('BSO')['Gap'].sum().reset_index().sort_values('Gap', ascending=False)
    fig1 = px.bar(bso_gaps, x='BSO', y='Gap', color='Gap', color_continuous_scale='viridis', 
                  title="Total Manpower Gaps by BSO", labels={'Gap': 'Manpower Gap'})
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    # Chart 2: Gaps by Platform
    plat_gaps = df.groupby('Platform')['Gap'].sum().reset_index().sort_values('Gap', ascending=False)
    fig2 = px.bar(plat_gaps, x='Platform', y='Gap', color='Gap', color_continuous_scale='plasma', 
                  title="Total Manpower Gaps by Platform", labels={'Gap': 'Manpower Gap'})
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("💰 Cost & Criticality Analysis")

col3, col4 = st.columns(2)

with col3:
    # Chart 3: Cost vs Criticality Scatter Plot
    fig3 = px.scatter(
        df, x='Cost_per_Billet', y='Model_Criticality_Score', color='Personnel_Type', size='Gap_Size',
        hover_data=['BSO', 'Platform', 'Job_Specialty', 'Pay_Grade_Level'],
        color_discrete_map={'Military': 'navy', 'Civilian': 'orange'},
        title="Cost vs. Criticality Score", labels={'Cost_per_Billet': 'Cost per Billet', 'Model_Criticality_Score': 'Criticality Score'}
    )
    fig3.update_layout(xaxis_tickformat='$,.0f')
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    # Chart 4: Financial Impact by BSO
    fin_bso = df.groupby('BSO')['Gap_Cost'].sum().reset_index().sort_values('Gap_Cost', ascending=False)
    fig4 = px.bar(fin_bso, x='BSO', y='Gap_Cost', color='Gap_Cost', color_continuous_scale='cividis', 
                  title="Estimated Financial Impact by BSO", labels={'Gap_Cost': 'Financial Impact ($)'})
    fig4.update_layout(yaxis_tickformat='$,.0f')
    st.plotly_chart(fig4, use_container_width=True)

# Data Table Section
st.subheader("📋 Detailed Data View")
with st.expander("View Raw Data"):
    st.dataframe(df, use_container_width=True)

# Export functionality
if export_html:
    html_template = f"""
    <html>
    <head>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; color: #00205b; }}
            .dashboard {{ display: flex; flex-wrap: wrap; justify-content: center; }}
            .chart-container {{ width: 48%; min-width: 500px; background: white; margin: 10px; padding: 10px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <h1>DON/MSC Interactive Manpower & Financial Dashboard</h1>
        <div class="dashboard">
            <div class="chart-container">{fig1.to_html(full_html=False, include_plotlyjs=False)}</div>
            <div class="chart-container">{fig2.to_html(full_html=False, include_plotlyjs=False)}</div>
            <div class="chart-container">{fig3.to_html(full_html=False, include_plotlyjs=False)}</div>
            <div class="chart-container">{fig4.to_html(full_html=False, include_plotlyjs=False)}</div>
        </div>
    </body>
    </html>
    """
    
    st.download_button(
        label="📥 Download Dashboard HTML",
        data=html_template,
        file_name="DON_MSC_Complete_Interactive_Dashboard.html",
        mime="text/html"
    )
    st.success("✅ Dashboard export ready!")
