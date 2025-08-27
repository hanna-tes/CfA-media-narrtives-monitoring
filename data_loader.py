# data_loader.py

import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta
from config import NEWSAPI_KEY

def get_african_countries():
    """
    Returns a dictionary of selected African countries and their 2-letter ISO codes.
    """
    return {
        'South Africa': 'za', 'Nigeria': 'ng', 'Egypt': 'eg', 'Morocco': 'ma'
    }

def get_news_categories():
    """
    Returns a list of supported news categories.
    """
    return ["general", "business", "technology", "health", "science", "sports", "entertainment"]

def get_articles_from_newsapi(country, category):
    """
    Fetches top headlines from NewsAPI.org for a specified country and category.

    Args:
        country (str): The 2-letter ISO code for the country.
        category (str): The news category.

    Returns:
        list: A list of dictionaries, where each dictionary is an article.
    """
    base_url = "https://newsapi.org/v2/top-headlines"
    
    params = {
        'country': country,
        'category': category,
        'pageSize': 100, # Max articles per request
        'apiKey': NEWSAPI_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status() # Raises an HTTPError for bad responses
        data = response.json()
        if data['status'] == 'ok':
            return data['articles']
        else:
            st.error(f"Error from NewsAPI: {data.get('message', 'Unknown error')}")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching data: {e}")
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
def load_and_transform_data(country_code, category):
    """
    Loads data, assigns labels, and transforms it into a pandas DataFrame.
    """
    raw_articles = get_articles_from_newsapi(country_code, category)
    
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
