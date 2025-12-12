# main.py
import streamlit as st
import pandas as pd
from data_loader import (
    load_and_transform_data,
    get_media_names,
    get_countries,
    get_actors
)
from contextual_all_intents_v2 import CA  # Your influence scores

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# ---- Show loading progress during enrichment ----
with st.spinner("Loading and enriching articles..."):
    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(p, msg):
        progress_bar.progress(min(p, 1.0))
        status_text.text(msg)

    df = load_and_transform_data(progress_callback=progress_callback)

progress_bar.empty()
status_text.empty()

if df.empty:
    st.error("No data loaded. Please check merged_dataset.csv.")
    st.stop()

# ---- SIDEBAR FILTERS ----
with st.sidebar:
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", get_media_names())
    selected_country = st.selectbox("Target Country", get_countries())
    selected_actor = st.selectbox("Foreign Actor", get_actors())

    intents = ["All"] + sorted(df['strategic_intent'].dropna().unique())
    selected_intent = st.selectbox("Strategic Intent", intents)

    tones = ["All"] + sorted(df['tone'].dropna().unique())
    selected_tone = st.selectbox("Tone", tones)

# ---- APPLY FILTERS ----
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

# ---- INFLUENCE INDEX ----
st.title("🌍 Vulnerability Index Tool")

@st.cache_data
def get_influence_score(actor, country):
    scores = [CA[i].get(actor, {}).get(country, 0) for i in CA]
    return sum(scores) / len(scores) if scores else 0

if selected_country != "All" and selected_actor != "All":
    avg_score = get_influence_score(selected_actor, selected_country)
    st.metric(
        "Contextual Influence Index",
        f"{avg_score:.2f}",
        help="Composite score (0.0–1.0) based on debt, military, resources, and strategic alignment."
    )
else:
    st.info("Select a Foreign Actor and Target Country to see the Influence Index.")

st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")

# ---- PAGINATION ----
articles_per_page = 6
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)

if "page" not in st.session_state:
    st.session_state.page = 0

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅ Previous") and st.session_state.page > 0:
        st.session_state.page -= 1
with col2:
    st.markdown(f"<p style='text-align: center;'>Page {st.session_state.page + 1} of {total_pages}</p>", unsafe_allow_html=True)
with col3:
    if st.button("Next ➡") and st.session_state.page < total_pages - 1:
        st.session_state.page += 1

start_idx = st.session_state.page * articles_per_page
end_idx = start_idx + articles_per_page
page_articles = filtered.iloc[start_idx:end_idx]

# ---- ARTICLE CARDS ----
for _, row in page_articles.iterrows():
    image_url = row.get('urlToImage', None)
    headline = row.get('headline', 'No headline')
    article_text = row.get('article_text', 'No summary available.')
    media = row.get('media_outlet', 'Unknown')
    posting_time = row['posting_time'].strftime('%Y-%m-%d') if pd.notna(row['posting_time']) else "Date Unknown"

    img_col, text_col = st.columns([1, 4])
    
    with img_col:
        if image_url and isinstance(image_url, str):
            st.image(image_url, width=120, caption=media)
        else:
            st.info("No image")

    with text_col:
        with st.expander(f"**{headline[:100]}...** (Source: {media} - {posting_time})"):
            st.caption(
                f"**Target Country**: {row.get('target_country', 'N/A')} | "
                f"**Foreign Actor**: {row.get('inferred_actor', 'N/A')}"
            )
            st.write(article_text)
            
            st.markdown(
                f"**Tone**: `{row.get('tone', 'N/A')}` | "
                f"**Strategic Intent**: `{row.get('strategic_intent', 'N/A')}`"
            )
            
            url = row.get('URL')
            if url and isinstance(url, str):
                st.markdown(f"[🔗 Read full article]({url})")
    
    st.markdown("---")
