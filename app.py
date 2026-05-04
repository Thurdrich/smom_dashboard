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

        # Plot 4 - Box plot
        if 'metric5' in df.columns:
            fig4 = px.box(df, y='metric5', title='Boxplot of Metric 5')
            st.plotly_chart(fig4)
        else:
            st.warning("Column 'metric5' not found in data")

        # Data table
        st.header('Data Table')
        st.dataframe(df)
        
    except FileNotFoundError:
        st.error("Error: CSV file 'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv' not found. Please ensure the file is in the correct location.")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    main()