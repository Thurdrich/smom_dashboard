import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# Page Configuration
st.set_page_config(page_title="SMOM Executive Summary", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #dee2e6; }
    h1, h2, h3 { color: #00205b; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_data():
    file_path = 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv.xlsx'
    if not os.path.exists(file_path): return None
    df = pd.read_excel(file_path)
    cost_map = {
        'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
        'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
    }
    if 'Pay_Grade_Level' in df.columns: df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)
    df.dropna(subset=['Cost_per_Billet'], inplace=True)
    if 'Gap' in df.columns: df['Gap_Size'] = df['Gap'].abs()
    return df

df = load_data()

if df is not None:
    st.sidebar.title("SMOM Controls")
    mode = st.sidebar.radio("View Mode", ["Executive Dashboard", "Mil vs Civ Comparison"])

    if mode == "Mil vs Civ Comparison":
        st.title("Military vs. Civilian Strategic Summary")
        mil_df = df[df['Personnel_Type'] == 'Military']
        civ_df = df[df['Personnel_Type'] == 'Civilian']

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🎖️ Military Personnel")
            m_c1, m_c2 = st.columns(2)
            m_c1.metric("Avg Criticality", f"{mil_df['Model_Criticality_Score'].mean():.1f}")
            m_c2.metric("Total Cost Est.", f"${(mil_df['Cost_per_Billet'].sum()/1e6):.1f}M")
            st.plotly_chart(px.box(mil_df, x='BSO', y='Model_Criticality_Score', title="Mil Criticality by BSO", color_discrete_sequence=['#00205b']), use_container_width=True)

        with col2:
            st.subheader("💼 Civilian Personnel")
            c_c1, c_c2 = st.columns(2)
            c_c1.metric("Avg Criticality", f"{civ_df['Model_Criticality_Score'].mean():.1f}")
            c_c2.metric("Total Cost Est.", f"${(civ_df['Cost_per_Billet'].sum()/1e6):.1f}M")
            st.plotly_chart(px.box(civ_df, x='BSO', y='Model_Criticality_Score', title="Civ Criticality by BSO", color_discrete_sequence=['#ff9900']), use_container_width=True)

    else:
        st.title("SMOM Integrated Executive Dashboard")
        p_type = st.sidebar.multiselect("Personnel", options=df['Personnel_Type'].unique(), default=df['Personnel_Type'].unique())
        bso_sel = st.sidebar.multiselect("BSO", options=sorted(df['BSO'].unique()), default=sorted(df['BSO'].unique())[:4])
        dff = df[(df['Personnel_Type'].isin(p_type)) & (df['BSO'].isin(bso_sel))]

        m1, m2, m3 = st.columns(3)
        m1.metric("Selected Billets", f"{len(dff):,}")
        m2.metric("Avg Criticality", f"{dff['Model_Criticality_Score'].mean():.2f}")
        m3.metric("Est. Portfolio Value", f"${(dff['Cost_per_Billet'].sum()/1e6):.1f}M")

        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.scatter(dff, x='Cost_per_Billet', y='Model_Criticality_Score', size='Gap_Size', color='Personnel_Type', title="Cost vs Criticality Map"), use_container_width=True)
        with c2:
            avg_c = dff.groupby('BSO')['Cost_per_Billet'].mean().reset_index().sort_values('Cost_per_Billet', ascending=False)
            st.plotly_chart(px.bar(avg_c, x='BSO', y='Cost_per_Billet', title="Average Cost per Billet by BSO"), use_container_width=True)
else:
    st.error("Data file missing in GitHub repository.")
