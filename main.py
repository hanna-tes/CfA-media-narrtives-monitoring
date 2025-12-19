import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import numpy as np 
from urllib.parse import urlparse, urljoin

# NOTE: Keeping your required libraries and scraper logic intact
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    st.error("Missing libraries: Please install 'requests' and 'beautifulsoup4' to enable image scraping.")
    requests = None
    BeautifulSoup = None

# --- [PASTE YOUR SCRAPER FUNCTIONS & MOCK LOGIC HERE - UNCHANGED] ---
# (fetch_og_image, is_valid_image_url, INTENT_FACTORS, mock_compute_gs, etc.)
# I am skipping the re-print of those functions for brevity, but they stay in your file.

def fetch_og_image(url, timeout=10):
    if not requests or not BeautifulSoup: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=timeout)
        soup = BeautifulSoup(response.content, 'html.parser')
        og_image = soup.find('meta', property='og:image')
        return og_image['content'] if og_image else None
    except: return None

def is_valid_image_url(url):
    if not url: return False
    blocked = ['logo', 'ad.', 'banner', 'gif', 'svg']
    return all(word not in url.lower() for word in blocked)

INTENT_FACTORS = {
    'Diplomatic Pressure': {'Economic Dependency': 0.7, 'Security Dependency': 0.3},
    'Economic Coercion': {'Economic Dependency': 0.9, 'Resource Dependence': 0.5},
    'Information Warfare': {'Social Fragility': 0.8, 'Media Literacy': 0.2},
    'Security Dependency': {'Military Presence': 0.9, 'Debt Vulnerability': 0.4}
}

def mock_compute_gs():
    return {
        'Senegal': {'Debt Vulnerability': 0.6, 'Military Presence': 0.3, 'Resource Dependence': 0.5, 'Social Fragility': 0.4, 'Media Literacy': 0.5, 'Economic Dependency': 0.7},
        'Ethiopia': {'Debt Vulnerability': 0.9, 'Military Presence': 0.7, 'Resource Dependence': 0.8, 'Social Fragility': 0.9, 'Media Literacy': 0.4, 'Economic Dependency': 0.6},
        'Nigeria': {'Debt Vulnerability': 0.5, 'Military Presence': 0.4, 'Resource Dependence': 0.9, 'Social Fragility': 0.8, 'Media Literacy': 0.6, 'Economic Dependency': 0.5},
    }

def mock_compute_R(g):
    actors, countries = ['China', 'Rwanda', 'Turkey', 'Russia'], list(g.keys())
    R_mock = {}
    for intent in INTENT_FACTORS:
        R_mock[intent] = {actor: {country: np.random.rand() * 0.8 + 0.1 for country in countries} for actor in actors}
    return R_mock

def mock_compute_CAs(g, R):
    CA_mock = {}
    actors = ['China', 'Rwanda', 'Turkey', 'Russia']
    for intent, factors in INTENT_FACTORS.items():
        CA_mock[intent] = {}
        for actor in actors:
            CA_mock[intent][actor] = {}
            for country, g_factors in g.items():
                score = sum(R[intent][actor][country] * g_factors.get(f, 0) * w for f, w in factors.items())
                max_w = sum(factors.values())
                CA_mock[intent][actor][country] = min(score / max_w, 1.0)
    return CA_mock

g = mock_compute_gs()
R = mock_compute_R(g)
CA = mock_compute_CAs(g,R)

# --- DATA LOADER ---
@st.cache_data
def load_and_transform_data():
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
        df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
        return df.dropna(subset=['article_text'])
    except:
        return pd.DataFrame()

# --- STYLING ---
st.set_page_config(page_title="CFA | Vulnerability Index", layout="wide")

st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stMetric { 
        background-color: #ffffff; 
        border: 1px solid #e2e8f0; 
        padding: 15px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .article-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .tag-blue { background: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; }
    .tag-red { background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; }
    .headline { font-size: 1.15rem; font-weight: 700; color: #1e293b; text-decoration: none; }
    .headline:hover { color: #3b82f6; }
</style>
""", unsafe_allow_html=True)

# --- START APP ---
col_l, col_r = st.columns([1, 4])
with col_l:
    st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=120)
with col_r:
    st.title("🌍 Vulnerability Index Dashboard")

df = load_and_transform_data()
if df.empty: st.stop()

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🔍 Filters")
    selected_actor = st.selectbox("Foreign Actor", ["All"] + sorted(list(df['inferred_actor'].dropna().unique())))
    selected_country = st.selectbox("Target Country", ["All"] + sorted(list(df['target_country'].dropna().unique())))
    selected_intent = st.selectbox("Strategic Intent", ["All"] + list(INTENT_FACTORS.keys()))

# --- FILTER LOGIC ---
filtered = df.copy()
if selected_actor != "All": filtered = filtered[filtered['inferred_actor'] == selected_actor]
if selected_country != "All": filtered = filtered[filtered['target_country'] == selected_country]
if selected_intent != "All": filtered = filtered[filtered['strategic_intent'] == selected_intent]

# --- METRIC CALCULATIONS ---
# (Keeping your specific math for CII and Sentiment)
tone_mapping = {'Factual': 0, 'Sensationalist': -0.3, 'Alarmist': -1.0, 'Positive': 1.0}
filtered['tone_numeric'] = filtered['tone'].map(tone_mapping).fillna(0)
avg_tone = filtered['tone_numeric'].mean() if not filtered.empty else 0

# CII Score Calculation
def get_cii(actor, country, intent):
    if actor == "All" or country == "All": return 0.0
    if intent != "All": return CA.get(intent, {}).get(actor, {}).get(country, 0.0)
    scores = [CA[i].get(actor, {}).get(country, 0) for i in CA]
    return sum(scores)/len(scores) if scores else 0

cii_val = get_cii(selected_actor, selected_country, selected_intent)

# --- DISPLAY KPIS ---
c1, c2, c3 = st.columns(3)
c1.metric("Articles Detected", len(filtered))
c2.metric("Average Tone", f"{avg_tone:.2f}")
c3.metric("Influence Index (CII)", f"{cii_val:.2f}")

# --- NEW ANALYTIC: RISK HEATMAP ---
st.markdown("### 📊 Regional Risk Distribution")
if selected_intent != "All":
    heat_data = []
    for actor, countries in CA[selected_intent].items():
        for country, val in countries.items():
            heat_data.append({"Actor": actor, "Country": country, "Risk": val})
    
    fig_heat = px.density_heatmap(pd.DataFrame(heat_data), x="Country", y="Actor", z="Risk", 
                                  color_continuous_scale="Reds", text_auto=True)
    st.plotly_chart(fig_heat, use_container_width=True)

# --- RESULTS FEED ---
st.markdown(f"### 📰 Narrative Feed ({len(filtered)} articles)")

# Pagination Logic
limit = 5
page = st.number_input("Page", min_value=1, value=1)
start_idx = (page - 1) * limit
page_df = filtered.iloc[start_idx : start_idx + limit]

for _, row in page_df.iterrows():
    img = row.get('urlToImage', 'https://placehold.co/200x120?text=No+Image')
    st.markdown(f"""
    <div class="article-card">
        <div style="display: flex; gap: 20px;">
            <img src="{img}" style="width: 180px; height: 110px; border-radius: 8px; object-fit: cover;">
            <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between;">
                    <span class="tag-blue">{row['media_outlet']}</span>
                    <span style="font-size: 12px; color: #64748b;">{row['posting_time']}</span>
                </div>
                <div style="margin: 8px 0;">
                    <a href="{row['URL']}" class="headline" target="_blank">{row['article_text'][:80]}...</a>
                </div>
                <div style="font-size: 14px; color: #475569; margin-bottom: 10px;">
                    {row['article_text'][:180]}...
                </div>
                <div>
                    <span class="tag-red">Intent: {row['strategic_intent']}</span>
                    <span class="tag-blue" style="background:#f1f5f9; color:#475569">Tone: {row['tone']}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
