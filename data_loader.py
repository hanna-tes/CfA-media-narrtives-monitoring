# data_loader.py
import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from groq import Groq

# --- Configuration ---
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250829083045.csv"
ML_OUTPUTS_DIR = "ml_outputs"  # Folder with your .npy and .pkl files

# --- Actor & Country Lists (from contextual_all_intents_v2.py) ---
ACTORS = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]
COUNTRIES = ["Senegal", "DRC", "CoteIvoire", "Ethiopia", "South Africa"]

def extract_actor(text):
    if pd.isna(text): return "Unknown"
    text_lower = str(text).lower()
    for actor in ACTORS:
        if actor.replace("UnitedStates", "US").lower() in text_lower:
            return actor
    return "Unknown"

def extract_country(text):
    if pd.isna(text): return "Unknown"
    text_lower = str(text).lower()
    for country in COUNTRIES:
        if country.lower() in text_lower or (country == "DRC" and "congo" in text_lower):
            return country
    return "Unknown"

# --- Groq Setup ---
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

# --- Web Scraping (simplified for speed) ---
def fetch_content_with_retry(url, fetch_type="snippet", retries=2):
    headers = {'User-Agent': 'Mozilla/5.0 ...'}
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                content = soup.find('article') or soup.find('div', class_=lambda x: x and 'content' in x.lower())
                if fetch_type == "snippet":
                    if content:
                        text = ' '.join(p.get_text() for p in content.find_all('p'))
                        return text[:2000] if len(text) > 50 else "No content"
                elif fetch_type == "image":
                    img = soup.find('meta', property='og:image')
                    if img: return img.get('content')
        except: pass
    return None if fetch_type == "image" else "Fetch failed"

# --- Core Data Loading ---
@st.cache_data(ttl=7200)  # Cache for 2 hours
def load_and_transform_data():
    # Load raw data
    df = pd.read_csv(LOCAL_DATA_FILE)
    df.rename(columns={
        'title': 'headline',
        'publish_date': 'date_published',
        'media_name': 'source_name'
    }, inplace=True)
    df['date_published'] = pd.to_datetime(df['date_published'], errors='coerce').dt.date

    # Load ML outputs
    try:
        tone_probs = np.load(os.path.join(ML_OUTPUTS_DIR, "tone_probs_all.npy"))
        strat_probs = np.load(os.path.join(ML_OUTPUTS_DIR, "strat_probs_all.npy"))
        with open(os.path.join(ML_OUTPUTS_ONEDRIVE, "tone_le.pkl"), "rb") as f:
            tone_le = pickle.load(f)
        with open(os.path.join(ML_OUTPUTS_DIR, "strat_le.pkl"), "rb") as f:
            strat_le = pickle.load(f)
        
        # Add predictions
        df['tone'] = tone_le.inverse_transform(tone_probs.argmax(axis=1))
        df['strategic_intent'] = strat_le.inverse_transform(strat_probs.argmax(axis=1))
    except Exception as e:
        st.error(f"ML outputs loading failed: {e}")
        df['tone'] = "Factual"
        df['strategic_intent'] = "Economic Dependency"

    # Add actor & country
    df['inferred_actor'] = df['text'].apply(extract_actor)
    df['target_country'] = df['text'].apply(extract_country)
    
    # Ensure required columns exist
    for col in ['url', 'headline', 'text', 'source_name']:
        if col not in df.columns:
            df[col] = "N/A"
    
    return df.reset_index(drop=True)

@st.cache_data(ttl=7200)
def get_media_names():
    df = load_and_transform_data()
    return ["All"] + sorted(df['source_name'].dropna().unique().tolist())

@st.cache_data(ttl=7200)
def get_countries():
    df = load_and_transform_data()
    return ["All"] + sorted(df['target_country'].dropna().unique().tolist())

@st.cache_data(ttl=7200)
def get_actors():
    df = load_and_transform_data()
    return ["All"] + sorted(df['inferred_actor'].dropna().unique().tolist())

def summarize_with_llama(text):
    if not client or not text or len(text) < 100:
        return "Summary not available."
    if text in st.session_state.get("llm_cache", {}):
        return st.session_state["llm_cache"][text]
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": "Summarize in one neutral paragraph (50-80 words)."},
                      {"role": "user", "content": text}],
            model="llama-3.1-8b-instant",
            max_tokens=100
        )
        summary = response.choices[0].message.content.strip()
        st.session_state.setdefault("llm_cache", {})[text] = summary
        return summary
    except:
        return "Summary not available."
