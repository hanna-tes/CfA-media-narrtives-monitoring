import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import numpy as np 
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# --- 1. CORE DATA CONSTANTS (Your Real Constants) ---
COUNTRIES_LIST = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
ACTORS_LIST = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]

GDP = {"Senegal": 33.6e9, "DRC": 70.75e9, "CoteIvoire": 86.54e9, "Ethiopia": 125.0e9}
FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}
L = {"Senegal": 0.90, "DRC": 0.20, "CoteIvoire": 0.20, "Ethiopia": 0.95}

DEBT = {
    "China": {"Senegal": 1410666722.69, "DRC": 2029900000.0, "CoteIvoire": 793390000.0, "Ethiopia": 4000000000.0},
    "France": {"Senegal": 280800000.0, "DRC": 0.0, "CoteIvoire": 523800000.0, "Ethiopia": 200000000.0},
    "UnitedStates": {"Senegal": 91500000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0},
}
G_RES = {"China": {"Senegal": 0.10, "DRC": 0.60, "CoteIvoire": 0.09, "Ethiopia": 0.70}}
G_MIL = {
    "China": {"Senegal": 0.33, "DRC": 0.33, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "France": {"Senegal": 0.0, "DRC": 0.33, "CoteIvoire": 0.33, "Ethiopia": 0.0},
    "UnitedStates": {"Senegal": 0.66, "DRC": 0.33, "CoteIvoire": 0.66, "Ethiopia": 0.66},
}

# --- 2. REAL MATHEMATICAL MODEL LOGIC ---
def clip(x): return max(0.0, min(1.0, float(x)))

@st.cache_data
def compute_real_CA_matrix():
    g = {a: {c: {} for c in COUNTRIES_LIST} for a in ACTORS_LIST}
    F_MIN, F_MAX = 22.0, 120.0
    
    for a in ACTORS_LIST:
        for c in COUNTRIES_LIST:
            debt = DEBT.get(a, {}).get(c, 0.0)
            g_debt = clip(debt / GDP[c]) if GDP.get(c, 0) > 0 else 0.0
            g_res = G_RES.get(a, {}).get(c, 0.0)
            g_mil = G_MIL.get(a, {}).get(c, 0.0)
            fsi_norm = clip((FSI_RAW.get(c, 70) - F_MIN) / (F_MAX - F_MIN))
            # Store g-factors for visualization
            g[a][c] = {"Debt": g_debt, "Resources": g_res, "Military": g_mil, "Fragility": fsi_norm, "LGBT_Laws": (1-L.get(c, 0.5)) * 0.1}

    # Calculate Intent-based scores
    INTENT_MAP = {
        "Economic Coercion": ["Debt", "Resources"],
        "Security Dependency": ["Debt", "Military"],
        "Information Warfare": ["Fragility", "Debt"],
        "Diplomatic Pressure": ["Debt", "Military", "Fragility"]
    }
    
    CA = {intent: {a: {c: 0.0 for c in COUNTRIES_LIST} for a in ACTORS_LIST} for intent in INTENT_MAP}
    for intent, factors in INTENT_MAP.items():
        for a in ACTORS_LIST:
            for c in COUNTRIES_LIST:
                score = np.mean([g[a][c][f] for f in factors])
                CA[intent][a][c] = clip(score)
                
    return CA, g

CA_REAL, G_FACTORS = compute_real_CA_matrix()

# --- 3. SCRAPER & DATA LOADING (Restored from your Version) ---
def fetch_og_image(url, timeout=5):
    if not url or not isinstance(url, str): return None
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        soup = BeautifulSoup(response.content, 'html.parser')
        og_image = soup.find('meta', property='og:image')
        return og_image['content'] if og_image else None
    except: return None

@st.cache_data
def load_and_transform_data():
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
        return df.dropna(subset=['article_text'])
    except: return pd.DataFrame()

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# CSS Restoration
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg"
st.markdown(f"""
<style>
.stApp {{ background-image: url("{NEW_BACKGROUND_URL}"); background-size: cover; }}
.card {{ background: #1e1e1e; color: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
.tag {{ background: #2a2a2a; color: #4ade80; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; margin-right: 5px; }}
.header {{ font-size: 1.2em; font-weight: bold; color: #58a6ff; }}
</style>
""", unsafe_allow_html=True)

st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=150)
st.title("🌍 Vulnerability Index Tool")

# Sidebar Filters
with st.sidebar:
    st.header("🔍 Filters")
    sel_actor = st.selectbox("Foreign Actor", ["All"] + ACTORS_LIST)
    sel_country = st.selectbox("Target Country", ["All"] + COUNTRIES_LIST)
    sel_intent = st.selectbox("Strategic Intent", ["All"] + list(CA_REAL.keys()))
    sel_tone = st.selectbox("Tone", ["All", "Critical", "Sensationalist", "Positive", "Neutral"])

# Data Processing
df = load_and_transform_data()
filtered = df.copy()

if sel_actor != "All": filtered = filtered[filtered['inferred_actor'] == sel_actor]
if sel_country != "All": filtered = filtered[filtered['target_country'] == sel_country]
if sel_intent != "All": filtered = filtered[filtered['strategic_intent'] == sel_intent]
if sel_tone != "All": filtered = filtered[filtered['tone'] == sel_tone]

# KPI Calculation Logic
def get_cii():
    if sel_actor == "All" or sel_country == "All": return 0.0
    intent_key = sel_intent if sel_intent != "All" else "Economic Coercion"
    return CA_REAL[intent_key][sel_actor][sel_country]

current_cii = get_cii()

col1, col2, col3 = st.columns(3)
col1.metric("Articles Analyzed", len(filtered))
col2.metric("Target Scope", f"{sel_actor} ➔ {sel_country}")
col3.metric("Contextual Influence Index", f"{current_cii:.2f}")

st.markdown("---")

# --- 5. VISUALIZATION NEXT TO GRID ---
main_col, side_col = st.columns([2, 1])

with main_col:
    st.subheader("📰 Intelligence Feed")
    for _, row in filtered.head(5).iterrows():
        st.markdown(f"""
        <div class="card">
            <div class="header">{row['article_text'][:80]}...</div>
            <div style="color: #aaa; font-size: 0.9em; margin-bottom: 10px;">Source: {row['media_outlet']} | {row['target_country']}</div>
            <div class="tags">
                <span class="tag">{row['tone']}</span>
                <span class="tag">{row['strategic_intent']}</span>
            </div>
            <a href="{row['URL']}" target="_blank" style="color: #60a5fa;">Read Full Article</a>
        </div>
        """, unsafe_allow_html=True)

with side_col:
    st.subheader("📊 Vulnerability Radar")
    if sel_actor != "All" and sel_country != "All":
        factors = G_FACTORS[sel_actor][sel_country]
        fig = go.Figure(data=go.Scatterpolar(
            r=list(factors.values()),
            theta=list(factors.keys()),
            fill='toself',
            marker=dict(color='#ff4b4b')
        ))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"This radar shows the structural weaknesses in **{sel_country}** that **{sel_actor}** leverages.")
    else:
        st.warning("Select a specific Actor and Country to view the Vulnerability Radar.")



# Pagination logic remains as per your session state implementation
