import streamlit as st
import pandas as pd
# Import the new scraping function
from data_loader import (
    load_and_transform_data, 
    get_media_names, 
    get_countries, 
    get_actors,
    scrape_og_image # <-- New import
)
from contextual_all_intents_v2 import CA  # Your influence scores

# ----------------------------------------------------------
#  PAGE CONFIG (Background Image Removed)
# ----------------------------------------------------------
st.set_page_config(
    page_title="Vulnerability Index Tool",
    layout="wide"
)

# ----------------------------------------------------------
#  LOAD DATA
# ----------------------------------------------------------
df = load_and_transform_data()

# ----------------------------------------------------------
#  SIDEBAR FILTERS
# ----------------------------------------------------------
with st.sidebar:
    st.title("🔍 Filters")

    selected_media = st.selectbox("Media Outlet", get_media_names())
    selected_country = st.selectbox("Target Country", get_countries())
    selected_actor = st.selectbox("Foreign Actor", get_actors())

    intents = ["All"] + sorted(df['strategic_intent'].dropna().unique())
    selected_intent = st.selectbox("Strategic Intent", intents)

    tones = ["All"] + sorted(df['tone'].dropna().unique())
    selected_tone = st.selectbox("Tone", tones)

# ----------------------------------------------------------
#  APPLY FILTERS
# ----------------------------------------------------------
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

# ----------------------------------------------------------
#  PAGE TITLE & INFLUENCE INDEX
# ----------------------------------------------------------
st.title("🌍 Vulnerability Index Tool")

# Contextual Influence Index (from your contextual_all_intents_v2.py)
@st.cache_data
def get_influence_score(actor, country):
    scores = [CA[i].get(actor, {}).get(country, 0) for i in CA]
    return sum(scores)/len(scores) if scores else 0

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

# ----------------------------------------------------------
#  PAGINATION SETUP
# ----------------------------------------------------------
articles_per_page = 6
total_pages = (len(filtered) - 1) // articles_per_page + 1

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

# ----------------------------------------------------------
#  ARTICLE CARDS WITH SCRAPED IMAGE
# ----------------------------------------------------------
for _, row in page_articles.iterrows():
    
    # 1. SCALING WARNING: This scraping operation is what will introduce delays!
    # It will run up to 6 times every time you click 'Next ➡' or change a filter.
    image_url = scrape_og_image(row.get('URL'))

    # Use columns to place the image next to the expander
    img_col, text_col = st.columns([1, 4])
    
    with img_col:
        # Display the scraped image if found
        if image_url:
            st.image(image_url, width=120, caption=row['media_outlet'])
        else:
            st.info("No featured image found.")

    with text_col:
        # The expander contains the article summary and details
        # Added the posting time to the expander title for better context
        posting_time_str = row['posting_time'].strftime('%Y-%m-%d') if pd.notna(row['posting_time']) else "Date Unknown"
        
        with st.expander(f"**{row['article_text'][:100]}...** (Source: {row['media_outlet']} - {posting_time_str})"):
            st.caption(
                f"**Target Country**: {row['target_country']} | "
                f"**Foreign Actor**: {row['inferred_actor']}"
            )

            st.write(
                row['article_text'] if pd.notna(row['article_text']) else "No summary available."
            )

            st.markdown(
                f"**Tone**: `{row['tone']}` | "
                f"**Strategic Intent**: `{row['strategic_intent']}`"
            )

            if pd.notna(row.get('URL', None)):
                st.markdown(f"[🔗 Read full article]({row['URL']})")
    
    st.markdown("---") # Separator between articles for clarity
