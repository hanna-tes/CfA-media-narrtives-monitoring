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
# Assuming CA is available from this import
from contextual_all_intents_v2 import CA 

# --- NEW BACKGROUND AND LOGO ---
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0=" 
# Using a clearly visible logo
BRIGHT_LOGO_URL = "https://opportunities.codeforafrica.org/wp-content/uploads/sites/5/2023/12/CfA-Logo-White-Green.png" 


# 🎨 Custom CSS for theme-aware dark cards
st.markdown(f"""
<style>
/* -------------------- THEME AWARE STYLES -------------------- */
/* Set background image for the app */
.stApp {{
    background-image: url("{NEW_BACKGROUND_URL}");
    background-size: cover;
    background-attachment: fixed;
}}
/* Ensure main text elements use Streamlit's theme color for visibility */
h1, h2, h3, h4, h5, h6, .css-1d3w5av, .stAlert p, .stMarkdown, .stMetric .css-1ndc21z, .stMetric .css-1ndc21z > div:first-child {{ 
    color: var(--text-color) !important; 
}}

/* -------------------- CARD-SPECIFIC STYLES (Always Dark) -------------------- */
.card {{
    background: #1e1e1e; /* Dark card background */
    color: #ffffff; /* White text inside dark card */
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    transition: transform 0.2s;
}}
.card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
}}
.image-container img {{
    width: 180px;
    height: auto;
    object-fit: cover;
    border-radius: 8px;
    margin-right: 15px;
}}
.header {{
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 5px;
}}
.meta {{
    font-size: 0.9em;
    color: #aaa;
    margin-bottom: 10px;
}}
.summary {{
    font-size: 1em;
    line-height: 1.6;
    margin-bottom: 10px;
}}
.tags {{
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}}
.tag {{
    background: #2a2a2a;
    color: #4ade80;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}}
.link {{
    color: #60a5fa;
    text-decoration: underline;
}}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# 🖼️ Logo in header 
st.image(BRIGHT_LOGO_URL, width=150)
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
    # Ensuring "All" is available for selections
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
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

# Influence Index Logic Fix
@st.cache_data
def get_influence_score(actor, country):
    if not actor or not country or not CA:
        return 0.0
        
    # FIX: Normalize input case using .title() to match the TitleCase keys in contextual_all_intents_v2.py
    # This converts "united states" to "United States", which is a key in your data.
    # We strip 'All' first just in case it somehow makes it through.
    actor_normalized = actor.title() if actor != 'All' else actor
    country_normalized = country.title() if country != 'All' else country
    
    # Calculate the sum of scores across all intents (i)
    scores = [CA[i].get(actor_normalized, {}).get(country_normalized, 0) for i in CA]
    
    # Calculate average score
    return sum(scores) / len(CA) if CA else 0.0

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

# Display Articles 
for _, row in page_articles.iterrows():
    
    article_text = str(row.get('article_text', 'No summary available.'))
    image_url = row.get('urlToImage', None)

    headline = article_text.split('.')[0] + "." if article_text and article_text != 'No summary available.' else "No Headline Available"
    
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

    # Image rendering logic
    display_image = image_url if image_url and isinstance(image_url, str) else 'https://placehold.co/400x200/cccccc/000000?text=No+Image'

    # 🎨 Render Card
    st.markdown(f"""
    <div class="card">
        <div style="display: flex; align-items: flex-start;">
            <div class="image-container">
                {f'<img src="{display_image}" alt="Article Image">' if 'No+Image' not in display_image else '<div style="width: 180px; height: 120px; background: #333; display: flex; align-items: center; justify-content: center; border-radius: 8px;">No Image</div>'}
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
    st.markdown(f"<h5 style='text-align: center; color: var(--text-color);'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
with col3:
    if st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1)):
        pass
