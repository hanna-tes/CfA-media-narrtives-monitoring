# data_loader.py
import streamlit as st
import pandas as pd

# ---------------- LOAD AND TRANSFORM DATA ----------------
@st.cache_data(ttl=86400)
def load_and_transform_data():
    """Load CSV and parse dates."""
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
        df = df.head(100).reset_index(drop=True)  # keep first 100 rows
        st.success(f"✅ Loaded {len(df)} sample articles!")
        return df
    except FileNotFoundError:
        st.error("Merged_dataset_sample.csv not found in repo root!")
        return pd.DataFrame()

# ---------------- FILTER HELPERS ----------------
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
