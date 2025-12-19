import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re

# --- 1. CONFIGURATION & STYLING ---
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
    .headline-link { color: #58a6ff; font-size: 1rem; font-weight: 600; text-decoration: none; }
    .meta-text { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; }
    .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; margin-left: 10px; }
    .badge-critical { background: #442d30; color: #ff7b72; border: 1px solid #f85149; }
    .badge-warning { background: #3e3123; color: #ffa657; border: 1px solid #d29922; }
    .badge-stable { background: #233129; color: #7ee787; border: 1px solid #3fb950; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA LOADING (Real Dataset) ---
@st.cache_data
def load_real_data():
    try:
        # Replace with your actual filename
        df = pd.read_csv("Merged_dataset_sample.csv")
        # Ensure column names match your logic
        # Clean article text for headlines
        def get_headline(text):
            if not isinstance(text, str): return "No Content"
            match = re.search(r'[^.?!]*[.?!]', text)
            return match.group(0).strip() if match else text[:60] + "..."
        
        df['headline'] = df['article_text'].apply(get_headline)
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()

raw_df = load_real_data()

# --- 3. MATHEMATICAL MODEL (Real Data Constants) ---
countries = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
actors = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]
GDP = {"Senegal": 33.6e9, "DRC": 70.75e9, "CoteIvoire": 86.54e9, "Ethiopia": 125.0e9}
FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}

# --- 4. SIDEBAR FILTERS (Handling "All") ---
with st.sidebar:
    st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=120)
    st.header("🔍 Intelligence Filters")
    sel_actor = st.selectbox("Foreign Actor", ["All"] + actors, index=0)
    sel_country = st.selectbox("Target Country", ["All"] + countries, index=0)
    sel_intent = st.selectbox("Strategic Intent", ["Economic", "Sovereignty", "ElectionInfluence", "SocialFragility"])

# --- 5. INDEX LOGIC (Handling 'All' without KeyErrors) ---
# We calculate a matrix of all possible scores first
@st.cache_data
def get_score_matrix():
    # This simulates your math logic for every actor/country pair
    matrix = {intent: pd.DataFrame(index=actors, columns=countries) for intent in ["Economic", "Sovereignty", "ElectionInfluence", "SocialFragility"]}
    for intent in matrix:
        for a in actors:
            for c in countries:
                # Placeholder for your specific compute_CAs logic
                matrix[intent].loc[a, c] = np.random.uniform(0.1, 0.9)
    return matrix

SCORE_MATRIX = get_score_matrix()

def calculate_display_metrics():
    df_intent = SCORE_MATRIX[sel_intent]
    
    if sel_actor == "All" and sel_country == "All":
        val = df_intent.values.mean()
        label = "Global Average Index"
    elif sel_actor == "All":
        val = df_intent[sel_country].mean()
        label = f"Avg Actor Influence in {sel_country}"
    elif sel_country == "All":
        val = df_intent.loc[sel_actor].mean()
        label = f"Avg {sel_actor} Influence across Africa"
    else:
        val = df_intent.loc[sel_actor, sel_country]
        label = "Specific Influence Index"
    
    return val, label

current_score, score_label = calculate_display_metrics()

# --- 6. MAIN DASHBOARD ---
st.title("🌍 Vulnerability Index Tool")
col1, col2, col3 = st.columns(3)
col1.metric("Actor Scope", sel_actor)
col2.metric("Country Scope", sel_country)
col3.metric(score_label, f"{current_score:.4f}")

st.markdown("---")

# Visual Comparison Chart
st.subheader(f"📊 {sel_intent} Comparison")
if sel_actor == "All" or sel_country == "All":
    if sel_actor == "All" and sel_country == "All":
        # Global: Compare Actors by their average influence
        plot_df = SCORE_MATRIX[sel_intent].mean(axis=1).reset_index()
    elif sel_actor == "All":
        # Compare all actors for one country
        plot_df = SCORE_MATRIX[sel_intent][sel_country].reset_index()
    else:
        # Compare all countries for one actor
        plot_df = SCORE_MATRIX[sel_intent].loc[sel_actor].reset_index()
    
    plot_df.columns = ["Entity", "Score"]
    fig = px.bar(plot_df, x="Entity", y="Score", color="Score", color_continuous_scale="Reds", template="plotly_dark")
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# --- 7. INTELLIGENCE FEED (Real Data Integration) ---
st.subheader("📰 Intelligence Feed")

# Apply Pandas filtering logic for "All"
filtered_df = raw_df.copy()
if sel_actor != "All":
    filtered_df = filtered_df[filtered_df['inferred_actor'] == sel_actor]
if sel_country != "All":
    filtered_df = filtered_df[filtered_df['target_country'] == sel_country]

if filtered_df.empty:
    st.info("No matching articles found in the dataset for these filters.")
else:
    for _, row in filtered_df.head(15).iterrows():
        # Map tone to CSS class
        tone = row.get('tone', 'Neutral')
        t_class = "badge-warning" if tone == "Sensationalist" else "badge-critical" if tone == "Critical" else "badge-stable"
        
        st.markdown(f"""
        <div class="article-strip">
            <div>
                <div class="meta-text">{row.get('media_outlet', 'News')} | {row.get('target_country', 'Global')}</div>
                <a href="{row.get('URL', '#')}" target="_blank" class="headline-link">{row.get('headline', 'View Article')}</a>
            </div>
            <span class="badge {t_class}">{tone}</span>
        </div>
        """, unsafe_allow_html=True)
