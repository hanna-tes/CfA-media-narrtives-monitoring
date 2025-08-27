# main.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from data_loader import load_and_transform_data

def display_article_card(row):
    """Displays an article as a card with an image, title, and a link."""
    st.markdown(
        f"""
        <div style="
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            background-color: #f9f9f9;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            height: 100%;
        ">
            <img src="{row['urlToImage']}" 
                 alt="{row['headline']}" 
                 style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px;">
            <h4 style="margin-top: 10px; margin-bottom: 5px;">{row['headline']}</h4>
            <p style="font-size: 14px; color: #555;">Published: {row['date_published']}</p>
            <p style="font-size: 14px; font-weight: bold; color: {'red' if row['label'] == 'Pro-Russia' else 'green' if row['label'] == 'Anti-US' else 'blue' if row['label'] == 'Factual' else 'gray'};">
                Label: {row['label']}
            </p>
            <a href="{row['url']}" target="_blank" style="
                text-decoration: none;
                color: #fff;
                background-color: #007bff;
                padding: 8px 15px;
                border-radius: 5px;
                margin-top: 10px;
            ">
                Read more
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

def main():
    """Main function to run the Streamlit app."""
    
    st.set_page_config(layout="wide")

    st.title("Dynamic News Dashboard 📰")
    st.markdown("Your dashboard now loads live data from **NewsAPI.org**!")

    # Load data using the cached function
    df = load_and_transform_data()
    
    if df.empty:
        st.warning("No articles found for the selected time period.")
        return

    # Sidebar for filtering options
    with st.sidebar:
        st.header("Dashboard Filters")
        
        # Date range slider
        default_start_date = datetime.now().date() - timedelta(days=7)
        default_end_date = datetime.now().date()
        date_range = st.slider(
            "Select Date Range",
            min_value=default_start_date,
            max_value=default_end_date,
            value=(default_start_date, default_end_date),
            format="YYYY-MM-DD"
        )
        
        # Multi-select for labels
        available_labels = sorted(df['label'].unique())
        selected_labels = st.multiselect(
            "Filter by Political Leaning",
            options=available_labels,
            default=available_labels
        )

    # Filter the DataFrame based on user selections
    filtered_df = df[df['label'].isin(selected_labels)]
    
    # Filter by date range from the slider
    filtered_df = filtered_df[
        (filtered_df['date_published'] >= date_range[0]) & 
        (filtered_df['date_published'] <= date_range[1])
    ]

    # Display key metrics at the top
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Articles", len(filtered_df))
    col2.metric("Unique News Sources", filtered_df['url'].nunique())
    
    most_common_label = filtered_df['label'].mode()
    col3.metric("Most Common Leaning", most_common_label[0] if not most_common_label.empty else "N/A")

    st.markdown("---")

    # Display the filtered articles in a grid layout
    st.subheader("Filtered Articles")
    
    if filtered_df.empty:
        st.info("No articles match the selected filters.")
    else:
        # Sort by date, most recent first
        filtered_df = filtered_df.sort_values(by='date_published', ascending=False)
        
        # Create columns for the grid view
        cols = st.columns(3)
        
        # Display articles in the grid
        for index, row in filtered_df.iterrows():
            with cols[index % 3]:
                display_article_card(row)

if __name__ == "__main__":
    main()
