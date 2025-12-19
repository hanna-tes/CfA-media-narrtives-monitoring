import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# --- 1. CORE CONFIGURATION & STYLING ---
st.set_page_config(page_title="Vulnerability Index Tool", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0b0d11; color: #e0e0e0; }
    section[data-testid="stSidebar"] { background-color: #111418 !important; border-right: 1px solid #30363d; }
    div[data-testid="stMetric"] { background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
    
    .article-strip {
        background: #111418; border-left: 3px solid #3067e2;
        padding: 12px 18px; margin-bottom: 8px; border: 1px solid #1f242b;
        display: flex; justify-content: space-between; align-items: center;
    }
    .article-strip:hover { background: #1c2128; border-color: #388bfd; }
    .headline-link { color: #58a6ff; font-size: 1rem; font-weight: 600; text-decoration: none; }
    .meta-text { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; margin-bottom: 4px; }
    
    .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; margin-left: 10px; }
    .badge-critical { background: #442d30; color: #ff7b72; border: 1px solid #f85149; }
    .badge-warning { background: #3e3123; color: #ffa657; border: 1px solid #d29922; }
    .badge-stable { background: #233129; color: #7ee787; border: 1px solid #3fb950; }
    .badge-neutral { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA INPUTS (Your constants) ---
countries = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
actors = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]

GDP = {"Senegal": 33.6e9, "DRC": 70.75e9, "CoteIvoire": 86.54e9, "Ethiopia": 125.0e9}
FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}
L = {"Senegal": 0.90, "DRC": 0.20, "CoteIvoire": 0.20, "Ethiopia": 0.95}

# Debt, Resources, and Military Presence Data
DEBT = {
    "China": {"Senegal": 1410666722.69, "DRC": 2029900000.0, "CoteIvoire": 793390000.0, "Ethiopia": 4000000000.0},
    "France": {"Senegal": 280800000.0, "DRC": 0.0, "CoteIvoire": 523800000.0, "Ethiopia": 200000000.0},
    "UnitedStates": {"Senegal": 91500000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0},
}
G_RES = {
    "China": {"Senegal": 0.10, "DRC": 0.60, "CoteIvoire": 0.09, "Ethiopia": 0.70},
    "France": {"Senegal": 0.05, "DRC": 0.05, "CoteIvoire": 0.20, "Ethiopia": 0.10},
}
G_MIL = {
    "China": {"Senegal": 0.33, "DRC": 0.33, "CoteIvoire": 0.0, "Ethiopia": 0.33},
    "France": {"Senegal": 0.0, "DRC": 0.33, "CoteIvoire": 0.33, "Ethiopia": 0.0},
    "UnitedStates": {"Senegal": 0.66, "DRC": 0.33, "CoteIvoire": 0.66, "Ethiopia": 0.66},
}

# --- 3. MATHEMATICAL MODEL FUNCTIONS ---
def clip(x): return max(0.0, min(1.0, float(x)))

def compute_gs():
    g = {a: {c: {} for c in countries} for a in actors}
    F_MIN, F_MAX = 22.0, 120.0
    for a in actors:
        for c in countries:
            debt = DEBT.get(a, {}).get(c, 0.0)
            g_debt = clip(debt / GDP[c]) if GDP.get(c, 0) > 0 else 0.0
            g_res = G_RES.get(a, {}).get(c, 0.0)
            g_mil = G_MIL.get(a, {}).get(c, 0.0)
            fsi_norm = clip((FSI_RAW.get(c, 70) - F_MIN) / (F_MAX - F_MIN))
            g[a][c] = {"debt": g_debt, "res": g_res, "mil": g_mil, "frag": fsi_norm, "elec": 0.25, "lgbt": (1-L.get(c, 0.5)) * 0.1}
    return g

def compute_R(g):
    R = {a: {c: {} for c in countries} for a in actors}
    factors = ["debt", "mil", "res", "elec", "lgbt", "frag"]
    for a in actors:
        max_per = {f: max([g[a][c].get(f, 0.0) for c in countries]) for f in factors}
        for c in countries:
            for f in factors:
                R[a][c][f] = (g[a][c][f] / max_per[f]) if max_per[f] > 0 else 0.0
    return R

def compute_CAs(g, R):
    INTENT_MAP = {
        "Economic": ["debt", "res"],
        "Sovereignty": ["debt", "mil", "elec"],
        "ElectionInfluence": ["elec", "debt", "mil"],
        "SocialFragility": ["frag", "debt", "mil"]
    }
    CA = {intent: {a: {c: 0.0 for c in countries} for a in actors} for intent in INTENT_MAP}
    for intent, factors in INTENT_MAP.items():
        for a in actors:
            for c in countries:
                denom = sum(R[a][c].get(f, 0.0) for f in factors)
                w = {f: (R[a][c].get(f, 0.0) / denom if denom > 0 else 1.0/len(factors)) for f in factors}
                val = sum(w[f] * g[a][c].get(f, 0.0) for f in factors)
                CA[intent][a][c] = clip(val)
    return CA

# Generate Real Scores
g_data = compute_gs()
r_data = compute_R(g_data)
CA_RESULTS = compute_CAs(g_data, r_data)

# --- 4. SCRAPER & DATA LOADING ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
        return df.dropna(subset=['article_text'])
    except:
        return pd.DataFrame(columns=['media_outlet', 'target_country', 'inferred_actor', 'strategic_intent', 'tone', 'URL', 'article_text'])

def get_display_text(df):
    def extract(text):
        if not isinstance(text, str): return "No content", "No Headline"
        first_sent = re.search(r'[^.?!]*[.?!]', text)
        headline = first_sent.group(0).strip() if first_sent else "Article Snippet"
        return text[:150] + "...", headline
    res = df['article_text'].apply(extract)
    df['summary'] = [r[0] for r in res]
    df['headline'] = [r[1] for r in res]
    return df

# --- 5. DASHBOARD LAYOUT ---
st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=150)
st.title("🌍 Vulnerability Index Tool")

df = load_data()
if not df.empty: df = get_display_text(df)

with st.sidebar:
    st.header("🔍 Intelligence Filters")
    sel_actor = st.selectbox("Foreign Actor", actors)
    sel_country = st.selectbox("Target Country", countries)
    sel_intent = st.selectbox("Strategic Intent", list(CA_RESULTS.keys()))

# Calculations for the Score
current_cii = CA_RESULTS[sel_intent].get(sel_actor, {}).get(sel_country, 0.0)

st.header("📊 Key Indicators")
col1, col2, col3 = st.columns(3)
col1.metric("Actor Under Observation", sel_actor)
col2.metric("Target Country", sel_country)
col3.metric("Contextual Influence Index", f"{current_cii:.4f}")



st.markdown("---")

# Filtered Feed
filtered = df[(df['target_country'] == sel_country) & (df['inferred_actor'] == sel_actor)]

st.subheader(f"📰 Intelligence Feed ({len(filtered)} detections)")
if filtered.empty:
    st.info("No specific articles found for this actor-country pair in the current dataset.")
else:
    for _, row in filtered.head(10).iterrows():
        tone_class = "badge-stable" if row['tone'] == 'Positive' else "badge-warning" if row['tone'] == 'Sensationalist' else "badge-critical"
        st.markdown(f"""
        <div class="article-strip">
            <div style="flex-grow: 1;">
                <div class="meta-text">{row['media_outlet']} | {row['target_country']}</div>
                <a href="{row['URL']}" target="_blank" class="headline-link">{row['headline']}</a>
            </div>
            <div>
                <span class="badge {tone_class}">{row['tone']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
