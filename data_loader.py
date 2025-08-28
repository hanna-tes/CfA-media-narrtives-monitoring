# data_loader.py

import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urlparse

# --- Configuration ---
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250828145206.csv"

# Toggle: Set to True to skip web scraping (useful during development)
SKIP_WEB_SCRAPING = False  # Change to True for faster testing

# --- Keyword definitions ---
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

ALL_ENTITIES_TO_MONITOR = [
    'South Africa', 'Nigeria', 'Kenya', 'Ghana', 'Ivory Coast', 'Ethiopia', 
    'Sudan', 'Burkina Faso', 'Mali', 'Togo', 'Benin',
    'UAE', 'France', 'Iraq', 'China', 'Israel', 'Saudi Arabia', 'Turkey', 'USA', 'Russia',
    'militant groups', 'insurgents', 'terrorists', 'extremists'
]

# Global list of media names
ALL_MEDIA_NAMES = []


def get_news_categories():
    return ["business", "politics", "general"]


def assign_labels_and_scores(df_articles):
    """Assign labels and scores based on keyword matching."""
    labels = list(KEYWORD_LABELS.keys()) + ["Factual", "Neutral"]
    for label in labels:
        df_articles[label] = 0.0

    for index, row in df_articles.iterrows():
        combined_text = f"{str(row['headline'] or '').lower()} {str(row['text'] or '').lower()}"

        found_strong_labels = False
        for label, keywords in KEYWORD_LABELS.items():
            score = sum(0.2 for keyword in keywords
                        if (f" {keyword} " in combined_text or
                            combined_text.startswith(f"{keyword} ") or
                            combined_text.endswith(f" {keyword}")))
            if score > 0:
                df_articles.at[index, label] = min(score, 1.0)
                if score >= 0.3:
                    found_strong_labels = True

        if not found_strong_labels:
            df_articles.at[index, "Factual"] = 0.7 + random.uniform(-0.1, 0.1)
            df_articles.at[index, "Neutral"] = 0.6 + random.uniform(-0.1, 0.1)

    for label in labels:
        df_articles[label] = df_articles[label].clip(upper=1.0)
    return df_articles


def fetch_content_with_retry(url, fetch_type="snippet", retries=3, delay=1):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if fetch_type == "snippet":
                selectors = soup.find_all(['article', 'div'], class_=['article-body', 'content-body', 'story-content', 'main-content'])
                for sel in selectors:
                    p = sel.find('p')
                    if p and p.get_text(strip=True):
                        return p.get_text(strip=True)[:500] + "..."
                p = soup.find('p')
                if p and p.get_text(strip=True):
                    return p.get_text(strip=True)[:500] + "..."

            elif fetch_type == "image":
                og = soup.find('meta', property='og:image')
                if og and og.get('content'):
                    return og['content']
                tw = soup.find('meta', property='twitter:image')
                if tw and tw.get('content'):
                    return tw['content']
                img = soup.find('img', src=True)
                if img:
                    return img['src']

            return None

        except requests.exceptions.Timeout:
            time.sleep(delay * (i + 1))
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code in (403, 404):
                return None
            time.sleep(delay * (i + 1))
        except Exception:
            time.sleep(delay * (i + 1))
    return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_raw_data():
    """Load and preprocess raw data without any web scraping."""
    try:
        df = pd.read_csv(LOCAL_DATA_FILE)
        df.rename(columns={
            'title': 'headline',
            'publish_date': 'date_published',
            'media_name': 'source_name'
        }, inplace=True)

        df['date_published'] = pd.to_datetime(
            df['date_published'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce'
        ).dt.date

        # Ensure required columns exist
        for col in ['headline', 'url', 'source_name']:
            if col not in df.columns:
                df[col] = None

        # Initialize text and image columns if missing
        if 'text' not in df.columns:
            df['text'] = None
        if 'urlToImage' not in df.columns:
            df['urlToImage'] = None

        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()


def enrich_articles_with_scraping(df):
    """Fetch missing snippets and images. Does NOT use @st.cache."""
    if SKIP_WEB_SCRAPING:
        st.info("Web scraping skipped (SKIP_WEB_SCRAPING=True). Using headlines as fallback.")
        df['text'] = df['headline'].apply(lambda x: f"{str(x)[:250]}..." if pd.notna(x) else "No snippet available.")
        df['urlToImage'] = None
        return df

    # Only scrape where needed
    needs_snippet = df['text'].isna() | (df['text'].eq("")) | (df['text'].eq("None"))
    needs_image = df['urlToImage'].isna() | (df['urlToImage'].eq("")) | (df['urlToImage'].eq("None"))

    if not (needs_snippet.any() or needs_image.any()):
        st.info("All articles already have text and images. Skipping scraping.")
        return df

    st.info("Starting to fetch article content and images. This may take a few minutes...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(df)
    snippets = df['text'].tolist()
    images = df['urlToImage'].tolist()
    failed_snippets = 0
    failed_images = 0

    for i, row in df.iterrows():
        url = row['url']
        status_text.text(f"Processing ({i+1}/{total}): {url[:50]}...")

        if needs_snippet.iloc[i]:
            snippet = fetch_content_with_retry(url, "snippet")
            snippets[i] = snippet or (str(row['headline'])[:250] + "..." if pd.notna(row['headline']) else "No snippet.")
            if not snippet:
                failed_snippets += 1

        if needs_image.iloc[i]:
            image = fetch_content_with_retry(url, "image")
            images[i] = image
            if not image:
                failed_images += 1

        progress_bar.progress((i + 1) / total)

    df['text'] = snippets
    df['urlToImage'] = images

    progress_bar.empty()
    status_text.empty()

    st.success("Content enrichment complete!")
    if failed_snippets:
        st.warning(f"Failed to fetch snippets for {failed_snippets} articles.")
    if failed_images:
        st.warning(f"Failed to fetch images for {failed_images} articles.")

    return df


@st.cache_data(ttl=3600)
def get_media_names_cached():
    """Cached list of media names."""
    df = load_raw_data()
    if 'source_name' in df.columns:
        return sorted(df['source_name'].dropna().unique().tolist())
    return []


def get_media_names_for_filter():
    global ALL_MEDIA_NAMES
    if not ALL_MEDIA_NAMES:
        ALL_MEDIA_NAMES = get_media_names_cached()
    return ALL_MEDIA_NAMES


def load_and_transform_data():
    """
    Main entry point. Loads, enriches, labels data.
    Uses session_state to avoid re-scraping on every rerun.
    """

    # Use session state to persist enriched data across reruns
    if 'enriched_df' not in st.session_state:
        st.session_state.enriched_df = None

    # Step 1: Load raw data
    df = load_raw_data()
    if df.empty:
        return pd.DataFrame()

    # Step 2: Enrich only if not already done
    if st.session_state.enriched_df is None:
        df = enrich_articles_with_scraping(df)
        st.session_state.enriched_df = df  # Save to session state
    else:
        df = st.session_state.enriched_df

    # Step 3: Assign labels (fast operation)
    df = assign_labels_and_scores(df.copy())

    # Final column selection
    all_labels = ["Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France", "Sensationalist", "Anti-US", "Opinion"]
    final_cols = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'source_name'] + all_labels
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    df = df[final_cols]

    return df
