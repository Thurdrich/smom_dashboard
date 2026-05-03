import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import streamlit_authenticator as stauth
import os

# 1. Page Configuration
st.set_page_config(page_title="STRATEGIC MANPOWER OPTIMIZATION MODEL", layout="wide")

# 2. Authentication Setup (Updated for v0.3.0)
# This is the "Dictionary" format the error was complaining about
credentials = {
    "usernames": {
        "admin": {
            "name": "Admin User",
            "password": "Leianna1812$*" # In a real app, we'd hash this, but this works for now
        },
        "Latiimer_SMOM": {
            "name": "Latiimer SMOM",
            "password": "hcoteam#1"
        }
    }
}

# The library now handles the hashing internally if we set it up like this
authenticator = stauth.Authenticate(
    credentials,
    "manpower_dashboard",
    "signature_key_2026",
    cookie_expiry_days=1
)

# 3. Render Login
# We use st.session_state to track if you're logged in
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    # SUCCESS: Show the dashboard
    authenticator.logout('Logout', 'sidebar')
    st.title("SMOM Dashboard")
    st.sidebar.success(f"Welcome {st.session_state['name']}")

    # --- DATA LOADING ---
    try:
        # This part finds your CSV file automatically
        base_path = os.path.dirname(__file__)
        csv_path = os.path.join(base_path, 'clean_mcs.csv')
        df = pd.read_csv(csv_path)
        
        # --- FILTERS ---
        st.sidebar.header("Filter Options")
        bso_filter = st.sidebar.multiselect("Select BSO:", options=df['BSO'].unique(), default=df['BSO'].unique())
        type_filter = st.sidebar.multiselect("Personnel Type:", options=df['Personnel_Type'].unique(), default=df['Personnel_Type'].unique())

        df_filtered = df[(df['BSO'].isin(bso_filter)) & (df['Personnel_Type'].isin(type_filter))]

        # --- KEY METRICS ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total BA", f"{df_filtered['BA'].sum():,}")
        with col2:
            st.metric("Total Onboard", f"{df_filtered['Onboard'].sum():,}")
        with col3:
            st.metric("Overall Gap", f"{df_filtered['Gap'].sum():,}")

        # --- CHARTS ---
        st.divider()
        
        # Chart: Gap by BSO
        fig_bso = px.bar(df_filtered.groupby('BSO')['Gap'].sum().reset_index(), 
                         x='BSO', y='Gap', title="Manpower Gap by BSO",
                         color_discrete_sequence=['#001f3f']) # Navy Blue
        st.plotly_chart(fig_bso, use_container_width=True)

        # Chart: Criticality vs Gap
        fig_scatter = px.scatter(df_filtered, x='Model_Criticality_Score', y='Gap', 
                                 color='Personnel_Type', title="Criticality vs. Gap Size",
                                 hover_data=['Job_Specialty'])
        st.plotly_chart(fig_scatter, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading data: {e}. Please ensure 'clean_mcs.csv' is in the same folder as this script.")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
