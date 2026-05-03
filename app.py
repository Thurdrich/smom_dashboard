import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import streamlit_authenticator as stauth

st.set_page_config(page_title="STRATEGIC MANPOWER OPTIMIZATION MODEL", layout="wide")

def safe_plotly_chart(fig):
    """
    Render Plotly charts safely through Streamlit. Some Plotly/Streamlit
    combinations can raise internal `trace.update(patch)` errors when
    rendering figures directly.
    """
    try:
        st.plotly_chart(fig, width='stretch')
    except Exception:
        fallback_fig = go.Figure(fig.to_dict() if hasattr(fig, "to_dict") else fig)
        st.plotly_chart(fallback_fig, width='stretch')

# Authentication
names = ['Admin User', 'Latiimer SMOM']
usernames = ['admin', 'Latiimer_SMOM']
passwords = ['Leianna1812$*', 'hcoteam#1']  # Change this to a strong password

hashed_passwords = stauth.Hasher(passwords).generate()

authenticator = stauth.Authenticate(names, usernames, hashed_passwords, 'manpower_dashboard', 'signature_key_2026', cookie_expiry_days=1)

name, authentication_status, username = authenticator.login('Login to Dashboard', 'main')

if authentication_status:
    authenticator.logout('Logout', 'sidebar')

    # 1. Page Configuration (Opens wide in Edge)
    st.title("Predictive Manpower Optimization Dashboard")
    st.markdown("Predictive analytics for manpower gaps, criticality, & budget optimization.")

    # Navy-style CSS
    st.markdown("""
    <style>
        .stApp {
            background-color: #001122;
            color: #ffffff;
        }
        .stTitle, .stHeader, .stSubheader {
            color: #ffffff;
        }
        .stSelectbox, .stTextInput {
            background-color: #003366;
            color: #ffffff;
        }
    </style>
    """, unsafe_allow_html=True)

    # 2. Load and Prep Data
    @st.cache_data
    def load_data():
        df = pd.read_csv('clean_mcs.csv')
        
        # Financial Mapping
        cost_map = {
            'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
            'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
        }
        df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)
        df.dropna(subset=['Cost_per_Billet'], inplace=True)
        df['Gap_Cost'] = df['Gap'] * df['Cost_per_Billet']
        
        return df

    df = load_data()
    bso_list = ['All Commands'] + sorted(list(df['BSO'].unique()))
    selected_bso = st.sidebar.selectbox("Filter by BSO:", bso_list)

    # Apply Filter
    if selected_bso != 'All Commands':
        df_filtered = df[df['BSO'] == selected_bso]
        st.subheader(f"Displaying Data for: {selected_bso}")
    else:
        df_filtered = df
        st.subheader("Displaying Data for: All Commands")

    # 4. Generate Interactive Plotly Charts
    col1, col2 = st.columns(2)

    with col1:
        # Chart A: Gaps by Platform
        sort_col_platform = st.selectbox("Sort Platform Gaps by:", ['Gap', 'Platform'], key='sort_platform')
        ascending_platform = st.selectbox("Order:", ['Descending', 'Ascending'], key='order_platform') == 'Ascending'
        platform_gaps = df_filtered.groupby('Platform')['Gap'].sum().reset_index().sort_values(by=sort_col_platform, ascending=ascending_platform)
        fig_platform = px.bar(platform_gaps, x='Platform', y='Gap', title="Total Manpower Gaps by Platform", color='Gap', color_continuous_scale='Blues', text='Gap')
        fig_platform.update_traces(textposition='outside')
        safe_plotly_chart(fig_platform)

        # Chart C: Financial Impact
        sort_col_fin = st.selectbox("Sort Financial Impact by:", ['Gap_Cost', 'Platform'], key='sort_fin')
        ascending_fin = st.selectbox("Order:", ['Descending', 'Ascending'], key='order_fin') == 'Ascending'
        fin_impact = df_filtered.groupby('Platform')['Gap_Cost'].sum().reset_index().sort_values(by=sort_col_fin, ascending=ascending_fin)
        fig_fin = px.bar(fin_impact, x='Platform', y='Gap_Cost', title="Financial Impact of Gaps by Platform", color='Gap_Cost', color_continuous_scale='Blues', text=fin_impact['Gap_Cost'].apply(lambda x: f'${x:,.0f}'))
        fig_fin.update_traces(textposition='outside')
        fig_fin.update_layout(yaxis_tickformat='$,.0f')
        safe_plotly_chart(fig_fin)

    with col2:
        # Chart B: Cost vs Criticality (The Surgical Haircut plot)
        try:
            fig_scatter = px.scatter(
                df_filtered, 
                x='Cost_per_Billet', 
                y='Model_Criticality_Score', 
                color='Personnel_Type', 
                size='Gap', 
                hover_data=['BSO', 'Platform', 'Job_Specialty', 'Pay_Grade_Level'], 
                color_discrete_map={'Military': 'navy', 'Civilian': 'orange'},
                title="Cost vs. Criticality Score (Hover for Details)"
            )
            fig_scatter.update_layout(xaxis_tickformat='$,.0f')
        except Exception as e:
            st.warning(f"Error creating scatter plot: {e}. Using fallback.")
            color_map = {'Military': 'navy', 'Civilian': 'orange'}
            fig_scatter = go.Figure()
            for pt in df_filtered['Personnel_Type'].unique():
                subset = df_filtered[df_filtered['Personnel_Type'] == pt]
                fig_scatter.add_trace(go.Scatter(
                    x=subset['Cost_per_Billet'],
                    y=subset['Model_Criticality_Score'],
                    mode='markers',
                    marker=dict(size=subset['Gap'], color=color_map.get(pt, 'blue')),
                    name=pt,
                    text=subset['Job_Specialty'],
                    hovertemplate='<b>%{text}</b><br>Cost: $%{x}<br>Criticality: %{y}<br>Gap: %{marker.size}<extra></extra>'
                ))
            fig_scatter.update_layout(
                title="Cost vs. Criticality Score (Hover for Details)",
                xaxis_title="Cost per Billet",
                yaxis_title="Criticality Score",
                xaxis_tickformat='$,.0f'
            )
        safe_plotly_chart(fig_scatter)
        
        # Chart D: Top Job Specialty Gaps
        sort_col_job = st.selectbox("Sort Job Gaps by:", ['Gap', 'Job_Specialty'], key='sort_job')
        ascending_job = st.selectbox("Order:", ['Descending', 'Ascending'], key='order_job') == 'Ascending'
        job_gaps = df_filtered.groupby('Job_Specialty')['Gap'].sum().reset_index().sort_values(by=sort_col_job, ascending=ascending_job).head(10)
        fig_jobs = px.bar(job_gaps, x='Job_Specialty', y='Gap', title="Top 10 Job Specialty Gaps", color='Gap', color_continuous_scale='Blues', text='Gap')
        fig_jobs.update_traces(textposition='outside')
        safe_plotly_chart(fig_jobs)

elif authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
