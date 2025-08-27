# data_loader.py

import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta
from config import NEWSAPI_KEY

def get_articles_from_newsapi(start_date, end_date):
    """
    Fetches news articles from the NewsAPI.org Everything endpoint.

    Args:
        start_date (str): The start date for the search in YYYY-MM-DD format.
        end_date (str): The end date for the search in YYYY-MM-DD format.

    Returns:
        list: A list of dictionaries, where each dictionary is an article.
    """
    base_url = "https://newsapi.org/v2/everything"
    
    # We will query for general topics to get a wide range of articles.
    # You can change this to be more specific.
    params = {
        'q': 'technology OR business OR world OR politics',
        'from': start_date,
        'to': end_date,
        'sortBy': 'relevancy',
        'language': 'en',
        'apiKey': NEWSAPI_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
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
        # Get a random label and assign it to the article
        article['label'] = random.choice(labels)
        
    return articles

@st.cache_data(ttl=3600)  # Cache the data for 1 hour to avoid redundant API calls
def load_and_transform_data():
    """
    Loads data, assigns labels, and transforms it into a pandas DataFrame.
    """
    # Define a date range. We'll get articles from the last 7 days.
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Fetch articles from the NewsAPI
    raw_articles = get_articles_from_newsapi(start_date, end_date)
    
    # Assign our simulated AI labels
    labeled_articles = assign_fake_labels(raw_articles)

    # Transform the list of dictionaries into a DataFrame
    df_articles = pd.DataFrame(labeled_articles)

    # Clean the DataFrame and format it to match your original structure
    if not df_articles.empty:
        df_articles['publishedAt'] = pd.to_datetime(df_articles['publishedAt'])
        df_articles['date_published'] = df_articles['publishedAt'].dt.date
        df_articles.rename(columns={'title': 'headline', 'content': 'text'}, inplace=True)
        df_articles = df_articles[['headline', 'text', 'url', 'urlToImage', 'date_published', 'label']]
        df_articles.columns = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'label']

    return df_articles
