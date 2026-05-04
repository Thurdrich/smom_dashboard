import streamlit as st
import pandas as pd
import plotly.express as px

# Load the data
@st.cache
def load_data():
    data = pd.read_csv('CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv')
    return data

# Main application function
def main():
    st.title('SMOM Dashboard')

    # Load data
    df = load_data()

    # Display metrics
    st.header('Metrics')
    st.write(f'Total Records: {df.shape[0]}')
    st.write(f'Columns: {df.columns.tolist()}')

    # Plot 1
    fig1 = px.histogram(df, x='metric1', title='Histogram of Metric 1')
    st.plotly_chart(fig1)

    # Plot 2
    fig2 = px.line(df, x='date', y='metric2', title='Metric 2 Over Time')
    st.plotly_chart(fig2)

    # Plot 3
    fig3 = px.scatter(df, x='metric3', y='metric4', title='Scatterplot of Metric 3 vs Metric 4')
    st.plotly_chart(fig3)

    # Plot 4
    fig4 = px.box(df, y='metric5', title='Boxplot of Metric 5')
    st.plotly_chart(fig4)

    # Data table
    st.header('Data Table')
    st.dataframe(df)

if __name__ == '__main__':
    main()
