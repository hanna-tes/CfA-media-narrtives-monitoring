# main.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from data_loader import load_and_transform_data, get_media_names, get_countries, get_actors
from contextual_all_intents_v2 import CA

# --- Page Config ---
st.set_page_config(
    page_title="Geopolitical Influence Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"  # Start with sidebar hidden
)

# --- Custom CSS for Better UI ---
st.markdown("""
<style>
    .main > div { padding-top: 2rem; }
    .stMetric { background-color: #f8f9fa; border-radius: 8px; padding: 1rem; }
    .article-card { border: 1px solid #e0e0e0; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .filter-section { background-color: #f8f9fa; padding: 1rem; border-radius: 8px; }
    .caption-text { color: #666; font-size: 0.95em; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'show_filters' not in st.session_state:
    st.session_state.show_filters = False

# --- Load Data ---
with st.spinner("Loading 15k articles..."):
    df = load_and_transform_data()

if df.empty:
    st.error("❌ No data available. Please check your data source.")
    st.stop()

# --- Toggle Filters Button ---
col1, col2 = st.columns([1, 5])
with col1:
    if st.button("🔍 Toggle Filters", use_container_width=True):
        st.session_state.show_filters = not st.session_state.show_filters

# --- Filters Sidebar (Collapsible) ---
if st.session_state.show_filters:
    with st.sidebar:
        st.title("🛠️ Filters")
        
        selected_media = st.selectbox("Media Outlet", get_media_names())
        selected_country = st.selectbox("Target Country", get_countries())
        selected_actor = st.selectbox("Foreign Actor", get_actors())
        
        intents = ["All"] + sorted(df['strategic_intent'].dropna().unique())
        selected_intent = st.selectbox("Strategic Intent", intents)
        
        tones = ["All"] + sorted(df['tone'].dropna().unique())
        selected_tone = st.selectbox("Tone", tones)
        
        dates = pd.to_datetime(df['date_published'], errors='coerce').dropna()
        min_date = dates.min().date() if not dates.empty else date(2020, 1, 1)
        max_date = dates.max().date() if not dates.empty else date.today()
        timeline = st.slider("Date Range", min_date, max_date, (min_date, max_date))
else:
    # Default: no filters
    selected_media = "All"
    selected_country = "All"
    selected_actor = "All"
    selected_intent = "All"
    selected_tone = "All"
    dates = pd.to_datetime(df['date_published'], errors='coerce').dropna()
    min_date = dates.min().date() if not dates.empty else date(2020, 1, 1)
    max_date = dates.max().date() if not dates.empty else date.today()
    timeline = (min_date, max_date)

# --- Apply Filters ---
filtered = df.copy()
filtered['date_published'] = pd.to_datetime(filtered['date_published'], errors='coerce')
filtered = filtered[
    (filtered['date_published'].dt.date >= timeline[0]) &
    (filtered['date_published'].dt.date <= timeline[1])
]
if selected_media != "All":
    filtered = filtered[filtered['source_name'] == selected_media]
if selected_country != "All":
    filtered = filtered[filtered['target_country'] == selected_country]
if selected_actor != "All":
    filtered = filtered[filtered['inferred_actor'] == selected_actor]
if selected_intent != "All":
    filtered = filtered[filtered['strategic_intent'] == selected_intent]
if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

filtered = filtered.sort_values('date_published', ascending=False).reset_index(drop=True)
total = len(filtered)
total_pages = max(1, (total + 4) // 5)

# --- MAIN CONTENT ---
st.title("🌍 Vulnerablity Index Dashboard")

# --- INFLUENCE INDEX (Top of Main Content) ---
if selected_country != "All" and selected_actor != "All":
    try:
        if selected_actor in CA.get("Economic Dependency", {}):
            scores = [CA[intent].get(selected_actor, {}).get(selected_country, 0) for intent in CA]
            avg_score = np.mean(scores)
            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric(
                    label="Contextual Influence Index",
                    value=f"{avg_score:.2f}",
                    help="Composite score (0.0-1.0) measuring foreign actor influence based on debt, military presence, resources, and media narratives."
                )
            with col2:
                st.caption("ℹ️ **Contextual Influence**: Quantifies strategic impact using real-world indicators and media narrative alignment from ML models.")
    except Exception as e:
        st.error("Influence index unavailable")

# --- Results Header ---
st.write(f"### 📊 Showing {min(total, (st.session_state.current_page-1)*5+1)}–{min(st.session_state.current_page*5, total)} of {total} articles")

# --- HELP SECTION ---
with st.expander("ℹ️ How to use this dashboard", expanded=False):
    st.write("""
    - **Step 1**: Click "Toggle Filters" to select a *Target Country* and *Foreign Actor*  
    - **Step 2**: View the **Contextual Influence Index** (0.0–1.0) at the top  
    - **Step 3**: Filter by *Tone* (Alarmist, Factual) or *Strategic Intent* (Economic Dependency, etc.)  
    - **Step 4**: Read article summaries to understand real-world context
    """)

# --- ARTICLE CARDS ---
for _, row in filtered.iloc[(st.session_state.current_page-1)*5 : st.session_state.current_page*5].iterrows():
    with st.container():
        st.markdown('<div class="article-card">', unsafe_allow_html=True)
        
        # Headline & Source
        st.markdown(f"### [{row['headline']}]({row['url']})")
        st.caption(f"**Source**: {row['source_name'] if pd.notna(row['source_name']) else 'Unknown'}")
        
        # Metadata
        st.caption(f"📅 {row['date_published']}")
        st.caption(f"**Target Country**: {row['target_country']} | **Foreign Actor**: {row['inferred_actor']}")
        
        # Summary
        summary = row['text'] if pd.notna(row['text']) else "No summary available."
        st.write(summary)
        
        # ML Predictions
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Tone**: `{row['tone']}`")
        with col2:
            st.markdown(f"**Strategic Intent**: `{row['strategic_intent']}`")
        
        # Per-article influence (if applicable)
        if (row['inferred_actor'] != "Unknown" and 
            row['target_country'] != "Unknown" and
            selected_country != "All" and selected_actor != "All"):
            actor, country, intent = row['inferred_actor'], row['target_country'], row['strategic_intent']
            if intent in CA and actor in CA[intent] and country in CA[intent][actor]:
                influence = CA[intent][actor][country]
                st.metric("Article Influence Score", f"{influence:.2f}")
        
        # Image (if available)
        img_url = row.get('urlToImage') or 'https://placehold.co/400x200?text=No+Image'
        try:
            st.image(img_url, use_column_width=True)
        except:
            st.image('https://placehold.co/400x200?text=Image+Error', use_column_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()

# --- PAGINATION ---
if total_pages > 1:
    cols = st.columns([1, 2, 1])
    with cols[0]:
        if st.button("⬅️ Previous", disabled=st.session_state.current_page == 1):
            st.session_state.current_page = max(1, st.session_state.current_page - 1)
            st.rerun()
    with cols[1]:
        st.markdown(f"<center style='padding: 10px;'>Page {st.session_state.current_page} of {total_pages}</center>", unsafe_allow_html=True)
    with cols[2]:
        if st.button("Next ➡️", disabled=st.session_state.current_page == total_pages):
            st.session_state.current_page = min(total_pages, st.session_state.current_page + 1)
            st.rerun()
