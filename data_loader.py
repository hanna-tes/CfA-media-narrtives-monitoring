# data_loader.py
import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import urllib.request

#release download URL — no spaces!
BASE_URL = "https://github.com/hanna-tes/CfA-media-narrtives-monitoring/releases/download/v1.0"

@st.cache_data(ttl=86400)
def load_and_transform_data():
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    ml_dir = "ml_outputs"
    os.makedirs(ml_dir, exist_ok=True)
    
    # Download dataset
    dataset_path = os.path.join(data_dir, "merged_dataset.csv")
    if not os.path.exists(dataset_path):
        st.info("⏳ Downloading dataset from GitHub Release...")
        urllib.request.urlretrieve(f"{BASE_URL}/merged_dataset.csv", dataset_path)
    df = pd.read_csv(dataset_path)
    
    # Download ML files
    for fname in ["tone_probs_all.npy", "strat_probs_all.npy", "tone_le.pkl", "strat_le.pkl"]:
        local_path = os.path.join(ml_dir, fname)
        if not os.path.exists(local_path):
            st.info(f"⏳ Downloading {fname}...")
            urllib.request.urlretrieve(f"{BASE_URL}/{fname}", local_path)
    
    # Load and apply predictions
    tone_probs = np.load(os.path.join(ml_dir, "tone_probs_all.npy"))
    strat_probs = np.load(os.path.join(ml_dir, "strat_probs_all.npy"))
    with open(os.path.join(ml_dir, "tone_le.pkl"), "rb") as f: tone_le = pickle.load(f)
    with open(os.path.join(ml_dir, "strat_le.pkl"), "rb") as f: strat_le = pickle.load(f)
    
    df['tone'] = tone_le.inverse_transform(tone_probs.argmax(axis=1))
    df['strategic_intent'] = strat_le.inverse_transform(strat_probs.argmax(axis=1))
    
    # Add actor/country (same as before)
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
    
    df['inferred_actor'] = df['text'].apply(extract_actor)
    df['target_country'] = df['text'].apply(extract_country)
    
    # Final: top 80
    df['date_published'] = pd.to_datetime(df.get('publish_date', df.get('date_published')), errors='coerce').dt.date
    df = df.sort_values('date_published', ascending=False).head(80).reset_index(drop=True)
    
    st.success("✅ Top 80 articles loaded!")
    return df

# Filter helpers (same as before)
@st.cache_data(ttl=86400)
def get_media_names():
    df = load_and_transform_data()
    return ["All"] + sorted(df['media_name'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_countries():
    df = load_and_transform_data()
    return ["All"] + sorted(df['target_country'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_actors():
    df = load_and_transform_data()
    return ["All"] + sorted(df['inferred_actor'].dropna().unique().tolist())
