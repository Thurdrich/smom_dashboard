import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from sklearn.linear_model import LinearRegression

# Page Config for Professional Dashboard Look
st.set_page_config(page_title="Strategic Manpower Optimization Module", layout="wide")

@st.cache_data
def load_and_clean_data():
    # Prefer the newly attached Epic Fury dataset while keeping the legacy filenames available.
    file_names = [
        'MSC Epic Fury Movement Tracker_N1.xlsx',
        'MSC Epic Fury Movement Tracker_N1.csv',
        'Epic Fury Data',
        'clean_mcs.csv',
        'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv'
    ]

    file_path = next((name for name in file_names if os.path.exists(name)), None)
    if file_path is None:
        return None

    if file_path.lower().endswith('.xlsx'):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    # Legacy dashboard compatibility: compute a small set of fields used by the charts.
    if 'Pay_Grade_Level' in df.columns:
        cost_map = {
            'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
            'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
        }
        df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)

    if 'Cost_per_Billet' in df.columns:
        df = df.dropna(subset=['Cost_per_Billet'])

    if 'Gap' in df.columns:
        df['Gap_Size'] = df['Gap'].abs()

    return df

df = load_and_clean_data()

if df is not None:
    st.title("Strategic Manpower Optimization Module Dashboard")
    st.markdown("--- ")

    st.sidebar.header("Dashboard Filters")

    if 'Personnel_Type' in df.columns:
        personnel_types = ['All'] + sorted(df['Personnel_Type'].dropna().unique().tolist())
        selected_personnel = st.sidebar.selectbox("Select Personnel Category", personnel_types)
    else:
        selected_personnel = 'All'

    if 'Platform' in df.columns:
        platform_types = ['All'] + sorted(df['Platform'].dropna().unique().tolist())
        selected_platform = st.sidebar.selectbox("Select Platform", platform_types)
    else:
        selected_platform = 'All'

    if 'BSO' in df.columns:
        bso_types = ['All'] + sorted(df['BSO'].dropna().unique().tolist())
        selected_bso = st.sidebar.selectbox("Select BSO", bso_types)
    else:
        selected_bso = 'All'

    if 'Cost_per_Billet' in df.columns:
        min_cost, max_cost = int(df['Cost_per_Billet'].min()), int(df['Cost_per_Billet'].max())
        cost_range = st.sidebar.slider(
            "Select Cost per Billet Range ($)",
            min_value=min_cost,
            max_value=max_cost,
            value=(min_cost, max_cost)
        )
    else:
        cost_range = (0, 0)

    if 'Model_Criticality_Score' in df.columns:
        min_crit, max_crit = int(df['Model_Criticality_Score'].min()), int(df['Model_Criticality_Score'].max())
        criticality_range = st.sidebar.slider(
            "Select Model Criticality Score Range",
            min_value=min_crit,
            max_value=max_crit,
            value=(min_crit, max_crit)
        )
    else:
        criticality_range = (0, 0)

    dff = df.copy()
    if selected_personnel != 'All' and 'Personnel_Type' in dff.columns:
        dff = dff[dff['Personnel_Type'] == selected_personnel]
    if selected_platform != 'All' and 'Platform' in dff.columns:
        dff = dff[dff['Platform'] == selected_platform]
    if selected_bso != 'All' and 'BSO' in dff.columns:
        dff = dff[dff['BSO'] == selected_bso]

    if 'Cost_per_Billet' in dff.columns:
        dff = dff[(dff['Cost_per_Billet'] >= cost_range[0]) & (dff['Cost_per_Billet'] <= cost_range[1])]
    if 'Model_Criticality_Score' in dff.columns:
        dff = dff[(dff['Model_Criticality_Score'] >= criticality_range[0]) & (dff['Model_Criticality_Score'] <= criticality_range[1])]

    col1, col2 = st.columns(2)
    with col1:
        if {'Cost_per_Billet', 'Model_Criticality_Score'}.issubset(dff.columns):
            fig1 = px.scatter(dff, x='Cost_per_Billet', y='Model_Criticality_Score', color='Personnel_Type' if 'Personnel_Type' in dff.columns else None,
                              size='Gap_Size' if 'Gap_Size' in dff.columns else None, hover_data=['BSO', 'Job_Specialty'] if {'BSO', 'Job_Specialty'}.issubset(dff.columns) else None,
                              title="Cost vs. Criticality Score")
            st.plotly_chart(fig1, use_container_width=True)
    with col2:
        if 'BSO' in dff.columns and 'Cost_per_Billet' in dff.columns:
            avg_cost = dff.groupby('BSO')['Cost_per_Billet'].mean().reset_index().sort_values('Cost_per_Billet', ascending=False)
            fig2 = px.bar(avg_cost, x='BSO', y='Cost_per_Billet', title="Average Cost per Billet by BSO", color='BSO')
            st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        if {'Gap_Size', 'Model_Criticality_Score'}.issubset(dff.columns):
            fig3 = px.scatter(dff, x='Gap_Size', y='Model_Criticality_Score', trendline="ols",
                              title="Personnel Gap vs. Criticality (Regression Analysis)")
            st.plotly_chart(fig3, use_container_width=True)
    with col4:
        if 'BSO' in dff.columns and 'Cost_per_Billet' in dff.columns:
            fig4 = px.box(dff, x='BSO', y='Cost_per_Billet', color='BSO', title="Cost Variance Analysis by BSO")
            st.plotly_chart(fig4, use_container_width=True)

    col5, col6 = st.columns(2)
    with col5:
        if 'Job_Specialty' in dff.columns and 'Model_Criticality_Score' in dff.columns:
            spec_data = dff.groupby('Job_Specialty')['Model_Criticality_Score'].mean().reset_index().sort_values('Model_Criticality_Score', ascending=False).head(15)
            fig5 = px.bar(spec_data, x='Job_Specialty', y='Model_Criticality_Score', title="Most Critical Job Specialties")
            st.plotly_chart(fig5, use_container_width=True)
    with col6:
        if {'BSO', 'Job_Specialty', 'Model_Criticality_Score'}.issubset(dff.columns):
            heat = dff.groupby(['BSO', 'Job_Specialty'])['Model_Criticality_Score'].mean().reset_index()
            fig6 = go.Figure(data=go.Heatmap(z=heat['Model_Criticality_Score'], x=heat['BSO'], y=heat['Job_Specialty'], colorscale='Viridis'))
            fig6.update_layout(title="Criticality Density Heatmap (BSO vs Specialty)")
            st.plotly_chart(fig6, use_container_width=True)

    csv = dff.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Filtered Data (CSV)", data=csv,
                               file_name=f'filtered_data_{selected_personnel.lower()}_{selected_platform.lower()}_{selected_bso.lower()}.csv', mime='text/csv')
else:
    st.error("Error: no supported dataset file was found. Please add 'MSC Epic Fury Movement Tracker_N1.csv' or the legacy CSV file to this folder.")
