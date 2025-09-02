import streamlit as st
import pandas as pd
import random
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin # Added urljoin
from groq import Groq

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    client = None
    st.warning(f"⚠️ Groq API key not found. Error: {e}. Running without LLM summarization.")

# --- Configuration ---
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250829083045.csv"
SKIP_WEB_SCRAPING = False

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

# ✅ COMPLETE REVISED FUNCTION
def fetch_content_with_retry(url, fetch_type="snippet", retries=3, delay=1):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the main content container of the article
            content_container = soup.find('article') or \
                                soup.find('div', class_=['article-body', 'content-body', 'story-content', 'main-content']) or \
                                soup.find('main')

            if fetch_type == "snippet":
                if content_container:
                    paragraphs = content_container.find_all('p')
                    full_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                    if len(full_text) > 50:
                        return full_text[:3000] # Give ample text for LLM
                return "No meaningful content found to summarize."

            elif fetch_type == "image":
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                
                twitter_image = soup.find('meta', property='twitter:image')
                if twitter_image and twitter_image.get('content'):
                    return twitter_image['content']

                if content_container:
                    img = content_container.find('img', src=True)
                    if img:
                        return urljoin(url, img.get('src'))

                img = soup.find('img', src=True)
                if img:
                    return urljoin(url, img.get('src'))
                    
                return None

        except requests.exceptions.RequestException:
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
    if 'llm_cache' not in st.session_state:
        st.session_state.llm_cache = {}
    
    # This check is now redundant because of the fix below, but harmless
    if text in st.session_state.llm_cache:
        return st.session_state.llm_cache[text]
    
    # ✅ FIX: Check if `text` is None or empty FIRST to prevent the TypeError.
    # This single line handles all cases of failed scrapes or insufficient content.
    if not text or not client or len(text) < 150 or "No meaningful content" in text:
        return "Summary not available (insufficient content)."
    
    # Check cache again after validating text
    if text in st.session_state.llm_cache:
        return st.session_state.llm_cache[text]

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a news summarizer. Summarize the key points of this article in one concise paragraph (around 50-80 words). Be factual and neutral. Do not include opinions or promotional language."},
                {"role": "user", "content": text}
            ],
            model="llama3-8b-8192",
            temperature=0.3,
            max_tokens=120,
            top_p=1.0
        )
        summary = chat_completion.choices[0].message.content.strip()
        
        st.session_state.llm_cache[text] = summary
        return summary
    except Exception as e:
        st.warning(f"LLM summarization failed: {e}")
        return f"LLM Error. Snippet: {text[:200]}..."
        
def enrich_articles_with_scraping(df, progress_callback=None):
    if SKIP_WEB_SCRAPING:
        df['text'] = "Scraping disabled for development."
        df['urlToImage'] = None
        return df

    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = {
            'url_to_text': {},
            'url_to_image': {}
        }

    scraped_text = st.session_state.scraped_data['url_to_text']
    scraped_image = st.session_state.scraped_data['url_to_image']

    urls_to_fetch = df[
        (df['text'].isnull() | (df['text'] == '')) & (df['url'].notnull()) |
        (df['urlToImage'].isnull() | (df['urlToImage'] == '')) & (df['url'].notnull())
    ]['url'].unique()

    if len(urls_to_fetch) == 0:
        df['text'] = df['url'].map(scraped_text).fillna(df['text'])
        df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])
        return df

    total = len(urls_to_fetch)
    processed = 0

    for url in urls_to_fetch:
        # Fetch snippet and summarize
        if url not in scraped_text:
            content = fetch_content_with_retry(url, "snippet")
            summary = summarize_with_llama(content)
            scraped_text[url] = summary

        # Fetch image
        if url not in scraped_image:
            image_url = fetch_content_with_retry(url, "image")
            
            if not is_valid_image_url(image_url):
                try:
                    domain = urlparse(url).netloc.replace('www.', '', 1)
                    image_url = f"https://logo.clearbit.com/{domain}"
                except Exception:
                    image_url = 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
            
            scraped_image[url] = image_url

        processed += 1
        if progress_callback:
            progress_callback(processed / total, f"Processed {processed}/{total} articles...")

    st.session_state.scraped_data['url_to_text'] = scraped_text
    st.session_state.scraped_data['url_to_image'] = scraped_image

    df['text'] = df['url'].map(scraped_text).fillna(df['text'])
    df['urlToImage'] = df['url'].map(scraped_image).fillna(df['urlToImage'])
    
    # Final cleanup for any remaining empty values
    df['text'].fillna("Summary not available.", inplace=True)
    df['urlToImage'].fillna('https://placehold.co/400x200/cccccc/000000?text=No+Image', inplace=True)

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
