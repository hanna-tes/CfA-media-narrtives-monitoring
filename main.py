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

# 🎨 Custom CSS for dark theme + cards
st.markdown("""
<style>
body {
    background-color: #0e0e0e;
    color: #ffffff;
}
.stApp {
    background-image: url("https://opportunities.codeforafrica.org/wp-content/uploads/sites/5/2015/11/1-Zq7KnTAeKjBf6eENRsacSQ.png");
    background-size: cover;
    background-attachment: fixed;
}
.card {
    background: #1e1e1e;
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    transition: transform 0.2s;
}
.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
}
.image-container img {
    width: 180px;
    height: auto;
    object-fit: cover;
    border-radius: 8px;
    margin-right: 15px;
}
.header {
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 5px;
}
.meta {
    font-size: 0.9em;
    color: #aaa;
    margin-bottom: 10px;
}
.summary {
    font-size: 1em;
    line-height: 1.6;
    margin-bottom: 10px;
}
.tags {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}
.tag {
    background: #2a2a2a;
    color: #4ade80;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}
.link {
    color: #60a5fa;
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# 🖼️ Logo in header
st.image("https://opportunities.codeforafrica.org/wp-content/uploads/sites/5/2015/11/1-Zq7KnTAeKjBf6eENRsacSQ.png", width=150)
st.title("🌍 Vulnerability Index Tool")

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

# Pagination (5 per page)
articles_per_page = 5
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)

if "page" not in st.session_state:
    st.session_state.page = 0

start_idx = st.session_state.page * articles_per_page
end_idx = start_idx + articles_per_page
page_articles = filtered.iloc[start_idx:end_idx]

# Display Articles (no expander, styled card)
for _, row in page_articles.iterrows():
    headline = str(row.get('article_text', 'No headline')).split('.')[0] + "."
    article_text = str(row.get('article_text', 'No summary available.'))
    media = str(row.get('media_outlet', 'Unknown'))
    target_country = str(row.get('target_country', 'N/A'))
    inferred_actor = str(row.get('inferred_actor', 'N/A'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))

    # Format posting time
    posting_time = "Date Unknown"
    if pd.notna(row.get('posting_time')):
        try:
            posting_time = row['posting_time'].strftime('%Y-%m-%d %H:%M')
        except:
            pass

    image_url = row.get('urlToImage', None)

    # 🎨 Render Card
    st.markdown(f"""
    <div class="card">
        <div style="display: flex; align-items: flex-start;">
            <div class="image-container">
                {f'<img src="{image_url}" alt="Article Image">' if image_url and isinstance(image_url, str) else '<div style="width: 180px; height: 120px; background: #333; display: flex; align-items: center; justify-content: center; border-radius: 8px;">No Image</div>'}
            </div>
            <div style="flex: 1;">
                <div class="header">{headline}</div>
                <div class="meta">Source: {media} – {posting_time}</div>
                <div class="summary">{article_text}</div>
                <div class="tags">
                    <span class="tag">Tone: {tone}</span>
                    <span class="tag">Intent: {intent}</span>
                </div>
                <a href="{row.get('URL', '#')}" target="_blank" class="link">🔗 Read full article</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Pagination Controls (at bottom)
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅ Previous", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page - 1)), disabled=(st.session_state.page == 0)):
        pass
with col2:
    st.markdown(f"<h5 style='text-align: center; color: #4A4A4A;'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
with col3:
    if st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1)):
        pass
