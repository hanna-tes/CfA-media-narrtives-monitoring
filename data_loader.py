# data_loader.py

import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta
from config import NEWSAPI_KEY

def get_african_countries():
    """
    Returns a dictionary of African countries and their ISO codes for search queries.
    """
    return {
        'All Countries': None,
        'South Africa': 'za',
        'Nigeria': 'ng',
        'Kenya': 'ke',
        'Ghana': 'gh',
        'Ivory Coast': 'ci',
        'Ethiopia': 'et',
        'Sudan': 'sd',
        'Burkina Faso': 'bf',
        'Mali': 'ml',
        'Togo': 'tg'
    }

def get_news_categories():
    """
    Returns a list of supported news categories.
    """
    return ["general", "business", "technology", "health", "science", "sports", "entertainment", "politics"]

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
def load_and_transform_data(country_code, category):
    """
    Loads data from the GNews API, assigns labels, and transforms it into a pandas DataFrame.
    """
    base_url = "https://gnews.io/api/v4/search"
    query_string = category
    if country_code:
        query_string = f"{category} AND {country_code} news"
        
    params = {
        'q': query_string,
        'lang': 'en',
        'country': country_code,
        'apikey': NEWSAPI_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if 'articles' in data:
            raw_articles = data['articles']
        else:
            st.error(f"Error from GNews: {data.get('errors', 'Unknown error')}")
            raw_articles = []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching data from GNews: {e}")
        raw_articles = []

    if not raw_articles:
        return pd.DataFrame()

    labeled_articles = assign_fake_labels(raw_articles)
    df_articles = pd.DataFrame(labeled_articles)

    # Clean the DataFrame and format it to match your original structure
    if not df_articles.empty:
        df_articles['publishedAt'] = pd.to_datetime(df_articles['publishedAt'])
        df_articles['date_published'] = df_articles['publishedAt'].dt.date
        df_articles.rename(columns={'title': 'headline', 'image': 'urlToImage'}, inplace=True)
        
        # Select and reorder the final columns
        final_cols = ['headline', 'content', 'url', 'urlToImage', 'date_published', 'label']
        for col in final_cols:
            if col not in df_articles.columns:
                df_articles[col] = None
        
        df_articles = df_articles[final_cols]
        # Rename the content column to text to be consistent with the app's display
        df_articles.rename(columns={'content': 'text'}, inplace=True)
    
    return df_articles
