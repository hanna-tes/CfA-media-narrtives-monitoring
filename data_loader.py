# data_loader.py
import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import urllib.request
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- Configuration ---
LOCAL_DATA_FILE = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/refs/heads/main/south-africa-or-nigeria-or-all-story-urls-20250829083045.csv"

# --- Actor & Country Lists ---
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

# --- ML Model Loading from GitHub Release ---
def load_ml_artifacts():
    ml_dir = "ml_outputs"
    os.makedirs(ml_dir, exist_ok=True)
    
    # REPLACE THIS WITH YOUR ACTUAL GITHUB URL
    BASE_URL = "https://github.com/hanna-tes/CfA-media-narrtives-monitoring/releases/tag/v1.0"
    files = {
        "tone_probs_all.npy": f"{BASE_URL}/tone_probs_all.npy",
        "tone_le.pkl": f"{BASE_URL}/tone_le.pkl",
        "strat_probs_all.npy": f"{BASE_URL}/strat_probs_all.npy",
        "strat_le.pkl": f"{BASE_URL}/strat_le.pkl"
    }
    
    # Download missing files
    for filename, url in files.items():
        local_path = os.path.join(ml_dir, filename)
        if not os.path.exists(local_path):
            st.info(f"⏳ Downloading {filename} (one-time, ~25MB total)...")
            try:
                urllib.request.urlretrieve(url, local_path)
            except Exception as e:
                st.error(f"❌ Download failed for {filename}: {e}")
                return None, None, None, None
    
    # Load files
    try:
        tone_probs = np.load(os.path.join(ml_dir, "tone_probs_all.npy"))
        with open(os.path.join(ml_dir, "tone_le.pkl"), "rb") as f:
            tone_le = pickle.load(f)
        strat_probs = np.load(os.path.join(ml_dir, "strat_probs_all.npy"))
        with open(os.path.join(ml_dir, "strat_le.pkl"), "rb") as f:
            strat_le = pickle.load(f)
        return tone_le, strat_le, tone_probs, strat_probs
    except Exception as e:
        st.error(f"❌ Failed to load ML artifacts: {e}")
        return None, None, None, None

# --- Core Data Loading ---
@st.cache_data(ttl=7200)
def load_and_transform_data():
    # Load raw data
    try:
        df = pd.read_csv(LOCAL_DATA_FILE)
        df.rename(columns={
            'title': 'headline',
            'publish_date': 'date_published',
            'media_name': 'source_name'
        }, inplace=True)
        df['date_published'] = pd.to_datetime(df['date_published'], errors='coerce').dt.date
    except Exception as e:
        st.error(f"❌ Failed to load raw  {e}")
        return pd.DataFrame()
    
    # Load ML predictions
    tone_le, strat_le, tone_probs, strat_probs = load_ml_artifacts()
    if tone_probs is not None and len(tone_probs) == len(df):
        df['tone'] = tone_le.inverse_transform(tone_probs.argmax(axis=1))
        df['strategic_intent'] = strat_le.inverse_transform(strat_probs.argmax(axis=1))
    else:
        df['tone'] = "Factual"
        df['strategic_intent'] = "Economic Dependency"
    
    # Add actor & country
    df['inferred_actor'] = df['text'].apply(extract_actor)
    df['target_country'] = df['text'].apply(extract_country)
    
    # Ensure required columns
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
