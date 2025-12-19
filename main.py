# main.py
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from urllib.parse import urlparse
import re
from math import isfinite
from data_loader import get_vulnerability_system

# Import everything from data_loader (ensure it includes the vulnerability logic)
from data_loader import (
    load_and_transform_data,
    enrich_with_scraping_and_llm,
    get_media_names,
    get_countries,
    get_actors,
    KEYWORD_LABELS,
    get_vulnerability_system,  # ✅ Keep this (new)
    compute_gs,                # ✅ Keep (used for radar chart)
    COUNTRIES as VULN_COUNTRIES,
    ACTORS as VULN_ACTORS
)
# ------------------ NAME MAPPING FOR UI/DATA ALIGNMENT ------------------
ACTOR_MAP = {
    "France": "France",
    "Russia": "Russia",
    "China": "China",
    "Turkey": "Turkey",
    "Rwanda": "Rwanda",
    "US": "UnitedStates",
    "USA": "UnitedStates",
    "United States": "UnitedStates",
    "UAE": "UAE",
    "Saudi Arabia": "Saudi",
    "Saudi": "Saudi",
    "Iran": "Iran",
    "Israel": "Israel",
    "Non-State": "NonState",
    "NonState": "NonState",
}

COUNTRY_MAP = {
    "DRC": "DRC",
    "Democratic Republic of the Congo": "DRC",
    "Senegal": "Senegal",
    "Ethiopia": "Ethiopia",
    "Cote d'Ivoire": "CoteIvoire",
    "Côte d'Ivoire": "CoteIvoire",
    "Ivory Coast": "CoteIvoire",
}

# Reverse maps for display
ACTOR_UI_NAME = {v: k for k, v in ACTOR_MAP.items() if k != v}
ACTOR_UI_NAME.update({a: a for a in VULN_ACTORS})  # fallback

# ------------------ INTENT UI LABELING ------------------
INTENT_UI_MAP = {
    "Economic": "Economic Coercion",
    "Sovereignty": "Diplomatic Pressure",
    "SocialFragility": "Information Warfare",
    "ElectionInfluence": "Election Influence",
    "MilitaryPresence": "Military Presence",
    "ResourceDependency": "Resource Dependency",
    "LGBTQ": "LGBTQ Framing",
    "Religious": "Religious Polarization"
}
INTENT_INTERNAL_MAP = {v: k for k, v in INTENT_UI_MAP.items()}

UI_INTENTS = ["All"] + list(INTENT_UI_MAP.values())

def get_influence_baseline_score(actor, country, intent_key):
    # Get the CA system via cached function (not global var)
    CA = get_vulnerability_system()  # ← this is the fix!
    
    a_norm = ACTOR_MAP.get(actor, actor)
    c_norm = COUNTRY_MAP.get(country, country)

    if intent_key == "All":
        scores = []
        for i in CA:  # ← now uses local `CA`, not global `VULNERABILITY_CA`
            if a_norm in CA[i] and c_norm in CA[i][a_norm]:
                scores.append(CA[i][a_norm][c_norm])
        return sum(scores) / len(scores) if scores else 0.0
    else:
        return CA.get(intent_key, {}).get(a_norm, {}).get(c_norm, 0.0)

# ------------------ THEME & LOGO ------------------
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0="
BRIGHT_LOGO_URL = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png"

st.markdown(f"""
<style>
.stApp {{
    background-image: url("{NEW_BACKGROUND_URL}");
    background-size: cover;
    background-attachment: fixed;
}}
/* Metric Cards */
.metric-card {{
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 20px;
    border-radius: 16px;
    text-align: center;
    box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    margin: 10px;
    border: 1px solid #e0e0e0;
}}
.metric-value {{
    font-size: 2.0em;
    font-weight: bold;
    color: #2d3748;
}}
.metric-label {{
    font-size: 1em;
    color: #718096;
    margin-top: 8px;
    font-weight: 500;
}}
.metric-delta.positive {{ color: #38a169; }}
.metric-delta.negative {{ color: #e53e3e; }}
.metric-delta {{ font-size: 0.95em; margin-top: 6px; }}

/* Keep your dark article cards */
.card {{
    background: #1e1e1e; 
    color: #ffffff; 
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
h1, h2, h3, h4, h5, h6 {{
    color: #1a1a1a !important;
}}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")
st.image(BRIGHT_LOGO_URL, width=150)
st.title("🌍 Contextual Vulnerability Index Tool")

# ------------------ LOAD & ENRICH DATA ------------------
with st.spinner("Loading dataset..."):
    df_base = load_and_transform_data()
if df_base.empty:
    st.stop()

with st.spinner("Enriching articles (Scraping & Summarizing)..."):
    progress_bar = st.progress(0)
    status_text = st.empty()
    def progress_callback(p, msg):
        progress_bar.progress(min(p, 1.0))
        status_text.text(msg)
    df = enrich_with_scraping_and_llm(df_base, progress_callback=progress_callback)
progress_bar.empty()
status_text.empty()

# ------------------ CREATE DISPLAY TEXT ------------------
def create_display_text(df_in):
    df_out = df_in.copy()
    def extract_summary_and_headline(text):
        if not isinstance(text, str) or not text.strip():
            return 'Summary extraction pending or failed.', 'Article Snippet (No Text)'
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return text[:100] + "...", "Article Snippet"
        headline = sentences[0] + "."
        if len(sentences) > 1:
            summary = headline + " " + sentences[1] + "."
        else:
            summary = headline
        return summary, headline
    results = df_out['article_text'].fillna('').apply(extract_summary_and_headline)
    df_out['llm_summary'] = [r[0] for r in results]
    df_out['display_headline'] = [r[1] for r in results]
    return df_out

df = create_display_text(df)

# ------------------ SIDEBAR FILTERS ------------------
with st.sidebar:
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
    selected_intent_ui = st.selectbox("Strategic Intent", UI_INTENTS)
    tones = ["All"] + sorted(df['tone'].dropna().unique().tolist())
    selected_tone = st.selectbox("Tone", tones)

# Map UI intent back to internal key
intent_key = "All" if selected_intent_ui == "All" else INTENT_INTERNAL_MAP[selected_intent_ui]

# ------------------ APPLY FILTERS ------------------
filtered = df.copy()
if selected_media != "All":
    filtered = filtered[filtered['media_outlet'] == selected_media]
if selected_country != "All":
    filtered = filtered[filtered['target_country'] == selected_country]
if selected_actor != "All":
    filtered = filtered[filtered['inferred_actor'] == selected_actor]
if intent_key != "All":
    # Optional: filter articles by strategic_intent if your data has it
    pass
if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

# ------------------ TONE SCORE ------------------
tone_mapping = {
    'Factual': 0.0, 'Neutral': 0.0, 'Positive': 1.0,
    'Sensationalist': -0.3, 'Cynical': -0.8, 'Alarmist': -1.0
}
filtered['tone_numeric'] = filtered['tone'].map(tone_mapping).fillna(0.0)
current_tone_score = filtered['tone_numeric'].mean() if not filtered.empty else 0.0

# ------------------ VULNERABILITY SCORE ------------------
baseline_influence_score = 0.0
final_influence_score = 0.0
if selected_actor != "All" and selected_country != "All":
    baseline_influence_score = get_influence_baseline_score(selected_actor, selected_country, intent_key)
    
    # Dynamic modulation
    volume_factor = min(1.0, len(filtered) / 100)
    tone_factor = 1.0 - (current_tone_score / 2.0)
    final_influence_score = min(1.0, baseline_influence_score * volume_factor * tone_factor)
else:
    final_influence_score = 0.0

# ------------------ KPI METRICS (FANCY CARDS) ------------------
current_article_count = len(filtered)
previous_article_count = max(1, int(len(df) * 0.95))
article_delta = current_article_count - previous_article_count
article_delta_class = "positive" if article_delta >= 0 else "negative"

tone_delta = current_tone_score - 0.1
tone_delta_class = "positive" if tone_delta >= 0 else "negative"

influence_delta = final_influence_score - (final_influence_score * 0.95)
influence_delta_class = "negative" if final_influence_score > 0.6 else "positive"

st.header("📊 Key Indicators")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{current_article_count:,.0f}</div>
        <div class="metric-label">Articles Analyzed</div>
        <div class="metric-delta {article_delta_class}">Δ {article_delta:+,.0f}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{current_tone_score:+.2f}</div>
        <div class="metric-label">Avg. Tone Score</div>
        <div class="metric-delta {tone_delta_class}">Δ {tone_delta:+.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{final_influence_score:.2f}</div>
        <div class="metric-label">Contextual Vulnerability Index</div>
        <div class="metric-delta {influence_delta_class}">High risk</div>
    </div>
    """, unsafe_allow_html=True)

# ------------------ ALERTS ------------------
if selected_actor != "All" and selected_country != "All":
    if final_influence_score >= 0.8:
        st.error(f"🚨 **Critical Risk**: {selected_actor} narratives in {selected_country} show very high contextual vulnerability (**{final_influence_score:.2f}**).")
    elif final_influence_score >= 0.6:
        st.warning(f"⚠️ **Elevated Risk**: Contextual vulnerability is high (**{final_influence_score:.2f}**). Monitor closely.")

# ------------------ SCORE EXPLANATION (NEW SECTION) ------------------
with st.expander("📘 What Do These Scores Mean?", expanded=False):
    st.markdown("""
    ### 🔹 **Contextual Vulnerability Index (CVI)**
    A **0.0–1.0** score that combines:
    - **Structural vulnerability** (debt, military presence, resource dependence, social fragility)
    - **Narrative activity** (volume of articles, tone)

    > **0.0–0.3**: Low risk  
    > **0.4–0.6**: Moderate risk — baseline structural factors present  
    > **0.7–0.8**: High risk — active narratives exploiting vulnerabilities  
    > **0.9–1.0**: Critical risk — high activity + deep structural exposure  

    ### 🔹 **Tone Score**
    Measures **journalistic framing**:
    - **+1.0**: Strongly positive (e.g., praise, support)
    - **0.0**: Neutral or factual
    - **-1.0**: Highly negative (alarmist, cynical)

    ### 🔹 **How It's Calculated**
    ```python
    CVI = Structural_Vulnerability × min(Article_Volume / 100, 1.0) × (1 - Tone_Score / 2)
    ```
    Negative tone **increases** vulnerability (since adversaries often use alarmist framing).
    """)

# ------------------ RADIAL CHART (if applicable) ------------------
if selected_actor != "All" and selected_country != "All" and intent_key != "All":
    st.subheader("🎯 Vulnerability Drivers")
    g_system = compute_gs()
    a_norm = ACTOR_MAP.get(selected_actor, selected_actor)
    c_norm = COUNTRY_MAP.get(selected_country, selected_country)
    
    if a_norm in g_system and c_norm in g_system[a_norm]:
        factors = list(VULNERABILITY_CA[intent_key].keys())  # Not quite—use INTENT_FACTORS
        from data_loader import INTENT_FACTORS
        factor_list = INTENT_FACTORS.get(intent_key, [])
        r_vals = [g_system[a_norm][c_norm].get(f, 0) for f in factor_list]
        theta_vals = [f.replace('_', ' ').title() for f in factor_list]
        
        if r_vals and any(r > 0 for r in r_vals):
            fig = px.line_polar(
                r=r_vals,
                theta=theta_vals,
                line_close=True,
                template="plotly_dark",
                title=f"Key Drivers: {INTENT_UI_MAP.get(intent_key, intent_key)}"
            )
            fig.update_traces(fill='toself', fillcolor='rgba(100, 149, 237, 0.3)')
            st.plotly_chart(fig, use_container_width=True)

# ------------------ REGIONAL HEATMAP ------------------
if selected_actor != "All" and intent_key != "All":
    st.subheader("🌍 Regional Vulnerability Comparison")
    heatmap_data = []
    for c in VULN_COUNTRIES:
        score = get_influence_baseline_score(selected_actor, c, intent_key)
        heatmap_data.append({"Country": c, "Vulnerability": score})
    df_heat = pd.DataFrame(heatmap_data)
    fig = px.bar(
        df_heat,
        x="Country",
        y="Vulnerability",
        color="Vulnerability",
        color_continuous_scale="RdYlBu_r",
        range_color=[0,1],
        title=f"How vulnerable is each country to {selected_actor} on '{INTENT_UI_MAP.get(intent_key, intent_key)}'?"
    )
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# ------------------ ARTICLE LISTING (UNCHANGED) ------------------
st.markdown("---")
st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")

articles_per_page = 5
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)
if "page" not in st.session_state:
    st.session_state.page = 0
start_idx = st.session_state.page * articles_per_page
end_idx = start_idx + articles_per_page
page_articles = filtered.iloc[start_idx:end_idx]

for _, row in page_articles.iterrows():
    summary_display = str(row.get('llm_summary', 'Summary extraction failed.'))
    headline = str(row.get('display_headline', 'Article Snippet (No Headline)'))
    image_url = str(row.get('urlToImage', ''))
    display_image = image_url if image_url and image_url not in ['None', 'nan', ''] else 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
    media = str(row.get('media_outlet', 'Unknown'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))
    posting_time = "Date Unknown"
    if pd.notna(row.get('posting_time')):
        try:
            posting_time = pd.to_datetime(row['posting_time']).strftime('%Y-%m-%d %H:%M')
        except:
            pass

    st.markdown(f"""
    <div class="card">
        <div style="display: flex; align-items: flex-start;">
            <div class="image-container">
                {f'<img src="{display_image}" alt="Article Image">' if 'No+Image' not in display_image else '<div style="width: 180px; height: 120px; background: #333; display: flex; align-items: center; justify-content: center; border-radius: 8px;">No Image</div>'}
            </div>
            <div style="flex: 1;">
                <div class="header">{headline}</div>
                <div class="meta">Source: {media} – {posting_time}</div>
                <div class="summary">{summary_display}</div>
                <div class="tags">
                    <span class="tag">Tone: {tone}</span>
                    <span class="tag">Intent: {intent}</span>
                </div>
                <a href="{row.get('URL', '#')}" target="_blank" class="link">🔗 Read full article</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ------------------ PAGINATION ------------------
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.button("⬅ Previous", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page - 1)), disabled=(st.session_state.page == 0))
with col2:
    st.markdown(f"<h5 style='text-align: center;'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
with col3:
    st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1))
