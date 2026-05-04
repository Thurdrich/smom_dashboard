import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit_authenticator as stauth
import os

# 1. Page Configuration
st.set_page_config(page_title="STRATEGIC MANPOWER OPTIMIZATION MODEL", layout="wide")

# 2. Authentication Setup
credentials = {
    "usernames": {
        "admin": {
            "name": "Admin User",
            "password": "Leianna1812$*"
        },
        "Latiimer_SMOM": {
            "name": "Latiimer SMOM",
            "password": "hcoteam#1"
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "manpower_dashboard",
    "signature_key_2026",
    cookie_expiry_days=1
)

# 3. Render Login
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    # SUCCESS: Show the dashboard
    authenticator.logout('Logout', 'sidebar')
    st.title("SMOM Dashboard")
    st.sidebar.success(f"Welcome {st.session_state['name']}")

    # --- DATA LOADING ---
    try:
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

        st.divider()

        # --- 5 CHARTS/GRAPHS ---
        
        # Chart 1: BA vs Onboard Comparison
        st.subheader("Chart 1: BA vs Onboard by BSO")
        df_chart1 = df_filtered.groupby('BSO')[['BA', 'Onboard']].sum().reset_index()
        fig1 = px.bar(df_chart1, x='BSO', y=['BA', 'Onboard'], barmode='group', 
                      title='BA vs Onboard Count by BSO')
        st.plotly_chart(fig1, use_container_width=True)

        # Chart 2: Gap Distribution (Histogram)
        st.subheader("Chart 2: Gap Distribution")
        fig2 = px.histogram(df_filtered, x='Gap', nbins=20, title='Distribution of Gaps',
                           labels={'Gap': 'Gap Size'})
        st.plotly_chart(fig2, use_container_width=True)

        # Chart 3: Personnel Type Breakdown (Pie Chart)
        st.subheader("Chart 3: Personnel Type Breakdown")
        df_chart3 = df_filtered.groupby('Personnel_Type')[['BA']].sum().reset_index()
        fig3 = px.pie(df_chart3, values='BA', names='Personnel_Type', 
                      title='BA Distribution by Personnel Type')
        st.plotly_chart(fig3, use_container_width=True)

        # Chart 4: BSO Comparison (Scatter Plot)
        st.subheader("Chart 4: Onboard vs BA by BSO")
        fig4 = px.scatter(df_filtered, x='BA', y='Onboard', color='BSO', size='Gap',
                         title='Onboard vs BA (bubble size = Gap)',
                         labels={'BA': 'Authorized Amount', 'Onboard': 'Current Onboard'})
        st.plotly_chart(fig4, use_container_width=True)

        # Chart 5: Gap by Personnel Type (Box Plot)
        st.subheader("Chart 5: Gap Analysis by Personnel Type")
        fig5 = px.box(df_filtered, x='Personnel_Type', y='Gap', color='Personnel_Type',
                      title='Gap Distribution by Personnel Type')
        st.plotly_chart(fig5, use_container_width=True)

        st.divider()

        # Data table
        st.header('Detailed Data Table')
        st.dataframe(df_filtered, use_container_width=True)
        
    except FileNotFoundError:
        st.error("Error: CSV file 'clean_mcs.csv' not found. Please ensure the file is in the correct location.")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

elif st.session_state["authentication_status"] is False:
    st.error("Invalid username or password")
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your credentials")