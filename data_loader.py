# data_loader.py (updated with progress_callback)

import streamlit as st
import pandas as pd
import random
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from groq import Groq

# --- Configuration ---
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250829083045.csv"
SKIP_WEB_SCRAPING = False  # Set to True during development

# --- Initialize LLM Cache ---
if 'llm_cache' not in st.session_state:
    st.session_state.llm_cache = {}

# --- Initialize Groq Client ---
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except:
    client = None
    st.warning("⚠️ Groq API key not found. Running without LLM summarization.")

# --- Keyword Labels ---
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

def get_news_categories():
    return ["business", "politics", "general"]

def assign_labels_and_scores(df_articles):
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if fetch_type == "snippet":
                containers = soup.find_all(['article', 'div'], class_=[
                    'article-body', 'content-body', 'story-content', 'main-content'
                ])
                for container in containers:
                    p = container.find('p')
                    if p and p.get_text(strip=True):
                        return p.get_text(strip=True)[:1000]  # Longer for LLM
                p = soup.find('p')
                if p and p.get_text(strip=True):
                    return p.get_text(strip=True)[:1000]
                return "No content available."

            elif fetch_type == "image":
                og = soup.find('meta', property='og:image')
                if og and og.get('content'):
                    return og['content']
                tw = soup.find('meta', property='twitter:image')
                if tw and tw.get('content'):
                    return tw['content']
                img = soup.find('img', src=True)
                if img:
                    return img['src'] or img.get('data-src')
                return None

        except Exception:
            time.sleep(delay * (i + 1))
    return None

def is_valid_image_url(url):
    if not url:
        return False
    url_lower = url.lower()
    blocked = ['logo', 'ad.', 'banner', 'sponsor', 'doubleclick', 'gif', 'svg', 'png?size=', 'taboola', 'youtube', 'favicon', '.ico']
    return all(word not in url_lower for word in blocked)

@st.cache_data(ttl=3600)
def load_raw_data():
    try:
        df = pd.read_csv(LOCAL_DATA_FILE)
        df.rename(columns={
            'title': 'headline',
            'publish_date': 'date_published',
            'media_name': 'source_name'
        }, inplace=True)

        df['date_published'] = pd.to_datetime(df['date_published'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
        df['date_published'] = df['date_published'].dt.date

        for col in ['headline', 'url', 'source_name', 'text', 'urlToImage']:
            if col not in df.columns:
                df[col] = None
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_media_names_cached():
    df = load_raw_data()
    if 'source_name' in df.columns:
        return sorted(df['source_name'].dropna().unique().tolist())
    return []

def get_media_names_for_filter():
    return get_media_names_cached()

def summarize_with_llama(text):
    """Cached LLM summarization"""
    # ✅ PROPER INITIALIZATION - check every time the function is called
    if 'llm_cache' not in st.session_state:
        st.session_state.llm_cache = {}
    
    # Now we know llm_cache exists
    if text in st.session_state.llm_cache:
        return st.session_state.llm_cache[text]
    
    if not client or len(text) < 50:
        return text[:300] + "..." if text else "No summary available."
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Summarize this article in one short paragraph. Focus on the main topic. Remove author names, publication dates, and promotional text. Keep it neutral and factual."},
                {"role": "user", "content": text[:3000]}
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct",  # ✅ CORRECT MODEL ID
            temperature=0.3,
            max_tokens=150,
            top_p=1.0
        )
        summary = chat_completion.choices[0].message.content.strip()
        st.session_state.llm_cache[text] = summary
        return summary
    except Exception as e:
        st.warning(f"LLM failed: {e}")
        return text[:300] + "..."

def enrich_articles_with_scraping(df, progress_callback=None):
    if SKIP_WEB_SCRAPING:
        df['text'] = df['headline'].apply(lambda x: f"{str(x)[:250]}..." if pd.notna(x) else "No summary available.")
        df['urlToImage'] = None
        return df

    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = {
            'url_to_text': {},
            'url_to_image': {}
        }

    scraped_text = st.session_state.scraped_data['url_to_text']
    scraped_image = st.session_state.scraped_data['url_to_image']

    urls_to_fetch = []
    for _, row in df.iterrows():
        url = row['url']
        needs_text = pd.isna(row['text']) or not str(row['text']).strip()
        needs_image = pd.isna(row['urlToImage']) or not str(row['urlToImage']).strip()

        if (needs_text and url not in scraped_text) or (needs_image and url not in scraped_image):
            urls_to_fetch.append(url)

    if not urls_to_fetch:
        df['text'] = df['url'].map(scraped_text).fillna(df['text'])
        df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])
        return df

    # Track progress for real-time feedback
    total = len(urls_to_fetch)
    processed = 0

    for url in urls_to_fetch:
        # Fetch snippet
        if url not in scraped_text:
            snippet = fetch_content_with_retry(url, "snippet")
            if snippet and len(snippet) > 150:  # Only summarize substantial content
                # ✅ Critical: Use cached LLM results
                summarized = summarize_with_llama(snippet)
                scraped_text[url] = summarized
            else:
                # Skip LLM for short snippets
                scraped_text[url] = snippet[:300] + "..." if snippet else "No summary available."

        # Fetch image
        if url not in scraped_image:
            image = fetch_content_with_retry(url, "image")

            # Fallback 1: Clearbit logo
            if not image or not is_valid_image_url(image):
                try:
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.replace('www.', '', 1)
                    image = f"https://logo.clearbit.com/{domain}"
                except Exception:
                    image = None

            # Fallback 2: Favicon
            if not image:
                try:
                    parsed_url = urlparse(url)
                    image = f"https://{parsed_url.netloc}/favicon.ico"
                except Exception:
                    image = None

            # Fallback 3: Placeholder
            if not image or not is_valid_image_url(image):
                image = 'https://placehold.co/400x200/cccccc/000000?text=No+Image'

            scraped_image[url] = image

        # Update progress (for main.py to track)
        processed += 1
        if progress_callback:
            progress_callback(processed / total, f"Processed {processed}/{total} articles...")

    st.session_state.scraped_data['url_to_text'] = scraped_text
    st.session_state.scraped_data['url_to_image'] = scraped_image

    df['text'] = df['url'].map(scraped_text).fillna(df['text'])
    df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])

    return df

def load_and_transform_data(progress_callback=None):
    df = load_raw_data()
    if df.empty:
        return pd.DataFrame()
    df = enrich_articles_with_scraping(df.copy(), progress_callback=progress_callback)
    df = assign_labels_and_scores(df)
    all_labels = ["Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France", "Sensationalist", "Anti-US", "Opinion"]
    final_cols = ['headline', 'text', 'url', 'urlToImage', 'date_published', 'source_name'] + all_labels
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    return df[final_cols].copy()
