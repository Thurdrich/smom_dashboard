import pandas as pd
import plotly.express as px

# 1. Load the data (In Databricks, ensure path starts with /dbfs/ if on storage)
# For this demo, assuming it's in the local driver directory
df = pd.read_csv('CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv')

# 2. Add Cost Data (Data Enrichment)
cost_map = {
    'E1': 50000, 'E2': 55000, 'E3': 60000, 'E4': 70000, 'E5': 85000, 'E6': 100000, 'E7': 120000, 'E8': 140000, 'E9': 160000,
    'GS-07': 70000, 'GS-09': 85000, 'GS-11': 100000, 'GS-12': 120000, 'GS-13': 140000, 'GS-14': 160000, 'GS-15': 180000
}
df['Cost_per_Billet'] = df['Pay_Grade_Level'].map(cost_map)
df.dropna(subset=['Cost_per_Billet'], inplace=True)

# Calculate financial impact
df['Gap_Cost'] = df['Gap'] * df['Cost_per_Billet']

# Ensure 'Gap' column is non-negative for plotting bubble size
df['Gap_Size'] = df['Gap'].abs()

# 3. Create the 4 Interactive Plots

# Chart 1: Gaps by BSO
bso_gaps = df.groupby('BSO')['Gap'].sum().reset_index().sort_values('Gap', ascending=False)
fig1 = px.bar(bso_gaps, x='BSO', y='Gap', color='Gap', color_continuous_scale='viridis', title="Total Manpower Gaps by BSO")

# Chart 2: Gaps by Platform
plat_gaps = df.groupby('Platform')['Gap'].sum().reset_index().sort_values('Gap', ascending=False)
fig2 = px.bar(plat_gaps, x='Platform', y='Gap', color='Gap', color_continuous_scale='plasma', title="Total Manpower Gaps by Platform")

# Chart 3: Cost vs Criticality Scatter Plot
fig3 = px.scatter(
    df, x='Cost_per_Billet', y='Model_Criticality_Score', color='Personnel_Type', size='Gap_Size',
    hover_data=['BSO', 'Platform', 'Job_Specialty', 'Pay_Grade_Level'],
    color_discrete_map={'Military': 'navy', 'Civilian': 'orange'},
    title="DON/MSC Interactive Cost vs. Criticality Score"
)
fig3.update_layout(xaxis_tickformat='$,.0f')

# Chart 4: Financial Impact by BSO
fin_bso = df.groupby('BSO')['Gap_Cost'].sum().reset_index().sort_values('Gap_Cost', ascending=False)
fig4 = px.bar(fin_bso, x='BSO', y='Gap_Cost', color='Gap_Cost', color_continuous_scale='cividis', title="Estimated Financial Impact by BSO")
fig4.update_layout(yaxis_tickformat='$,.0f')

# --- DATABRICKS DISPLAY ---
# In Databricks, running these shows them inline
fig1.show()
fig2.show()
fig3.show()
fig4.show()

# 4. Generate the HTML File for download/export
html_template = f"""
<html>
<head>
    <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; }}
        h1 {{ text-align: center; color: #00205b; }}
        .dashboard {{ display: flex; flex-wrap: wrap; justify-content: center; }}
        .chart-container {{ width: 48%; min-width: 500px; background: white; margin: 10px; padding: 10px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>DON/MSC Interactive Manpower & Financial Dashboard</h1>
    <div class=\"dashboard\">
        <div class=\"chart-container\">{fig1.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class=\"chart-container\">{fig2.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class=\"chart-container\">{fig3.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class=\"chart-container\">{fig4.to_html(full_html=False, include_plotlyjs=False)}</div>
    </div>
</body>
</html>
"""

# Save locally in Databricks workspace
output_path = "DON_MSC_Complete_Interactive_Dashboard.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"Success! Dashboard created and displayed. Dashboard saved as {output_path}.")
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
