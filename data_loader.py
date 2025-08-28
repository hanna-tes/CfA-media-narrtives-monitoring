# data_loader.py

import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import time # For adding a delay between requests

# Define the path to your data directory (now a URL)
# IMPORTANT: Replace with your actual GitHub raw CSV URL
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250828134636.csv" 

# --- Keyword definitions for content-driven label assignment ---
KEYWORD_LABELS = {
    "Pro-Russia": ["russia", "kremlin", "putin", "russian forces", "moscow", "russian influence", "russia partnership"],
    "Anti-West": ["western sanctions", "western interference", "nato", "eu policy", "western powers", "western interests", "western hypocrisy"],
    "Anti-France": ["france colonialism", "french influence", "paris policy", "french troops", "francafrique", "anti-france sentiment", "french withdrawal"],
    "Anti-US": ["anti-american", "us aggression", "us interference", "us sanctions", "american hegemony", "us imperialism", "us military presence", "us meddling", "us failed policy", "us-led", "criticism of us", "condemn us", "us withdraw"],
    "Sensationalist": ["shocking", "urgent", "breaking news", "exclusive", "bombshell", "crisis", "scandal", "explosive", "reveal", "warning", "catastrophe", "unprecedented"],
    "Opinion": ["opinion", "analysis", "commentary", "viewpoint", "perspective", "column", "editorial", "blog", "critique"],
    "Business": ["economy", "business", "market", "finance", "investment", "trade", "growth", "industry", "currency", "revenue", "jobs", "commerce", "development"],
    "Politics": ["government", "election", "parliament", "president", "policy", "diplomacy", "governance", "democracy", "coup", "protest", "legislation", "political party", "reforms"]
}

# Combine all entities to monitor for potential country-based filtering in articles (not used as direct filter now)
ALL_ENTITIES_TO_MONITOR = [
    'South Africa', 'Nigeria', 'Kenya', 'Ghana', 'Ivory Coast', 'Ethiopia', 
    'Sudan', 'Burkina Faso', 'Mali', 'Togo', 'Benin',
    'UAE', 'France', 'Iraq', 'China', 'Israel', 'Saudi Arabia', 'Turkey', 'USA', 'Russia',
    'militant groups', 'insurgents', 'terrorists', 'extremists'
]


def get_news_categories():
    """
    Returns a list of supported news categories.
    These are for filtering purposes in the dashboard.
    """
    return ["business", "politics", "general"] 

def assign_labels_and_scores(df_articles):
    """
    Assigns political leanings and scores to each article based on keyword presence in content.

    Args:
        df_articles (pd.DataFrame): DataFrame of articles.

    Returns:
        pd.DataFrame: The DataFrame with new 'label' and score columns for each defined label.
    """
    labels = ["Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France", "Sensationalist", "Anti-US", "Opinion"]
    
    # Initialize all label columns to 0.0
    for label in labels:
        df_articles[label] = 0.0

    for index, row in df_articles.iterrows():
        combined_text = f"{str(row['headline']).lower()} {str(row['text']).lower()}"
        
        found_strong_labels = False
        for label, keywords in KEYWORD_LABELS.items():
            score = 0.0
            for keyword in keywords:
                # Use word boundaries for more precise matching (e.g., "us " not "business")
                if f" {keyword} " in combined_text or combined_text.startswith(f"{keyword} ") or combined_text.endswith(f" {keyword}"):
                    score += 0.2 
            
            if score > 0:
                df_articles.at[index, label] = min(score, 1.0)
                if score >= 0.3: # Consider a label "found" if score is reasonable
                    found_strong_labels = True
        
        # If no specific labels were strongly matched, assign a higher Factual/Neutral score
        if not found_strong_labels:
            df_articles.at[index, "Factual"] = 0.7 + random.uniform(-0.1, 0.1) # Default to factual
            df_articles.at[index, "Neutral"] = 0.6 + random.uniform(-0.1, 0.1) # Default to neutral

    # Ensure scores don't exceed 1.0 (clipping again just in case)
    for label in labels:
        df_articles[label] = df_articles[label].clip(upper=1.0)
            
    return df_articles

def fetch_first_paragraph(url):
    """
    Fetches the content of a given URL and attempts to extract the first paragraph.
    Includes error handling for network requests.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10) # 10-second timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Common elements where article content might be found
        article_content_divs = soup.find_all(['article', 'div'], class_=['article-body', 'content-body', 'story-content', 'main-content'])
        
        if article_content_divs:
            for div in article_content_divs:
                first_p = div.find('p')
                if first_p and first_p.get_text(strip=True):
                    return first_p.get_text(strip=True)
        
        # If no specific article div found, try to get the first significant paragraph from the body
        first_p = soup.find('p')
        if first_p and first_p.get_text(strip=True):
            return first_p.get_text(strip=True)

    except requests.exceptions.RequestException as e:
        pass
    except Exception as e:
        pass
    
    return None

def fetch_article_image(url):
    """
    Fetches the content of a given URL and attempts to extract a prominent image URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try to find Open Graph or Twitter Card image meta tags first
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']
        
        twitter_image = soup.find('meta', property='twitter:image')
        if twitter_image and twitter_image.get('content'):
            return twitter_image['content']

        # If meta tags not found, look for prominent <img> tags
        # Prioritize images within common article content containers
        article_content_divs = soup.find_all(['article', 'div'], class_=['article-body', 'content-body', 'story-content', 'main-content'])
        for div in article_content_divs:
            img = div.find('img')
            if img and img.get('src'):
                return img['src']
        
        # Fallback: get the first large-looking image from the page
        img = soup.find('img', {'src': True})
        if img and img.get('src'):
            return img['src']

    except requests.exceptions.RequestException:
        pass
    except Exception:
        pass

    return None


# Global variable to store all loaded media names
ALL_MEDIA_NAMES = []

@st.cache_data(ttl=3600)  # Cache the data for 1 hour to avoid re-loading file unnecessarily
def load_initial_data_for_media_names():
    """
    Loads data once to extract all unique media names for the filter.
    This prevents re-loading the full data frame just to get filter options.
    """
    try:
        df_temp = pd.read_csv(LOCAL_DATA_FILE)
        df_temp.rename(columns={'media_name': 'source_name'}, inplace=True)
        unique_media_names = sorted(df_temp['source_name'].dropna().unique().tolist())
        return unique_media_names
    except Exception as e:
        st.error(f"Error loading data for media names from URL: {e}")
        return []

def get_media_names_for_filter():
    """Returns a list of all unique media names from the loaded data."""
    global ALL_MEDIA_NAMES
    if not ALL_MEDIA_NAMES:
        ALL_MEDIA_NAMES = load_initial_data_for_media_names()
    return ALL_MEDIA_NAMES

@st.cache_data(ttl=3600)  # Cache the data for 1 hour to avoid re-loading file unnecessarily
def load_and_transform_data():
    """
    Loads data from the GitHub raw CSV URL, fetches article snippets and images,
    assigns labels and scores, and transforms it into a pandas DataFrame.
    """
    try:
        # Load the CSV file directly from the URL
        df_articles = pd.read_csv(LOCAL_DATA_FILE)

        # Rename columns to match the dashboard's expectations
        df_articles.rename(columns={
            'title': 'headline',
            'publish_date': 'date_published',
            'media_name': 'source_name' 
        }, inplace=True)

        # Ensure 'date_published' is datetime type and then convert to date object
        df_articles['date_published'] = pd.to_datetime(
            df_articles['date_published'], 
            format="%Y-%m-%d %H:%M:%S.%f", # Specify format including fractional seconds
            errors='coerce'               # Convert unparseable dates to NaT instead of erroring
        ).dt.date
        
        # --- Fetch article snippets and images from URLs ---
        # Only fetch if 'text' column is empty or doesn't exist AND 'urlToImage' is empty or doesn't exist
        if ('text' not in df_articles.columns or df_articles['text'].isnull().all()) or \
           ('urlToImage' not in df_articles.columns or df_articles['urlToImage'].isnull().all()):
            
            st.info("Fetching article snippets and images from URLs. This may take a moment...")
            progress_bar = st.progress(0)
            total_articles = len(df_articles)
            
            snippets = []
            image_urls = []
            for i, row in df_articles.iterrows():
                # Fetch snippet
                snippet = fetch_first_paragraph(row['url'])
                if snippet:
                    snippets.append(snippet[:500] + "..." if len(snippet) > 500 else snippet)
                else:
                    snippets.append(row['headline'][:250] + "..." if pd.notna(row['headline']) else "")
                
                # Fetch image
                image = fetch_article_image(row['url'])
                image_urls.append(image)

                progress_bar.progress((i + 1) / total_articles)
                time.sleep(0.02)
            
            df_articles['text'] = snippets
            df_articles['urlToImage'] = image_urls
            st.success("Finished fetching snippets and images.")
        else:
            # If text and image columns are already populated, just truncate text
            df_articles['text'] = df_articles['text'].apply(lambda x: str(x)[:500] + "..." if pd.notna(x) and len(str(x)) > 500 else x)


        # Assign content-driven labels and scores
        df_articles = assign_labels_and_scores(df_articles)
        
        # Select and reorder the final columns to match main.py's expectations
        all_labels = ["Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France", "Sensationalist", "Anti-US", "Opinion"]
        final_cols = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'source_name'] + all_labels
        
        # Ensure all final_cols exist before selection
        for col in final_cols:
            if col not in df_articles.columns:
                df_articles[col] = None
        
        df_articles = df_articles[final_cols]
    
        return df_articles

    except Exception as e:
        st.error(f"Error loading or processing data from URL: {e}")
        return pd.DataFrame()
