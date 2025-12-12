import streamlit as st
import pandas as pd
import base64
from data_loader import load_and_transform_data, get_media_names, get_countries, get_actors
from contextual_all_intents_v2 import CA  # Your influence scores

# ----------------------------------------------------------
#  PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(
    page_title="Vulnerability Index Tool",
    layout="wide"
)


# ----------------------------------------------------------
#  CFA BACKGROUND WATERMARK
# ----------------------------------------------------------
def add_cfa_background():
    try:
        with open("CFA_Logo.png", "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: 40%;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}

            .stApp::before {{
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-image: inherit;
                background-size: inherit;
                background-position: inherit;
                background-repeat: inherit;
                opacity: 0.06;
                z-index: -1;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

    except FileNotFoundError:
        st.warning("⚠️ cfa_logo_light.png not found — CfA watermark disabled.")

add_cfa_background()


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
#  PAGE TITLE
# ----------------------------------------------------------
st.title("🌍 Vulnerability Index Monitoring Dashboard")


# ----------------------------------------------------------
#  CONTEXTUAL INFLUENCE INDEX
# ----------------------------------------------------------
if selected_country != "All" and selected_actor != "All":
    try:
        scores = [CA[i].get(selected_actor, {}).get(selected_country, 0) for i in CA]
        avg_score = sum(scores) / len(scores) if scores else 0

        st.metric(
            "Contextual Influence Index",
            f"{avg_score:.2f}",
            help="Composite score (0.0–1.0) based on debt, military, resources, and strategic alignment."
        )

    except Exception as e:
        st.error("Influence index unavailable")


st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")


# ----------------------------------------------------------
#  PAGINATION SETUP
# ----------------------------------------------------------
articles_per_page = 10
total_pages = (len(filtered) - 1) // articles_per_page + 1

if "page" not in st.session_state:
    st.session_state.page = 0

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if st.button("⬅ Previous") and st.session_state.page > 0:
        st.session_state.page -= 1

with col3:
    if st.button("Next ➡") and st.session_state.page < total_pages - 1:
        st.session_state.page += 1

start_idx = st.session_state.page * articles_per_page
end_idx = start_idx + articles_per_page
page_articles = filtered.iloc[start_idx:end_idx]


# ----------------------------------------------------------
#  ARTICLE CARDS WITH EXPANDER
# ----------------------------------------------------------
for _, row in page_articles.iterrows():
    with st.expander(f"{row['article_text'][:100]}..."):
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

st.write(f"Page {st.session_state.page + 1} of {total_pages}")
