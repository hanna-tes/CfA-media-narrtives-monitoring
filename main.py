 data_loader.py

import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta
from config import NEWSAPI_KEY

def get_african_countries():
    """
    Returns a dictionary of selected African countries and their 2-letter ISO codes.
    NewsAPI free tier supports a limited number of countries.
    """
    return {
        'South Africa': 'za', 'Nigeria': 'ng', 'Egypt': 'eg', 'Morocco': 'ma',
        'Kenya': 'ke', 'Ghana': 'gh'
    }

def get_news_categories():
    """
    Returns a list of supported news categories.
    """
    return ["general", "business", "technology", "health", "science", "sports", "entertainment"]

@st.cache_data(ttl=3600)
def get_news_sources_for_country(country_code):
    """
    Fetches all available news sources for a specified country from NewsAPI.org.
    
    Args:
        country_code (str): The 2-letter ISO code for the country.

    Returns:
        list: A list of dictionaries, where each dictionary is a news source.
    """
    base_url = "https://newsapi.org/v2/top-headlines/sources"
    params = {
        'country': country_code,
        'apiKey': NEWSAPI_KEY
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'ok':
            return data['sources']
        else:
            st.error(f"Error from NewsAPI: {data.get('message', 'Unknown error')}")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching sources: {e}")
        return []

def assign_fake_labels(articles):
    """
    Assigns fake political leanings to each article for dashboard visualization.
    This simulates the AI analysis from your original dataset.

    Args:
        articles (list): A list of article dictionaries.

    Returns:
        list: The same list of articles with new 'label' key.
    """
    labels = ["Pro-Russia", "Anti-US", "Factual", "Neutral"]
    
    for article in articles:
        article['label'] = random.choice(labels)
        
    return articles

@st.cache_data(ttl=3600)  # Cache the data for 1 hour to avoid redundant API calls
def load_and_transform_data(country_code, category, source_id=None):
    """
    Loads data, assigns labels, and transforms it into a pandas DataFrame.
    """
    base_url = "https://newsapi.org/v2/top-headlines"
    params = {
        'country': country_code,
        'category': category,
        'pageSize': 100, # Max articles per request
        'apiKey': NEWSAPI_KEY
    }
    
    if source_id:
        params['sources'] = source_id
        # The 'category' parameter is not supported when using 'sources'
        del params['category']
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'ok':
            raw_articles = data['articles']
        else:
            st.error(f"Error from NewsAPI: {data.get('message', 'Unknown error')}")
            raw_articles = []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching data: {e}")
        raw_articles = []

    if not raw_articles:
        return pd.DataFrame()

    labeled_articles = assign_fake_labels(raw_articles)
    df_articles = pd.DataFrame(labeled_articles)

    # Clean the DataFrame and format it to match your original structure
    if not df_articles.empty:
        df_articles['publishedAt'] = pd.to_datetime(df_articles['publishedAt'])
        df_articles['date_published'] = df_articles['publishedAt'].dt.date
        df_articles.rename(columns={'title': 'headline', 'content': 'text'}, inplace=True)
        
        # Select and reorder the final columns
        final_cols = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'label']
        for col in final_cols:
            if col not in df_articles.columns:
                df_articles[col] = None
        
        df_articles = df_articles[final_cols]
    
    return df_articles


# main.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from data_loader import load_and_transform_data, get_african_countries, get_news_categories, get_news_sources_for_country

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

        # Get news sources for the selected country
        sources_list = get_news_sources_for_country(selected_country_code)
        source_names = {source['name']: source['id'] for source in sources_list}
        selected_source_name = st.selectbox(
            "Select News Source",
            options=["All Sources"] + list(source_names.keys())
        )
        selected_source_id = source_names.get(selected_source_name, None)

        # Category filter (this will be ignored if a specific source is selected)
        news_categories = get_news_categories()
        selected_category = st.selectbox(
            "Select Category",
            options=news_categories,
            disabled=(selected_source_id is not None)
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
    df = load_and_transform_data(selected_country_code, selected_category, selected_source_id)
    
    if df.empty:
        st.warning("No articles found for the selected filters. Please try a different combination.")
        return

    # Filter the DataFrame based on the simulated labels
    filtered_df = df[df['label'].isin(selected_labels)]
    
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
