import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from functools import lru_cache # For aggressive in-session caching

# ---------------- SCRAPING FUNCTION ----------------
@lru_cache(maxsize=100)
def scrape_og_image(url):
    """
    Scrapes the Open Graph (og:image) URL from an article link.
    This is the most reliable way to get the 'featured image'.
    """
    if not url or pd.isna(url):
        return None
    
    # Use a generic placeholder if the URL is not a string
    if not isinstance(url, str):
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Use a short timeout to prevent the app from hanging forever
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status() # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for the Open Graph image tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']
            
    except requests.RequestException as e:
        # st.warning(f"Failed to scrape {url}: {e}") # Do not use st.warning here as it will clutter the app on every failed scrape
        pass # Silently fail if scraping fails
    except Exception as e:
        pass
        
    return None # Return None if no image is found or scraping fails


# ---------------- LOAD AND TRANSFORM DATA ----------------
# The caching decorator should be before the function definition
@st.cache_data(ttl=86400)
def load_and_transform_data():
    """Load CSV and parse dates."""
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
        df = df.head(100).reset_index(drop=True)  # keep first 100 rows
        
        # NOTE: We DO NOT scrape here. We scrape only for the visible articles 
        # to avoid massive performance hits on initial load.
        
        st.success(f"✅ Loaded {len(df)} sample articles!")
        return df
    except FileNotFoundError:
        st.error("Merged_dataset_sample.csv not found in repo root!")
        return pd.DataFrame()

# ---------------- FILTER HELPERS ----------------
# ... (rest of the file remains the same, no changes needed below this line)
@st.cache_data(ttl=86400)
def get_media_names():
    df = load_and_transform_data()
    return ["All"] + sorted(df['media_outlet'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_countries():
    df = load_and_transform_data()
    return ["All"] + sorted(df['target_country'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_actors():
    df = load_and_transform_data()
    return ["All"] + sorted(df['inferred_actor'].dropna().unique().tolist())
