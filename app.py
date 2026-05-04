import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from sklearn.linear_model import LinearRegression

# Page Config
st.set_page_config(page_title="SMOM Executive Dashboard", layout="wide")

@st.cache_data
def load_data():
    file_path = 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv'
    if not os.path.exists(file_path): return None
    df = pd.read_csv(file_path)
    cost_map = {
        'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 
        'E7': 120000, 'E8': 140000, 'E9': 160000, 'GS-07': 70000, 'GS-09': 85000, 
        'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
    }
    if 'Pay_Grade_Level' in df.columns: 
        df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)
    df.dropna(subset=['Cost_per_Billet'], inplace=True)
    if 'Gap' in df.columns: 
        df['Gap_Size'] = df['Gap'].abs()
    return df

df = load_data()

if df is not None:
    st.title("Strategic Manpower Optimization Module (SMOM) Dashboard")
    
    # Sidebar Filters
    st.sidebar.header("Dashboard Filters")
    p_types = ['All'] + sorted(df['Personnel_Type'].unique().tolist())
    sel_p = st.sidebar.selectbox("Personnel Category", p_types)
    
    dff = df if sel_p == 'All' else df[df['Personnel_Type'] == sel_p]

    # KPIs
    m1, m2, m3 = st.columns(3)
    m1.metric("Selected Billets", f"{len(dff):,}")
    m2.metric("Avg Criticality", f"{dff['Model_Criticality_Score'].mean():.2f}")
    m3.metric("Est. Portfolio Value", f"${(dff['Cost_per_Billet'].sum()/1e6):.1f}M")

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(px.scatter(dff, x='Cost_per_Billet', y='Model_Criticality_Score', size='Gap_Size', color='Personnel_Type', title="Cost vs Criticality"), use_container_width=True)
    with col2:
        avg_c = dff.groupby('BSO')['Cost_per_Billet'].mean().reset_index().sort_values('Cost_per_Billet', ascending=False)
        st.plotly_chart(px.bar(avg_c, x='BSO', y='Cost_per_Billet', title="Avg Cost by BSO"), use_container_width=True)
else:
    st.error("Data file not found. Ensure CSV is in the repository.")
