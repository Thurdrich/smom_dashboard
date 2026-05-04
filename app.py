import streamlit as st
import pandas as pd
import plotly.express as px

# Load the data
@st.cache_data
def load_data():
    data = pd.read_csv('CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv')
    return data

# Main application function
def main():
    st.title('SMOM Dashboard')

    try:
        # Load data
        df = load_data()
        
        # Display metrics
        st.header('Metrics')
        st.write(f'Total Records: {df.shape[0]}')
        st.write(f'Columns: {df.columns.tolist()}')

        # Plot 1 - Histogram
        if 'metric1' in df.columns:
            fig1 = px.histogram(df, x='metric1', title='Histogram of Metric 1')
            st.plotly_chart(fig1)
        else:
            st.warning("Column 'metric1' not found in data")

        # Plot 2 - Line chart
        if 'date' in df.columns and 'metric2' in df.columns:
            fig2 = px.line(df, x='date', y='metric2', title='Metric 2 Over Time')
            st.plotly_chart(fig2)
        else:
            st.warning("Columns 'date' or 'metric2' not found in data")

        # Plot 3 - Scatter plot
        if 'metric3' in df.columns and 'metric4' in df.columns:
            fig3 = px.scatter(df, x='metric3', y='metric4', title='Scatterplot of Metric 3 vs Metric 4')
            st.plotly_chart(fig3)
        else:
            st.warning("Columns 'metric3' or 'metric4' not found in data")

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