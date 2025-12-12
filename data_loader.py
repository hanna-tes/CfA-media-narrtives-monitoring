# data_loader.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import random

client = None
try:
    from groq import Groq
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

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

def assign_labels_and_scores(df_articles):
    labels = list(KEYWORD_LABELS.keys()) + ["Factual", "Neutral"]
    for label in labels:
        df_articles[label] = 0.0

    for idx, row in df_articles.iterrows():
        text = str(row.get('article_text', '')).lower()
        found_strong = False
        for label, keywords in KEYWORD_LABELS.items():
            score = sum(0.2 for kw in keywords if f" {kw} " in f" {text} ")
            if score > 0:
                df_articles.at[idx, label] = min(score, 1.0)
                if score >= 0.3:
                    found_strong = True
        if not found_strong:
            df_articles.at[idx, "Factual"] = 0.7 + random.uniform(-0.1, 0.1)
            df_articles.at[idx, "Neutral"] = 0.6 + random.uniform(-0.1, 0.1)

    for label in labels:
        df_articles[label] = df_articles[label].clip(upper=1.0)
    return df_articles

def fetch_content_with_retry(url, fetch_type="snippet", retries=3, delay=1):
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            content_container = soup.find('article') or \
                soup.find('div', class_=['article-body', 'content-body', 'story-content', 'main-content']) or \
                soup.find('main')

            if fetch_type == "snippet":
                if content_container:
                    paras = content_container.find_all('p')
                    full_text = ' '.join([p.get_text(strip=True) for p in paras])
                    if len(full_text) > 50:
                        return full_text[:3000] # Return the raw scraped text
                return "No meaningful content found."

            elif fetch_type == "image":
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                if content_container:
                    img = content_container.find('img', src=True)
                    if img:
                        return urljoin(url, img['src'])
                img = soup.find('img', src=True)
                if img:
                    return urljoin(url, img['src'])
                return None

        except Exception:
            time.sleep(delay * (i + 1))
    return None

def is_valid_image_url(url):
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    blocked = ['logo', 'ad.', 'banner', 'sponsor', 'doubleclick', 'gif', 'svg', 'png?size=', 'taboola', 'youtube', 'favicon', '.ico']
    return all(word not in url_lower for word in blocked)

@st.cache_data(ttl=86400)
def load_raw_data():
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        required_cols = [
            'URL', 'article_text', 'posting_time', 'media_outlet',
            'target_country', 'inferred_actor', 'tone', 'strategic_intent',
            'urlToImage' 
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        # ✅ FIX: Parse posting_time with multiple formats
        df['posting_time'] = (
            pd.to_datetime(df['posting_time'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            .fillna(pd.to_datetime(df['posting_time'], format="%d/%m/%Y %H:%M", errors='coerce'))
        )
        # Add a column for the *original* article text content
        df['scraped_content'] = df['article_text']
        return df
    except Exception as e:
        st.error(f"Failed to load merged_dataset.csv: {e}")
        return pd.DataFrame()

def summarize_with_llama(text):
    if not text or not client or len(text) < 150 or "No meaningful content" in text:
        return "LLM summarization failed." 
    if 'llm_cache' not in st.session_state:
        st.session_state.llm_cache = {}
    if text in st.session_state.llm_cache:
        return st.session_state.llm_cache[text]
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Summarize key points in one concise paragraph (50–80 words). Be factual and neutral."},
                {"role": "user", "content": text}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=120
        )
        summary = chat_completion.choices[0].message.content.strip()
        st.session_state.llm_cache[text] = summary
        return summary
    except Exception:
        return "LLM summarization failed."

def enrich_with_scraping_and_llm(df, progress_callback=None):
    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = {'url_to_text': {}, 'url_to_image': {}, 'url_to_summary': {}}

    scraped_content = st.session_state.scraped_data['url_to_text']
    scraped_image = st.session_state.scraped_data['url_to_image']
    scraped_summary = st.session_state.scraped_data['url_to_summary']

    # Identify articles that need scraping/enrichment
    needs_content = df['scraped_content'].isnull() | (df['scraped_content'] == '')
    needs_image = ~df['urlToImage'].notna()
    needs_any = (needs_content | needs_image) & df['URL'].notnull()
    urls_to_fetch = df[needs_any]['URL'].dropna().unique()

    if len(urls_to_fetch) == 0:
        # Map cached results back
        df['scraped_content'] = df['URL'].map(scraped_content).fillna(df['scraped_content'])
        df['article_text'] = df['URL'].map(scraped_summary).fillna(df['article_text'])
        df['urlToImage'] = df['URL'].map(scraped_image).fillna(df['urlToImage'])
        return df

    total = len(urls_to_fetch)
    for i, url in enumerate(urls_to_fetch):
        # 1. Scrape Content
        if url not in scraped_content:
            content = fetch_content_with_retry(url, "snippet")
            scraped_content[url] = content
        else:
            content = scraped_content[url]

        # 2. Summarize (LLM attempt with robust sentence fallback)
        if url not in scraped_summary:
            summary = summarize_with_llama(content)
            
            if summary == "LLM summarization failed." or summary == "Summary not available.":
                if content and content != "No meaningful content found.":
                    
                    # --- IMPROVED ROBUST FALLBACK LOGIC ---
                    sentences = content.split('.')
                    fallback_summary_parts = [s.strip() for s in sentences if s.strip()]
                    
                    # 1. Attempt to use first sentence
                    first_sentence = fallback_summary_parts[0] + "." if fallback_summary_parts else ""
                    
                    if len(first_sentence) > 50: 
                        summary = first_sentence
                    else:
                        # 2. Use the first two or three sentences
                        robust_summary = '. '.join(fallback_summary_parts[:3]) + "."
                        
                        if len(robust_summary) > 50:
                            summary = robust_summary
                        else:
                            # 3. Final fallback: display whatever meaningful content was found
                            summary = content if len(content) > 50 else "No detailed summary available, but article content found." 
                else:
                    summary = "No summary available."
            # --------------------------------------------
            scraped_summary[url] = summary
        
        # 3. Fetch Image with Clearbit Logo Fallback
        if url not in scraped_image:
            img_url = fetch_content_with_retry(url, "image")
            
            # If the scraped image is not valid or None, use the domain logo
            if not is_valid_image_url(img_url):
                try:
                    domain = urlparse(url).netloc.replace('www.', '')
                    # Set the fallback to the Clearbit Logo URL
                    img_url = f"https://logo.clearbit.com/{domain}"
                except Exception:
                    # Final safety net placeholder
                    img_url = 'https://placehold.co/400x200/cccccc/000000?text=No+Image' 
            
            scraped_image[url] = img_url

        if progress_callback:
            progress_callback((i + 1) / total, f"Enriching {i+1}/{total}...")

    st.session_state.scraped_data['url_to_text'] = scraped_content
    st.session_state.scraped_data['url_to_image'] = scraped_image
    st.session_state.scraped_data['url_to_summary'] = scraped_summary

    # Map the final summary and image back to the DataFrame
    df['scraped_content'] = df['URL'].map(scraped_content).fillna(df['scraped_content'])
    df['article_text'] = df['URL'].map(scraped_summary).fillna(df['article_text']) # article_text now holds the final summary/fallback
    df['urlToImage'] = df['URL'].map(scraped_image).fillna(df['urlToImage'])

    # Final fillna for safety
    df['article_text'].fillna("No summary available.", inplace=True)
    df['urlToImage'].fillna('https://placehold.co/400x200/cccccc/000000?text=No+Image', inplace=True)
    return df

@st.cache_data(ttl=86400)
def load_and_transform_data():
    df = load_raw_data()
    if df.empty:
        return df
    if 'article_text' not in df.columns:
        df['article_text'] = None
    if 'urlToImage' not in df.columns:
        df['urlToImage'] = None
    df = assign_labels_and_scores(df)
    return df

@st.cache_data(ttl=86400)
def get_media_names():
    df = load_raw_data()
    return sorted(df['media_outlet'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_countries():
    df = load_raw_data()
    return sorted(df['target_country'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_actors():
    df = load_raw_data()
    return sorted(df['inferred_actor'].dropna().unique().tolist())
