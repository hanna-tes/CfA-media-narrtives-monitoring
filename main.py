# main.py
import streamlit as st
import pandas as pd
from data_loader import (
    load_and_transform_data,
    enrich_with_scraping_and_llm,
    get_media_names,
    get_countries,
    get_actors
)
from contextual_all_intents_v2 import CA

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# Load base data
with st.spinner("Loading dataset..."):
    df_base = load_and_transform_data()
if df_base.empty:
    st.error("No data loaded. Please check merged_dataset.csv.")
    st.stop()

# Enrich with scraping
with st.spinner("Enriching articles..."):
    progress_bar = st.progress(0)
    status_text = st.empty()
    def progress_callback(p, msg):
        progress_bar.progress(min(p, 1.0))
        status_text.text(msg)
    df = enrich_with_scraping_and_llm(df_base, progress_callback=progress_callback)
progress_bar.empty()
status_text.empty()

# Sidebar filters
with st.sidebar:
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", get_media_names())
    selected_country = st.selectbox("Target Country", get_countries())
    selected_actor = st.selectbox("Foreign Actor", get_actors())
    intents = ["All"] + sorted(df['strategic_intent'].dropna().unique())
    selected_intent = st.selectbox("Strategic Intent", intents)
    tones = ["All"] + sorted(df['tone'].dropna().unique())
    selected_tone = st.selectbox("Tone", tones)

# Apply filters
filtered = df.copy()
if selected_media != "All":
    filtered = filtered[filtered['media_outlet'] == selected_media]
if selected_country != "All":
    filtered = filtered[filtered['target_country'] == selected_country]
if selected_actor != "All":
    filtered = filtered[filtered['inferred_actor'] == selected_actor]
if selected_intent != "All":
    filtered = filtered[filtered['strategic_intent'] == selected_intent]
if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

# Influence Index
st.title("🌍 Vulnerability Index Tool")

@st.cache_data
def get_influence_score(actor, country):
    scores = [CA[i].get(actor, {}).get(country, 0) for i in CA]
    return sum(scores) / len(scores) if scores else 0

if selected_country != "All" and selected_actor != "All":
    avg_score = get_influence_score(selected_actor, selected_country)
    st.metric("Contextual Influence Index", f"{avg_score:.2f}")
else:
    st.info("Select a Foreign Actor and Target Country to see the Influence Index.")

st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")

# Article cards
for _, row in filtered.iterrows():
    url = row.get('URL') or '#'
    article_text = str(row.get('article_text', 'No summary available.'))
    media = str(row.get('media_outlet', 'Unknown'))
    target_country = str(row.get('target_country', 'N/A'))
    inferred_actor = str(row.get('inferred_actor', 'N/A'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))
    
    # ✅ Use first sentence as headline
    headline = article_text.split('.')[0][:150] + ("" if len(article_text.split('.')[0]) <= 150 else "...")

    posting_time = "Date Unknown"
    if pd.notna(row.get('posting_time')):
        try:
            posting_time = row['posting_time'].strftime('%Y-%m-%d')
        except:
            pass

    image_url = row.get('urlToImage', None)

    img_col, text_col = st.columns([1, 4])
    with img_col:
        if image_url and isinstance(image_url, str):
            st.image(image_url, width=120, caption=media)
        else:
            st.info("No image")
    with text_col:
        with st.expander(f"**{headline}** (Source: {media} – {posting_time})"):
            st.caption(f"**Target Country**: {target_country} | **Foreign Actor**: {inferred_actor}")
            st.write(article_text)
            st.markdown(f"**Tone**: `{tone}` | **Strategic Intent**: `{intent}`")
            st.markdown(f"[🔗 Read full article]({url})")
    st.markdown("---")

# Pagination at bottom
articles_per_page = 6
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)

if "page" not in st.session_state:
    st.session_state.page = 0

if total_pages > 1:
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.button("⬅ Previous", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page - 1)), disabled=(st.session_state.page == 0))
    with col2:
        st.markdown(f"<h5 style='text-align: center; color: #4A4A4A;'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
    with col3:
        st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1))
