import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re

# --- 1. CONFIGURATION & DARK THEME ---
st.set_page_config(page_title="Vulnerability Index Tool", layout="wide", initial_sidebar_state="expanded")

# Inject Custom CSS for the High-Contrast Dark Theme
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

# --- 2. DATA CONSTANTS (Your contextual_all_intents_v2 data) ---
countries = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
actors = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]

GDP = {"Senegal": 33.6e9, "DRC": 70.75e9, "CoteIvoire": 86.54e9, "Ethiopia": 125.0e9}
DEBT = {
    "China": {"Senegal": 1410666722.69, "DRC": 2029900000.0, "CoteIvoire": 793390000.0, "Ethiopia": 4000000000.0},
    "France": {"Senegal": 280800000.0, "DRC": 0.0, "CoteIvoire": 523800000.0, "Ethiopia": 200000000.0},
    "UnitedStates": {"Senegal": 91500000.0, "DRC": 0.0, "CoteIvoire": 0.0, "Ethiopia": 100000000.0}
}
G_RES = {"China": {"Senegal": 0.10, "DRC": 0.60, "CoteIvoire": 0.09, "Ethiopia": 0.70}}
G_MIL = {"UnitedStates": {"Senegal": 0.66, "DRC": 0.33, "CoteIvoire": 0.66, "Ethiopia": 0.66}}
FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}

# --- 3. MATHEMATICAL ENGINE ---
def clip(x): return max(0.0, min(1.0, float(x)))

@st.cache_data
def compute_all_scores():
    """Generates the full Actor x Country x Intent score matrix."""
    g = {a: {c: {} for c in countries} for a in actors}
    # Initial G-Factors
    for a in actors:
        for c in countries:
            d = DEBT.get(a, {}).get(c, 0.0)
            g_debt = clip(d / GDP[c]) if GDP[c] > 0 else 0.0
            g_res = G_RES.get(a, {}).get(c, 0.0)
            g_mil = G_MIL.get(a, {}).get(c, 0.0)
            g[a][c] = {"debt": g_debt, "res": g_res, "mil": g_mil, "elec": 0.25, "frag": clip((FSI_RAW[c]-22)/98)}

    # Normalization & CA Calculation (Simplified version of your intent logic)
    intents = ["Economic", "Sovereignty", "ElectionInfluence", "SocialFragility"]
    intent_map = {
        "Economic": ["debt", "res"],
        "Sovereignty": ["debt", "mil"],
        "ElectionInfluence": ["elec", "debt"],
        "SocialFragility": ["frag", "mil"]
    }
    
    final_results = {intent: {a: {c: 0.0 for c in countries} for a in actors} for intent in intents}
    for intent, factors in intent_map.items():
        for a in actors:
            for c in countries:
                # Basic weighted average for UI display
                score = sum(g[a][c][f] for f in factors) / len(factors)
                final_results[intent][a][c] = clip(score)
    return final_results

CA_MATRIX = compute_all_scores()

# --- 4. SIDEBAR FILTERS (Default to "All") ---
with st.sidebar:
    st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=120)
    st.header("🔍 Intelligence Filters")
    sel_actor = st.selectbox("Foreign Actor", ["All"] + actors, index=0)
    sel_country = st.selectbox("Target Country", ["All"] + countries, index=0)
    sel_intent = st.selectbox("Strategic Intent", list(CA_MATRIX.keys()))

# --- 5. SCORE CALCULATION LOGIC ---
def get_display_score():
    if sel_actor == "All" and sel_country == "All":
        vals = [CA_MATRIX[sel_intent][a][c] for a in actors for c in countries]
        return np.mean(vals), "Global Average Index"
    elif sel_actor == "All":
        vals = [CA_MATRIX[sel_intent][a][sel_country] for a in actors]
        return np.mean(vals), f"Avg Index for {sel_country}"
    elif sel_country == "All":
        vals = [CA_MATRIX[sel_intent][sel_actor][c] for c in countries]
        return np.mean(vals), f"Avg Index for {sel_actor}"
    else:
        return CA_MATRIX[sel_intent][sel_actor][sel_country], "Specific Influence Score"

score, score_type = get_display_score()

# --- 6. MAIN DASHBOARD UI ---
st.title("🌍 Vulnerability Index Tool")
st.markdown(f"**Analysis Mode:** {sel_intent} Influence Analysis")

# Metrics Row
c1, c2, c3 = st.columns(3)
c1.metric("Selected Actor", sel_actor)
c2.metric("Selected Country", sel_country)
c3.metric(score_type, f"{score:.4f}")

st.markdown("---")

# Comparative Visualization (Only if 'All' is selected)
if sel_actor == "All" or sel_country == "All":
    st.subheader(f"📊 {sel_intent} Intensity Comparison")
    
    # Determine what to compare on the X-axis
    comp_list = countries if sel_actor != "All" else actors
    plot_data = []
    
    for item in comp_list:
        # Get the individual scores for the chart
        act = item if sel_actor == "All" else sel_actor
        cnt = sel_country if sel_actor == "All" else item
        s = CA_MATRIX[sel_intent][act][cnt]
        plot_data.append({"Entity": item, "Vulnerability Score": s})
    
    fig = px.bar(pd.DataFrame(plot_data), x="Entity", y="Vulnerability Score", 
                 color="Vulnerability Score", color_continuous_scale="Reds", template="plotly_dark")
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# Heatmap integration would appear here


st.markdown("---")

# --- 7. INTELLIGENCE FEED (Placeholder Data) ---
st.subheader("📰 Intelligence Feed")
mock_feed = [
    {"source": "REUTERS", "actor": "China", "country": "DRC", "tone": "Sensationalist", "head": "New Mining Accords Signed in Kinshasa"},
    {"source": "AFP", "actor": "France", "country": "Senegal", "head": "Diplomatic Tensions Rise Over Regional Security", "tone": "Critical"},
    {"source": "AP", "actor": "UnitedStates", "country": "Ethiopia", "head": "Humanitarian Aid Package Announced", "tone": "Positive"},
]

# Filter mock feed based on selections
display_feed = [f for f in mock_feed if (sel_actor == "All" or f['actor'] == sel_actor) and (sel_country == "All" or f['country'] == sel_country)]

if not display_feed:
    st.info("No active alerts for this specific filter set.")
else:
    for item in display_feed:
        t_class = "badge-warning" if item['tone'] == "Sensationalist" else "badge-critical" if item['tone'] == "Critical" else "badge-stable"
        st.markdown(f"""
        <div class="article-strip">
            <div>
                <div class="meta-text">{item['source']} | {item['country']}</div>
                <a href="#" class="headline-link">{item['head']}</a>
            </div>
            <span class="badge {t_class}">{item['tone']}</span>
        </div>
        """, unsafe_allow_html=True)
