# data_loader.py
import streamlit as st
import pandas as pd

@st.cache_data(ttl=86400)
def load_and_transform_data():
    # Load your sample CSV (already in repo root)
    df = pd.read_csv("Merged_dataset_sample.csv")
    
    # Ensure date parsing
    df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
    
    # Keep top 100 articles (or all if < 100)
    df = df.head(100).reset_index(drop=True)
    
    st.success(f"✅ Loaded {len(df)} sample articles!")
    return df

# Filter helpers
@st.cache_data(ttl=86400)
def get_media_names():
    df = load_and_transform_data()
    return ["All"] + sorted(df['media_outlet'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_countries():
    df = load_and_transform_data()
    return ["All"] + sorted(df['target_country'].dropna().unique().tolist())

@st.cache_data(ttl=86400)
def get_actors():
    df = load_and_transform_data()
    return ["All"] + sorted(df['inferred_actor'].dropna().unique().tolist())
