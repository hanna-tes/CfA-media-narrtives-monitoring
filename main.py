# main.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from data_loader import load_and_transform_data, get_african_countries, get_news_categories

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
            <p style="font-size: 14px; color: #555;">{row['text']}</p>
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

    st.title("CfA Media Narratives Monitoring 🌍")
    st.markdown("Dashboard for monitoring media narratives from African news sources.")

    # Sidebar for filtering options
    with st.sidebar:
        st.header("Dashboard Filters")
        
        # Country filter
        african_countries = get_african_countries()
        selected_country_name = st.selectbox(
            "Select Country",
            options=list(african_countries.keys())
        )
        selected_country_code = african_countries[selected_country_name]
        
        # Category filter (now works with countries)
        news_categories = get_news_categories()
        selected_category = st.selectbox(
            "Select Category",
            options=news_categories
        )

        st.markdown("---")
        st.subheader("Simulated Filters")
        
        # Multi-select for labels (from a fixed list for now)
        available_labels = ["Pro-Russia", "Anti-US", "Factual", "Neutral"]
        selected_labels = st.multiselect(
            "Filter by Political Leaning",
            options=available_labels,
            default=available_labels
        )

    # Load data based on selected filters
    df = load_and_transform_data(selected_country_name, selected_category)
    
    if df.empty:
        st.warning("No articles found for the selected filters. Please try a different combination.")
        return

    # Filter the DataFrame based on the simulated labels
    filtered_df = df[df['label'].isin(selected_labels)]
    
    # Display key metrics at the top
    st.subheader("Key Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Articles", len(filtered_df))
    
    # Calculate unique sources. The GNews API doesn't always provide a source name, so we use the URL to be safe.
    col2.metric("Unique News Sources", filtered_df['url'].nunique())
    
    most_common_label = filtered_df['label'].mode()
    col3.metric("Most Common Leaning", most_common_label[0] if not most_common_label.empty else "N/A")

    st.markdown("---")

    # Bar chart for label distribution
    st.subheader("Narrative Distribution")
    if not filtered_df.empty:
        label_counts = filtered_df['label'].value_counts().reset_index()
        label_counts.columns = ['label', 'count']
        
        chart = alt.Chart(label_counts).mark_bar().encode(
            x=alt.X('label', axis=None),
            y=alt.Y('count', title='Number of Articles'),
            color=alt.Color('label', legend=alt.Legend(title="Political Leaning")),
            tooltip=['label', 'count']
        ).properties(
            title='Article Count by Political Leaning'
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No articles to display in the chart.")
        
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
