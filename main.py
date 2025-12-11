# main.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from data_loader import load_and_transform_data, get_media_names, get_countries, get_actors
from contextual_all_intents_v2 import CA  # Your influence scores

st.set_page_config(page_title="Geopolitical Influence Dashboard", layout="wide")

# --- Initialize session state ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

# --- Load data (with progress) ---
with st.spinner("Loading 15k articles..."):
    df = load_and_transform_data()

if df.empty:
    st.error("No data loaded")
    st.stop()

# --- Sidebar Filters ---
with st.sidebar:
    st.title("🔍 Filters")
    
    # Media outlet
    selected_media = st.selectbox("Media Outlet", get_media_names())
    
    # Target country
    selected_country = st.selectbox("Target Country", get_countries())
    
    # Foreign actor
    selected_actor = st.selectbox("Foreign Actor", get_actors())
    
    # Strategic intent
    intents = ["All"] + sorted(df['strategic_intent'].dropna().unique())
    selected_intent = st.selectbox("Strategic Intent", intents)
    
    # Tone
    tones = ["All"] + sorted(df['tone'].dropna().unique())
    selected_tone = st.selectbox("Tone", tones)
    
    # Date range
    dates = pd.to_datetime(df['date_published'], errors='coerce').dropna()
    min_date = dates.min().date() if not dates.empty else date(2020, 1, 1)
    max_date = dates.max().date() if not dates.empty else date.today()
    timeline = st.slider("Date Range", min_date, max_date, (min_date, max_date))
    
    # Influence Index
    st.divider()
    if selected_country != "All" and selected_actor != "All":
        try:
            if selected_actor in CA.get("Economic Dependency", {}):
                scores = [CA[intent].get(selected_actor, {}).get(selected_country, 0) 
                         for intent in CA]
                avg_score = np.mean(scores)
                st.metric("Influence Index", f"{avg_score:.2f}")
        except Exception as e:
            st.error("Index error")

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

# --- Display Results ---
st.title("🌍 Geopolitical Influence Dashboard")
st.write(f"Showing {min(total, (st.session_state.current_page-1)*5+1)}–{min(st.session_state.current_page*5, total)} of {total} articles")

# Article cards
for _, row in filtered.iloc[(st.session_state.current_page-1)*5 : st.session_state.current_page*5].iterrows():
    col1, col2 = st.columns([1, 2])
    with col1:
        img = row.get('urlToImage') or 'https://placehold.co/400x200'
        st.image(img, use_column_width=True)
        st.caption(row['source_name'] if pd.notna(row['source_name']) else "Unknown")
    with col2:
        st.markdown(f"### [{row['headline']}]({row['url']})")
        st.caption(f"📅 {row['date_published']} | 🌍 {row['target_country']} | 🕵️ {row['inferred_actor']}")
        st.write(row['text'] if pd.notna(row['text']) else "No summary.")
        st.markdown(f"**Tone**: {row['tone']} | **Intent**: {row['strategic_intent']}")
        
        # Per-article influence score
        if row['inferred_actor'] != "Unknown" and row['target_country'] != "Unknown":
            actor, country, intent = row['inferred_actor'], row['target_country'], row['strategic_intent']
            if intent in CA and actor in CA[intent] and country in CA[intent][actor]:
                influence = CA[intent][actor][country]
                st.metric("Contextual Influence", f"{influence:.2f}")
    st.divider()

# Pagination
if total_pages > 1:
    cols = st.columns([1, 2, 1])
    with cols[0]:
        if st.button("⬅️ Previous") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with cols[1]:
        st.markdown(f"<center>Page {st.session_state.current_page} of {total_pages}</center>", unsafe_allow_html=True)
    with cols[2]:
        if st.button("Next ➡️") and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
            st.rerun()
