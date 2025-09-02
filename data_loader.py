import streamlit as st
import pandas as pd
import random
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import asyncio
from playwright.async_api import async_playwright

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

# === NEW PLAYWRIGHT-BASED FUNCTION ===
CSS_SELECTORS = [
    'article',
    'div.article-body',
    'div.content-body',
    'div.story-content',
    'div.main-content',
    'div.post_content',
    'div.jl_content',
    'div.story.btm20',
    'div.container-fluid',
    'div.article_content',
    'div.col-tn-12',
    'div.col-sm-8',
    'div.column',
    'main',
    'div.mycase4_reader',
    'div.content-inner'
]

async def fetch_content_with_playwright(url, fetch_type="snippet"):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Navigate to the URL and wait for the network to be idle
            await page.goto(url, wait_until='networkidle')

            # Find the first element that matches any of the selectors
            main_content = None
            for selector in CSS_SELECTORS:
                main_content_elements = await page.locator(selector).all()
                if main_content_elements:
                    main_content = main_content_elements[0]
                    break
            
            if main_content:
                if fetch_type == "snippet":
                    full_text = await main_content.inner_text()
                    if len(full_text.strip()) > 50:
                        await browser.close()
                        return full_text[:3000] # Give ample text for LLM
                
                elif fetch_type == "image":
                    # Try to find Open Graph or Twitter image first
                    og_image_url = await page.locator('meta[property="og:image"]').get_attribute('content')
                    if og_image_url:
                        await browser.close()
                        return og_image_url
                    
                    twitter_image_url = await page.locator('meta[property="twitter:image"]').get_attribute('content')
                    if twitter_image_url:
                        await browser.close()
                        return twitter_image_url
                        
                    # Find first image within the main content container
                    img_src = await main_content.locator('img').get_attribute('src')
                    if img_src:
                        await browser.close()
                        return urljoin(url, img_src)
            
            await browser.close()
            return "No meaningful content found to summarize." if fetch_type == "snippet" else None

    except Exception as e:
        print(f"Playwright failed to fetch content from {url}: {e}")
        return "No meaningful content found to summarize." if fetch_type == "snippet" else None

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
    
    if not text or not client or len(text) < 150 or "No meaningful content" in text:
        return "Summary not available (insufficient content)."
    
    if text in st.session_state.llm_cache:
        return st.session_state.llm_cache[text]

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a news summarizer. Summarize the key points of this article in one concise paragraph (around 50-80 words). Be factual and neutral. Do not include opinions or promotional language."},
                {"role": "user", "content": text}
            ],
            model="llama-3.1-8b-instant",
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
        # Fetch snippet and summarize using the new async function
        if url not in scraped_text:
            content = asyncio.run(fetch_content_with_playwright(url, "snippet"))
            summary = summarize_with_llama(content)
            scraped_text[url] = summary

        # Fetch image using the new async function
        if url not in scraped_image:
            image_url = asyncio.run(fetch_content_with_playwright(url, "image"))
            
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
