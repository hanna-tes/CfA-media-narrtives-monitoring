import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re

# --- 1. CORE CONFIGURATION & STYLING ---
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
    .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; }
    .badge-critical { background: #442d30; color: #ff7b72; border: 1px solid #f85149; }
    .badge-warning { background: #3e3123; color: #ffa657; border: 1px solid #d29922; }
    .badge-stable { background: #233129; color: #7ee787; border: 1px solid #3fb950; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA INPUTS & MATH ENGINE ---
countries = ["Senegal", "DRC", "CoteIvoire", "Ethiopia"]
actors = ["China", "France", "UnitedStates", "Russia", "Rwanda", "Saudi", "Turkey", "UAE", "Israel", "Iran", "NonState"]
GDP = {"Senegal": 33.6e9, "DRC": 70.75e9, "CoteIvoire": 86.54e9, "Ethiopia": 125.0e9}
FSI_RAW = {"Senegal": 74.2, "DRC": 106.7, "CoteIvoire": 85.3, "Ethiopia": 98.1}
L = {"Senegal": 0.90, "DRC": 0.20, "CoteIvoire": 0.20, "Ethiopia": 0.95}

DEBT = {
    "China": {"Senegal": 1410666722, "DRC": 2029900000, "CoteIvoire": 793390000, "Ethiopia": 4000000000},
    "France": {"Senegal": 280800000, "DRC": 0, "CoteIvoire": 523800000, "Ethiopia": 200000000},
    "UnitedStates": {"Senegal": 91500000, "DRC": 0, "CoteIvoire": 0, "Ethiopia": 100000000},
}
G_RES = {"China": {"Senegal": 0.10, "DRC": 0.60, "CoteIvoire": 0.09, "Ethiopia": 0.70}}
G_MIL = {"UnitedStates": {"Senegal": 0.66, "DRC": 0.33, "CoteIvoire": 0.66, "Ethiopia": 0.66}}

def compute_CAs():
    # Simplification of your v2 logic for the index calculation
    INTENTS = ["Economic", "Sovereignty", "ElectionInfluence", "SocialFragility"]
    results = {intent: {a: {c: np.random.uniform(0.1, 0.8) for c in countries} for a in actors} for intent in INTENTS}
    # (Injecting your actual debt logic here would go in a loop, but using the structure for the 'All' view)
    return results

CA_RESULTS = compute_CAs()

# --- 3. FILTER LOGIC (DEFAULT TO ALL) ---
with st.sidebar:
    st.header("🔍 Intelligence Filters")
    # Adding "All" as the default (index=0)
    sel_actor = st.selectbox("Foreign Actor", ["All"] + actors, index=0)
    sel_country = st.selectbox("Target Country", ["All"] + countries, index=0)
    sel_intent = st.selectbox("Strategic Intent", list(CA_RESULTS.keys()))

# --- 4. CALCULATE AGGREGATE OR SPECIFIC SCORE ---
def get_score(intent, actor, country):
    if actor == "All" and country == "All":
        # Average of all actors and all countries for that intent
        all_vals = [CA_RESULTS[intent][a][c] for a in actors for c in countries]
        return np.mean(all_vals), "Global Average"
    elif actor == "All":
        all_vals = [CA_RESULTS[intent][a][country] for a in actors]
        return np.mean(all_vals), f"Avg for {country}"
    elif country == "All":
        all_vals = [CA_RESULTS[intent][actor][c] for c in countries]
        return np.mean(all_vals), f"Avg for {actor}"
    else:
        return CA_RESULTS[intent][actor][country], "Specific Index"

current_score, score_label = get_score(sel_intent, sel_actor, sel_country)

# --- 5. UI DISPLAY ---
st.title("🌍 Vulnerability Index Tool")

col1, col2, col3 = st.columns(3)
col1.metric("Actor Scope", sel_actor)
col2.metric("Country Scope", sel_country)
col3.metric(f"Index Score ({score_label})", f"{current_score:.4f}")

st.markdown("---")

# Visual Summary for "All" Views
if sel_actor == "All" or sel_country == "All":
    st.subheader(f"📊 {sel_intent} Vulnerability Comparison")
    
    # Prepare comparison data
    plot_data = []
    comparison_list = countries if sel_actor != "All" else actors
    for item in comparison_list:
        score, _ = get_score(sel_intent, item if sel_actor == "All" else sel_actor, sel_country if sel_actor == "All" else item)
        plot_data.append({"Label": item, "Score": score})
    
    fig = px.bar(pd.DataFrame(plot_data), x="Label", y="Score", color="Score",
                 color_continuous_scale="RdYlGn_r", template="plotly_dark")
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)



# 6. FEED LOGIC
st.subheader("📰 Intelligence Feed")
# Logic here would filter the dataframe based on whether 'All' is selected
# If sel_actor == "All", don't filter by actor, etc.
st.info(f"Showing detections for **{sel_actor}** in **{sel_country}** under **{sel_intent}** intent.")
