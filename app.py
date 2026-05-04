import streamlit as st
import pandas as pd
import plotly.express as px

# Sample Data

df = pd.DataFrame({
    'Category': ['A', 'B', 'C', 'D'],
    'Values': [10, 20, 15, 30]
})

# Title
st.title('Strategic Manpower Optimization Module (SMOM)')

# Bar Chart
try:
    fig_bar = px.bar(df, x='Category', y='Values', title='Bar Chart')
    st.plotly_chart(fig_bar)
except Exception as e:
    st.error(f'Error displaying bar chart: {e}')

# Line Chart
try:
    fig_line = px.line(df, x='Category', y='Values', title='Line Chart')
    st.plotly_chart(fig_line)
except Exception as e:
    st.error(f'Error displaying line chart: {e}')

# Pie Chart
try:
    fig_pie = px.pie(df, names='Category', values='Values', title='Pie Chart')
    st.plotly_chart(fig_pie)
except Exception as e:
    st.error(f'Error displaying pie chart: {e}')

# Scatter Plot
try:
    fig_scatter = px.scatter(df, x='Category', y='Values', title='Scatter Plot')
    st.plotly_chart(fig_scatter)
except Exception as e:
    st.error(f'Error displaying scatter plot: {e}')
