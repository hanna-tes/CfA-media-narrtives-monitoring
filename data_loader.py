# data_loader.py

import streamlit as st
import pandas as pd
import random
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- Configuration ---
# Replace with your actual raw GitHub CSV URL
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250828145206.csv"

# Toggle: Set to True during development to skip slow web scraping
SKIP_WEB_SCRAPING = False  # Change to True for fast testing

# --- Keyword definitions for labeling ---
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

# --- Functions ---

def get_news_categories():
    """Returns supported categories for filtering."""
    return ["business", "politics", "general"]

def assign_labels_and_scores(df_articles):
    """Assign content-based labels and scores to each article."""
    labels = list(KEYWORD_LABELS.keys()) + ["Factual", "Neutral"]
    for label in labels:
        df_articles[label] = 0.0

    for index, row in df_articles.iterrows():
        combined_text = f"{str(row['headline'] or '').lower()} {str(row['text'] or '').lower()}"

        found_strong_labels = False
        for label, keywords in KEYWORD_LABELS.items():
            score = 0.0
            for keyword in keywords:
                if (f" {keyword} " in combined_text or
                    combined_text.startswith(f"{keyword} ") or
                    combined_text.endswith(f" {keyword}")):
                    score += 0.2
            if score > 0:
                df_articles.at[index, label] = min(score, 1.0)
                if score >= 0.3:
                    found_strong_labels = True

        if not found_strong_labels:
            df_articles.at[index, "Factual"] = 0.7 + random.uniform(-0.1, 0.1)
            df_articles.at[index, "Neutral"] = 0.6 + random.uniform(-0.1, 0.1)

    # Clip scores to max 1.0
    for label in labels:
        df_articles[label] = df_articles[label].clip(upper=1.0)

    return df_articles

def fetch_content_with_retry(url, fetch_type="snippet", retries=3, delay=1):
    """Fetch article snippet or main image with retry logic."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }

    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if fetch_type == "snippet":
                # Look for article content containers
                containers = soup.find_all(['article', 'div'], class_=[
                    'article-body', 'content-body', 'story-content', 'main-content',
                    'entry-content', 'post-content', 'article__body'
                ])
                for container in containers:
                    p = container.find('p')
                    if p and p.get_text(strip=True):
                        return p.get_text(strip=True)[:500] + "..."
                # Fallback: first <p> on page
                p = soup.find('p')
                if p and p.get_text(strip=True):
                    return p.get_text(strip=True)[:500] + "..."

            elif fetch_type == "image":
                # 1. Open Graph image (best)
                og = soup.find('meta', property='og:image')
                if og and og.get('content'):
                    img_url = og['content']
                    if is_valid_image_url(img_url):
                        return img_url

                # 2. Twitter Card image
                tw = soup.find('meta', property='twitter:image')
                if tw and tw.get('content'):
                    img_url = tw['content']
                    if is_valid_image_url(img_url):
                        return img_url

                # 3. First image in article body
                containers = soup.find_all(['article', 'div'], class_=[
                    'article-body', 'content-body', 'story-content', 'main-content',
                    'entry-content', 'post-content'
                ])
                for container in containers:
                    img = container.find('img', src=True)
                    if img:
                        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                        if src and is_valid_image_url(src):
                            return src

                # 4. First image on page (last resort)
                img = soup.find('img', src=True)
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src and is_valid_image_url(src):
                        return src

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

def is_valid_image_url(url):
    """Filter out ad banners, logos, placeholders."""
    url_lower = url.lower()
    blocked = ['logo', 'ad.', 'banner', 'sponsor', 'doubleclick', 'placeholder', 'icon', 'gif']
    return all(word not in url_lower for word in blocked)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_raw_data():
    """Load and clean raw data from URL (no scraping)."""
    try:
        df = pd.read_csv(LOCAL_DATA_FILE)
        df.rename(columns={
            'title': 'headline',
            'publish_date': 'date_published',
            'media_name': 'source_name'
        }, inplace=True)

        # Convert date
        df['date_published'] = pd.to_datetime(
            df['date_published'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce'
        ).dt.date

        # Ensure required columns exist
        for col in ['headline', 'url', 'source_name', 'text', 'urlToImage']:
            if col not in df.columns:
                df[col] = None

        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_media_names_cached():
    """Cached list of media names for filter."""
    df = load_raw_data()
    if 'source_name' in df.columns:
        return sorted(df['source_name'].dropna().unique().tolist())
    return []

def get_media_names_for_filter():
    """Get all unique media names."""
    return get_media_names_cached()

def enrich_articles_with_scraping(df):
    """Enrich articles with snippets and images using resume support."""
    if SKIP_WEB_SCRAPING:
        st.info("⏭️ Web scraping skipped (SKIP_WEB_SCRAPING=True). Using fallbacks.")
        df['text'] = df['text'].fillna(
            df['headline'].apply(lambda x: f"{str(x)[:250]}..." if pd.notna(x) else "No snippet.")
        )
        df['urlToImage'] = df['urlToImage'].fillna(None)
        return df

    # Initialize session state for persistent caching across reruns
    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = {
            'url_to_text': {},
            'url_to_image': {},
            'failed': {'snippet': set(), 'image': set()}
        }

    scraped_text = st.session_state.scraped_data['url_to_text']
    scraped_image = st.session_state.scraped_data['url_to_image']
    failed_snippets = st.session_state.scraped_data['failed']['snippet']
    failed_images = st.session_state.scraped_data['failed']['image']

    # Identify URLs that still need processing
    urls_to_fetch = []
    for _, row in df.iterrows():
        url = row['url']
        needs_text = pd.isna(row['text']) or not str(row['text']).strip()
        needs_image = pd.isna(row['urlToImage']) or not str(row['urlToImage']).strip()

        if (needs_text and url not in scraped_text and url not in failed_snippets) or \
           (needs_image and url not in scraped_image and url not in failed_images):
            urls_to_fetch.append(url)

    if not urls_to_fetch:
        st.info("✅ All articles already processed or previously failed. Using cached results.")
        df['text'] = df['url'].map(scraped_text).fillna(df['text'])
        df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])
        return df

    st.info(f"🔁 Fetching content for {len(urls_to_fetch)} articles. This may take a while...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(urls_to_fetch)
    processed = 0

    for url in urls_to_fetch:
        status_text.text(f"📄 Processing: {url[:60]}...")

        # Fetch snippet
        if url not in scraped_text and url not in failed_snippets:
            snippet = fetch_content_with_retry(url, "snippet")
            if snippet:
                scraped_text[url] = snippet
            else:
                failed_snippets.add(url)
                # Fallback: use headline
                scraped_text[url] = df[df['url'] == url]['headline'].iloc[0][:250] + "..." \
                    if not df[df['url'] == url].empty else "No snippet."

        # Fetch image
        if url not in scraped_image and url not in failed_images:
            image = fetch_content_with_retry(url, "image")
            if image:
                scraped_image[url] = image
            else:
                failed_images.add(url)

        processed += 1
        progress_bar.progress(processed / total)

    # Save back to session state
    st.session_state.scraped_data['url_to_text'] = scraped_text
    st.session_state.scraped_data['url_to_image'] = scraped_image

    # Apply to DataFrame
    df['text'] = df['url'].map(scraped_text).fillna(df['text'])
    df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])

    progress_bar.empty()
    status_text.empty()
    st.success("🎉 Content enrichment complete!")

    if failed_snippets:
        st.warning(f"⚠️ Failed to fetch snippets for {len(failed_snippets)} articles.")
    if failed_images:
        st.warning(f"⚠️ Failed to fetch images for {len(failed_images)} articles.")

    return df

def load_and_transform_data():
    """
    Main function: loads, enriches, labels data.
    Uses st.session_state to avoid restarting.
    """
    # Load raw data (cached)
    df = load_raw_data()
    if df.empty:
        return pd.DataFrame()

    # Enrich with scraping (with resume support)
    df = enrich_articles_with_scraping(df.copy())

    # Assign labels
    df = assign_labels_and_scores(df)

    # Final columns
    all_labels = ["Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France", "Sensationalist", "Anti-US", "Opinion"]
    final_cols = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'source_name'] + all_labels

    for col in final_cols:
        if col not in df.columns:
            df[col] = None

    return df[df[final_cols]]
