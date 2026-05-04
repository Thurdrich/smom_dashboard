import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from sklearn.linear_model import LinearRegression

# Page Config for Professional Dashboard Look
st.set_page_config(page_title="Strategic Manpower Optimization Module Dashboard", layout="wide")

@st.cache_data
def load_and_clean_data():
    # Target the specific CSV file used in your dataset
    file_path = 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv'
    if not os.path.exists(file_path):
        return None

    # Load and Enrich Data
    df = pd.read_csv(file_path)
    cost_map = {
        'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
        'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
    }

    if 'Pay_Grade_Level' in df.columns:
        df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)

    df.dropna(subset=['Cost_per_Billet'], inplace=True)

    if 'Gap' in df.columns:
        df['Gap_Size'] = df['Gap'].abs()

    return df

df = load_and_clean_data()

if df is not None:
    st.title("Strategic Manpower Optimization Module Dashboard")
    st.markdown("--- ")

    # Sidebar Filters
    st.sidebar.header("Dashboard Filters")

    # Personnel Type Filter
    personnel_types = ['All'] + sorted(df['Personnel_Type'].unique().tolist())
    selected_personnel = st.sidebar.selectbox("Select Personnel Category", personnel_types)

    # Platform Filter
    platform_types = ['All'] + sorted(df['Platform'].unique().tolist())
    selected_platform = st.sidebar.selectbox("Select Platform", platform_types)

    # BSO Filter
    bso_types = ['All'] + sorted(df['BSO'].unique().tolist())
    selected_bso = st.sidebar.selectbox("Select BSO", bso_types)

    # Budget Range Filter
    min_cost, max_cost = int(df['Cost_per_Billet'].min()), int(df['Cost_per_Billet'].max())
    cost_range = st.sidebar.slider(
        "Select Cost per Billet Range ($)",
        min_value=min_cost,
        max_value=max_cost,
        value=(min_cost, max_cost)
    )

    # Criticality Score Range Filter
    min_crit, max_crit = int(df['Model_Criticality_Score'].min()), int(df['Model_Criticality_Score'].max())
    criticality_range = st.sidebar.slider(
        "Select Model Criticality Score Range",
        min_value=min_crit,
        max_value=max_crit,
        value=(min_crit, max_crit)
    )

    # Filter Dataset based on all selections
    dff = df.copy()
    if selected_personnel != 'All':
        dff = dff[dff['Personnel_Type'] == selected_personnel]
    if selected_platform != 'All':
        dff = dff[dff['Platform'] == selected_platform]
    if selected_bso != 'All':
        dff = dff[dff['BSO'] == selected_bso]

    dff = dff[(dff['Cost_per_Billet'] >= cost_range[0]) & (dff['Cost_per_Billet'] <= cost_range[1])]
    dff = dff[(dff['Model_Criticality_Score'] >= criticality_range[0]) & (dff['Model_Criticality_Score'] <= criticality_range[1])]

    # Row 1: Primary Metrics
    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.scatter(dff, x='Cost_per_Billet', y='Model_Criticality_Score', color='Personnel_Type',
                          size='Gap_Size', hover_data=['BSO', 'Job_Specialty'],
                          title="Cost vs. Criticality Score (Bubble Size = Gap)")
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        avg_cost = dff.groupby('BSO')['Cost_per_Billet'].mean().reset_index().sort_values('Cost_per_Billet', ascending=False)
        fig2 = px.bar(avg_cost, x='BSO', y='Cost_per_Billet', title="Average Cost per Billet by BSO", color='BSO')
        st.plotly_chart(fig2, use_container_width=True)

    # Row 2: Regression and Variance
    col3, col4 = st.columns(2)
    with col3:
        fig3 = px.scatter(dff, x='Gap_Size', y='Model_Criticality_Score', trendline="ols",
                          title="Personnel Gap vs. Criticality (Regression Analysis)")
        st.plotly_chart(fig3, use_container_width=True)
    with col4:
        fig4 = px.box(dff, x='BSO', y='Cost_per_Billet', color='BSO', title="Cost Variance Analysis by BSO")
        st.plotly_chart(fig4, use_container_width=True)

    # Row 3: Specialty Analysis
    col5, col6 = st.columns(2)
    with col5:
        spec_data = dff.groupby('Job_Specialty')['Model_Criticality_Score'].mean().reset_index().sort_values('Model_Criticality_Score', ascending=False).head(15)
        fig5 = px.bar(spec_data, x='Job_Specialty', y='Model_Criticality_Score', title="Top 15 Most Critical Job Specialties")
        st.plotly_chart(fig5, use_container_width=True)
    with col6:
        heat = dff.groupby(['BSO', 'Job_Specialty'])['Model_Criticality_Score'].mean().reset_index()
        fig6 = go.Figure(data=go.Heatmap(z=heat['Model_Criticality_Score'], x=heat['BSO'], y=heat['Job_Specialty'], colorscale='Viridis'))
        fig6.update_layout(title="Criticality Density Heatmap (BSO vs Specialty)")
        st.plotly_chart(fig6, use_container_width=True)

    # Export Feature
    csv = dff.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Filtered Data (CSV)", data=csv,
                               file_name=f'filtered_data_{selected_personnel.lower()}_{selected_platform.lower()}_{selected_bso.lower()}.csv', mime='text/csv')
else:
    st.error("Error: 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv' not found. Please upload the data file.")
