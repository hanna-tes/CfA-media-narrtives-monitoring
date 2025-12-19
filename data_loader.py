# data_loader.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import random
from math import isfinite

# ==================== LLM CLIENT ====================
client = None
try:
    from groq import Groq
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

# ==================== KEYWORD LABELING ====================
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

# ==================== SCRAPING HELPERS ====================
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
                        return full_text[:3000]
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

# ==================== DATA LOADING ====================
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
        df['posting_time'] = (
            pd.to_datetime(df['posting_time'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            .fillna(pd.to_datetime(df['posting_time'], format="%d/%m/%Y %H:%M", errors='coerce'))
        )
        df['scraped_content'] = df['article_text']
        return df
    except Exception as e:
        st.error(f"Failed to load Merged_dataset_sample.csv: {e}")
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
        st.session_state.scraped_data = {}
    if 'url_to_text' not in st.session_state.scraped_data:
        st.session_state.scraped_data['url_to_text'] = {}
    if 'url_to_image' not in st.session_state.scraped_data:
        st.session_state.scraped_data['url_to_image'] = {}
    if 'url_to_summary' not in st.session_state.scraped_data:
        st.session_state.scraped_data['url_to_summary'] = {}
        
    scraped_content = st.session_state.scraped_data['url_to_text']
    scraped_image = st.session_state.scraped_data['url_to_image']
    scraped_summary = st.session_state.scraped_data['url_to_summary']

    needs_content = df['scraped_content'].isnull() | (df['scraped_content'] == '')
    needs_image = ~df['urlToImage'].notna()
    needs_any = (needs_content | needs_image) & df['URL'].notnull()
    urls_to_fetch = df[needs_any]['URL'].dropna().unique()

    if len(urls_to_fetch) == 0:
        df['scraped_content'] = df['URL'].map(scraped_content).fillna(df['scraped_content'])
        df['article_text'] = df['URL'].map(scraped_summary).fillna(df['article_text'])
        df['urlToImage'] = df['URL'].map(scraped_image).fillna(df['urlToImage'])
        return df

    total = len(urls_to_fetch)
    for i, url in enumerate(urls_to_fetch):
        if url not in scraped_content:
            content = fetch_content_with_retry(url, "snippet")
            scraped_content[url] = content
        else:
            content = scraped_content[url]

        if url not in scraped_summary:
            summary = summarize_with_llama(content)
            if summary == "LLM summarization failed.":
                if content and content != "No meaningful content found.":
                    sentences = content.split('.')
                    fallback_summary_parts = [s.strip() for s in sentences if s.strip()]
                    first_sentence = fallback_summary_parts[0] + "." if fallback_summary_parts else ""
                    if len(first_sentence) > 50: 
                        summary = first_sentence
                    else:
                        robust_summary = '. '.join(fallback_summary_parts[:3]) + "."
                        if len(robust_summary) > 50:
                            summary = robust_summary
                        else:
                            summary = content if len(content) > 50 else "No detailed summary available, but article content found."
                else:
                    summary = "No summary available."
            scraped_summary[url] = summary
        
        if url not in scraped_image:
            img_url = fetch_content_with_retry(url, "image")
            if not is_valid_image_url(img_url):
                try:
                    domain = urlparse(url).netloc.replace('www.', '')
                    img_url = f"https://logo.clearbit.com/{domain}"
                except Exception:
                    img_url = 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
            scraped_image[url] = img_url

        if progress_callback:
            progress_callback((i + 1) / total, f"Enriching {i+1}/{total}...")

    st.session_state.scraped_data['url_to_text'] = scraped_content
    st.session_state.scraped_data['url_to_image'] = scraped_image
    st.session_state.scraped_data['url_to_summary'] = scraped_summary

    df['scraped_content'] = df['URL'].map(scraped_content).fillna(df['scraped_content'])
    df['article_text'] = df['URL'].map(scraped_summary).fillna(df['article_text'])
    df['urlToImage'] = df['URL'].map(scraped_image).fillna(df['urlToImage'])

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

# ==================== CONTEXTUAL VULNERABILITY SCORING ====================
# Based on contextual_all_intents_v2.py

COUNTRIES = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
ACTORS = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]

GDP = {
    "Senegal": 33.6e9,
    "DRC": 70.75e9,
    "CoteIvoire": 86.54e9,
    "Ethiopia": 125.0e9
}

DEBT = {
    "China": {"Senegal": 1410666722.69, "DRC": 2029900000.0, "CoteIvoire": 793390000.0, "Ethiopia": 4000000000.0},
    "France": {"Senegal": 280800000.0, "DRC": 0.0, "CoteIvoire": 523800000.0, "Ethiopia": 200000000.0},
    "UnitedStates": {"Senegal": 91500000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0},
    "Russia": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 50000000.0},
    "Rwanda": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.0},
    "Saudi": {"Senegal": 110000000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 50000000.0},
    "UAE": {"Senegal": 65600000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0},
    "Turkey": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 200000000.0},
    "Israel": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 50000000.0},
    "Iran": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0},
    "NonState": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.0},
}

G_RES = {
    "China": {"Senegal": 0.10, "DRC": 0.60, "CoteIvoire": 0.09, "Ethiopia": 0.70},
    "France": {"Senegal": 0.05, "DRC": 0.05, "CoteIvoire": 0.20, "Ethiopia": 0.10},
    "UnitedStates": {"Senegal": 0.40, "DRC": 0.05, "CoteIvoire": 0.0, "Ethiopia": 0.15},
    "Russia": {"Senegal": 0.0, "DRC": 0.10, "CoteIvoire": 0.0, "Ethiopia": 0.10},
    "NonState": {"Senegal": 0.05, "DRC": 0.05, "CoteIvoire": 0.05, "Ethiopia": 0.05},
    "Saudi": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.20},
    "UAE": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.50},
    "Turkey": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.60},
    "Israel": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.10},
    "Iran": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.0},
    "Rwanda": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.0},
}

G_MIL = {
    "China": {"Senegal": 0.33, "DRC": 0.33, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "France": {"Senegal": 0.0, "DRC": 0.33, "CoteIvoire": 0.33, "Ethiopia": 0.0},
    "UnitedStates": {"Senegal": 0.66, "DRC": 0.33, "CoteIvoire": 0.66, "Ethiopia": 0.66},
    "Russia": {"Senegal": 0.0, "DRC": 0.33, "CoteIvoire": 0.10, "Ethiopia": 0.50},
    "Rwanda": {"Senegal": 0.0, "DRC": 0.33, "CoteIvoire": 0.0, "Ethiopia": 0.0},
    "NonState": {"Senegal": 0.0, "DRC": 1.00, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "Saudi": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "UAE": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "Turkey": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "Israel": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "Iran": {"Senegal": 0.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 0.0},
}

FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}
FSI_MIN, FSI_MAX = 22.0, 120.0
FSI_NORM = {c: max(0.0, min(1.0, (FSI_RAW[c] - FSI_MIN) / (FSI_MAX - FSI_MIN))) for c in COUNTRIES}

L = {"Senegal": 0.90, "DRC": 0.20, "CoteIvoire": 0.20, "Ethiopia": 0.95}

ACTOR_DISINFO = {
    "China": {"Senegal": 0.46, "DRC": 0.50, "CoteIvoire": 0.40, "Ethiopia": 0.35},
    "France": {"Senegal": 0.84, "DRC": 0.44, "CoteIvoire": 0.82, "Ethiopia": 0.60},
    "UnitedStates": {"Senegal": 0.58, "DRC": 0.24, "CoteIvoire": 0.34, "Ethiopia": 0.50},
    "Russia": {"Senegal": 0.24, "DRC": 0.50, "CoteIvoire": 0.20, "Ethiopia": 0.65},
    "Rwanda": {"Senegal": 0.12, "DRC": 0.56, "CoteIvoire": 0.12, "Ethiopia": 0.05},
    "Saudi": {"Senegal": 0.25, "DRC": 0.01, "CoteIvoire": 0.02, "Ethiopia": 0.10},
    "UAE": {"Senegal": 0.25, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.60},
    "Turkey": {"Senegal": 0.20, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.40},
    "Israel": {"Senegal": 0.10, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.20},
    "Iran": {"Senegal": 0.08, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
    "NonState": {"Senegal": 0.42, "DRC": 0.64, "CoteIvoire": 0.44, "Ethiopia": 0.55},
}

ACTOR_ELEC = {
    "China": {"Senegal": 0.32, "DRC": 0.50, "CoteIvoire": 0.10, "Ethiopia": 0.40},
    "France": {"Senegal": 0.68, "DRC": 0.08, "CoteIvoire": 0.80, "Ethiopia": 0.60},
    "UnitedStates": {"Senegal": 0.46, "DRC": 0.06, "CoteIvoire": 0.06, "Ethiopia": 0.75},
    "Russia": {"Senegal": 0.10, "DRC": 0.25, "CoteIvoire": 0.01, "Ethiopia": 0.40},
    "Rwanda": {"Senegal": 0.10, "DRC": 0.70, "CoteIvoire": 0.05, "Ethiopia": 0.0},
    "NonState": {"Senegal": 0.02, "DRC": 0.10, "CoteIvoire": 0.05, "Ethiopia": 0.30},
    "Saudi": {"Senegal": 0.05, "DRC": 0.01, "CoteIvoire": 0.01, "Ethiopia": 0.20},
    "UAE": {"Senegal": 0.05, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.50},
    "Turkey": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.20},
    "Israel": {"Senegal": 0.03, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.30},
    "Iran": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
}

ACTOR_LGBTQ = {
    "UnitedStates": {"Senegal": 0.70, "DRC": 0.14, "CoteIvoire": 0.14, "Ethiopia": 0.80},
    "France": {"Senegal": 0.65, "DRC": 0.13, "CoteIvoire": 0.65, "Ethiopia": 0.70},
    "China": {"Senegal": 0.05, "DRC": 0.05, "CoteIvoire": 0.05, "Ethiopia": 0.05},
    "Russia": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
    "NonState": {"Senegal": 0.00, "DRC": 0.00, "CoteIvoire": 0.00, "Ethiopia": 0.00},
    "Saudi": {"Senegal": 0.01, "DRC": 0.01, "CoteIvoire": 0.01, "Ethiopia": 0.01},
    "UAE": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
    "Turkey": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
    "Israel": {"Senegal": 0.01, "DRC": 0.01, "CoteIvoire": 0.01, "Ethiopia": 0.01},
    "Iran": {"Senegal": 0.01, "DRC": 0.01, "CoteIvoire": 0.01, "Ethiopia": 0.01},
    "Rwanda": {"Senegal": 0.02, "DRC": 0.02, "CoteIvoire": 0.02, "Ethiopia": 0.02},
}

INTENT_FACTORS = {
    "Economic": ["debt", "res"],
    "Sovereignty": ["debt", "mil", "elec"],
    "LGBTQ": ["lgbt", "elec"],
    "Religious": ["elec", "mil"],
    "ElectionInforce": ["elec", "debt", "mil"],
    "MilitaryPresence": ["mil", "debt"],
    "ResourceDependency": ["res", "debt"],
    "SocialFragility": ["frag", "debt", "mil"]
}

def clip(x):
    return max(0.0, min(1.0, float(x)))

def presence_factor(a, c):
    if DEBT.get(a, {}).get(c, 0.0) > 0:
        return 1.0
    if G_MIL.get(a, {}).get(c, 0.0) >= 0.33:
        return 1.0
    if G_RES.get(a, {}).get(c, 0.0) >= 0.10:
        return 1.0
    if any([
        G_MIL.get(a, {}).get(c, 0.0) > 0,
        G_RES.get(a, {}).get(c, 0.0) > 0,
        ACTOR_DISINFO.get(a, {}).get(c, 0.0) > 0.15
    ]):
        return 0.5
    return 0.2

def compute_gs():
    g = {a: {c: {} for c in COUNTRIES} for a in ACTORS}
    for a in ACTORS:
        for c in COUNTRIES:
            debt_val = DEBT.get(a, {}).get(c, 0.0)
            g_debt = clip(debt_val / GDP[c]) if GDP[c] > 0 else 0.0
            g_res = G_RES.get(a, {}).get(c, 0.0)
            g_mil = G_MIL.get(a, {}).get(c, 0.0)

            months_to_elec = 3 if c == "CoteIvoire" else 999
            g_elec_time = (1 - min(months_to_elec, 24) / 24) if months_to_elec < 999 else 0.0
            base = 0.25 * presence_factor(a, c)
            elec_index = ACTOR_ELEC.get(a, {}).get(c, 0.0)
            g_elec = elec_index * max(g_elec_time, base)

            lgbt_index = ACTOR_LGBTQ.get(a, {}).get(c, 0.0)
            g_lgbt = (1 - L[c]) * lgbt_index

            disinfo_index = ACTOR_DISINFO.get(a, {}).get(c, 0.0)
            g_frag = FSI_NORM[c] * disinfo_index

            g[a][c] = {
                "debt": g_debt,
                "res": g_res,
                "mil": g_mil,
                "elec": g_elec,
                "lgbt": g_lgbt,
                "frag": g_frag
            }
    return g

def raw_metrics(a, c, g):
    return {
        "debt": DEBT.get(a, {}).get(c, 0.0),
        "mil": G_MIL.get(a, {}).get(c, 0.0),
        "res": G_RES.get(a, {}).get(c, 0.0),
        "elec": g[a][c]["elec"],
        "lgbt": g[a][c]["lgbt"],
        "frag": g[a][c]["frag"]
    }

def compute_R(g):
    R = {a: {c: {} for c in COUNTRIES} for a in ACTORS}
    for a in ACTORS:
        max_per = {}
        for f in ["debt", "mil", "res", "elec", "lgbt", "frag"]:
            vals = [raw_metrics(a, c, g)[f] for c in COUNTRIES]
            max_per[f] = max(v for v in vals if isfinite(v)) if vals else 0.0
        for c in COUNTRIES:
            m = raw_metrics(a, c, g)
            for f in ["debt", "mil", "res", "elec", "lgbt", "frag"]:
                R[a][c][f] = (m[f] / max_per[f]) if max_per[f] > 0 else 0.0
    return R

def compute_CAs(g, R):
    CA = {intent: {a: {c: 0.0 for c in COUNTRIES} for a in ACTORS} for intent in INTENT_FACTORS}
    for intent, factors in INTENT_FACTORS.items():
        for a in ACTORS:
            for c in COUNTRIES:
                denom = sum(R[a][c].get(f, 0.0) for f in factors)
                if denom == 0:
                    w = {f: 1.0 / len(factors) for f in factors}
                else:
                    w = {f: (R[a][c].get(f, 0.0) / denom) for f in factors}
                CA_val = sum(w[f] * g[a][c].get(f, 0.0) for f in factors)
                CA[intent][a][c] = clip(CA_val)
    return CA

@st.cache_resource
def get_vulnerability_system():
    """Compute or return cached vulnerability scores (CA matrix)."""
    g = compute_gs()
    R = compute_R(g)
    CA = compute_CAs(g, R)
    return CA

# Public exports for main.py
#VULNERABILITY_CA = _precompute_vulnerability_system()
